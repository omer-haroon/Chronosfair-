"""
Exam Scheduler GA — ChronosFair v4.0 (GA #2 of 3)
=================================================
Schedules exams for a session's course offerings.

Chromosome = list of genes, one per exam unit:
    a unit is a CourseOffering that needs an exam
    a gene is (exam_date, time_slot_id, room_id)

Objectives:
  HARD  — no room double-booked on (date, slot)
          no student group sits two exams in the same slot
  SOFT  — a group never sits two exams on the same day (fatigue rule)
          exams spread evenly across the exam window (FAIRNESS via Jain's
          index over exams-per-day — no single overloaded day)
  Domain construction already excludes holidays and dates outside the
  session, and rooms that cannot hold the group.
"""
import random
from collections import defaultdict
from datetime import timedelta
from decimal import Decimal

from django.db import transaction, IntegrityError
from django.utils import timezone

from scheduler.models import (
    AcademicSession, CourseOffering, CourseOfferingGroup, Room, TimeSlot,
    Holiday, Exam, GARun, ConstraintViolation, ConstraintCatalog, StudentGroup,
    Ledger,
)
from .engine import GeneticEngine, GAResult
from .fairness import jain_index


DEFAULT_WEIGHTS = {
    'room_clash': 10.0,
    'group_same_slot': 10.0,     # two exams, same group, same slot (impossible to sit)
    'group_same_day': 3.0,       # two exams, same group, same day (fatigue)
    'no_valid_domain': 15.0,
    'fairness': 4.0,             # weight of (1 - JFI) over exams-per-day
    'window_edge': 0.2,          # light nudge: don't compress everything at window start
}


class ExamGAProblem:
    def __init__(self, academic_session, exam_type='final', department=None,
                 rng=None, weights=None):
        self.academic_session = academic_session
        self.exam_type = exam_type
        self.department = department
        self.rng = rng or random.Random()
        self.weights = dict(DEFAULT_WEIGHTS)
        if weights:
            self.weights.update({k: float(v) for k, v in weights.items() if v is not None})

        self.time_slots = list(TimeSlot.objects.filter(is_active=True))
        if not self.time_slots:
            raise ValueError("No active TimeSlots found — seed time slots first.")

        # Exam window: explicit exam dates on the session, else last 3 weeks
        session = academic_session
        if session.exam_start_date and session.exam_end_date:
            self.window_start, self.window_end = session.exam_start_date, session.exam_end_date
        else:
            self.window_end = session.end_date
            self.window_start = session.end_date - timedelta(days=20)

        holiday_dates = set(
            Holiday.objects.filter(holiday_date__gte=self.window_start,
                                   holiday_date__lte=self.window_end)
            .values_list('holiday_date', flat=True)
        )
        self.valid_dates = [
            self.window_start + timedelta(days=i)
            for i in range((self.window_end - self.window_start).days + 1)
            if (self.window_start + timedelta(days=i)) not in holiday_dates
        ]
        if not self.valid_dates:
            raise ValueError("Exam window has no valid (non-holiday) dates.")

        self.units = []
        self.domains = []
        self._build_units()

    # ------------------------------------------------------------------
    def _build_units(self):
        offerings = CourseOffering.objects.filter(
            academic_session=self.academic_session,
            status__in=['planned', 'confirmed', 'scheduling', 'active'],
        ).select_related('course', 'course__room_type_required')
        if self.department is not None:
            offerings = offerings.filter(course__program__department=self.department)

        rooms = list(Room.objects.filter(is_active=True))
        for offering in offerings:
            group_ids = list(
                CourseOfferingGroup.objects.filter(course_offering=offering)
                .values_list('student_group_id', flat=True)
            )
            sizes = list(StudentGroup.objects.filter(id__in=group_ids).values_list('size', flat=True))
            needed = max(sizes) if sizes else 1

            # exams go in lecture rooms / exam halls big enough for the group
            candidate_rooms = [
                r for r in rooms
                if r.get_exam_capacity() >= needed
                and r.room_type_id == offering.course.room_type_required_id
            ]
            if not candidate_rooms:  # fall back to any room big enough
                candidate_rooms = [r for r in rooms if r.get_exam_capacity() >= needed]

            domain = [(d, ts.id, r.id) for d in self.valid_dates
                      for ts in self.time_slots for r in candidate_rooms]
            self.units.append({
                'offering_id': offering.id,
                'group_ids': group_ids,
                'course_code': offering.course.code,
                'enrollment': sum(sizes),
            })
            self.domains.append(domain)

    # ------------------------------------------------------------------
    # GA hooks
    # ------------------------------------------------------------------
    def random_chromosome(self):
        return [self.rng.choice(domain) if domain else (None, None, None)
                for domain in self.domains]

    def fitness(self, chromosome):
        w = self.weights
        penalty = 0.0
        by_room = defaultdict(int)
        by_group_slot = defaultdict(int)
        by_group_day = defaultdict(int)
        exams_per_day = defaultdict(int)

        for gene, unit in zip(chromosome, self.units):
            date, slot_id, room_id = gene
            if date is None:
                penalty += w['no_valid_domain']
                continue
            by_room[(room_id, date, slot_id)] += 1
            exams_per_day[date] += 1
            for gid in unit['group_ids']:
                by_group_slot[(gid, date, slot_id)] += 1
                by_group_day[(gid, date)] += 1

        for count in by_room.values():
            if count > 1:
                penalty += w['room_clash'] * (count - 1)
        for count in by_group_slot.values():
            if count > 1:
                penalty += w['group_same_slot'] * (count - 1)
        for count in by_group_day.values():
            if count > 1:
                penalty += w['group_same_day'] * (count - 1)

        # FAIRNESS: even spread of exams across the window (JFI over exams/day)
        if exams_per_day:
            target = len(self.units) / len(self.valid_dates)
            vec = [exams_per_day.get(d, 0) for d in self.valid_dates]
            # blend absolute JFI with deviation-from-even-target
            penalty += w['fairness'] * (1.0 - jain_index(vec))
            penalty += w['window_edge'] * abs(len(exams_per_day) - min(len(self.valid_dates), max(1, int(len(self.units) / max(target, 1))))) / len(self.valid_dates)

        return 1.0 / (1.0 + penalty)

    def crossover(self, parent_a, parent_b):
        child_a, child_b = [], []
        for gene_a, gene_b in zip(parent_a, parent_b):
            if self.rng.random() < 0.5:
                child_a.append(gene_a)
                child_b.append(gene_b)
            else:
                child_a.append(gene_b)
                child_b.append(gene_a)
        return child_a, child_b

    def mutate(self, chromosome, mutation_rate):
        mutated = list(chromosome)
        for i, domain in enumerate(self.domains):
            if domain and self.rng.random() < mutation_rate:
                mutated[i] = self.rng.choice(domain)
        return mutated

    def repair(self, chromosome, max_passes=3):
        chromosome = list(chromosome)
        for _ in range(max_passes):
            occupied_room = defaultdict(int)
            occupied_group = defaultdict(int)
            for gene, unit in zip(chromosome, self.units):
                date, slot_id, room_id = gene
                if date is None:
                    continue
                occupied_room[(room_id, date, slot_id)] += 1
                for gid in unit['group_ids']:
                    occupied_group[(gid, date, slot_id)] += 1

            any_fixed = False
            for i, (gene, unit, domain) in enumerate(zip(chromosome, self.units, self.domains)):
                date, slot_id, room_id = gene
                if date is None or not domain:
                    continue
                clashing = (
                    occupied_room[(room_id, date, slot_id)] > 1
                    or any(occupied_group[(gid, date, slot_id)] > 1 for gid in unit['group_ids'])
                )
                if not clashing:
                    continue
                self.rng.shuffle(domain)
                for new_date, new_slot, new_room in domain:
                    if (occupied_room[(new_room, new_date, new_slot)] == 0
                            and all(occupied_group[(gid, new_date, new_slot)] == 0
                                    for gid in unit['group_ids'])):
                        occupied_room[(room_id, date, slot_id)] -= 1
                        for gid in unit['group_ids']:
                            occupied_group[(gid, date, slot_id)] -= 1
                        chromosome[i] = (new_date, new_slot, new_room)
                        occupied_room[(new_room, new_date, new_slot)] += 1
                        for gid in unit['group_ids']:
                            occupied_group[(gid, new_date, new_slot)] += 1
                        any_fixed = True
                        break
            if not any_fixed:
                break
        return chromosome

    # ------------------------------------------------------------------
    def run(self, population_size=60, generations=200, mutation_rate=0.05,
            crossover_rate=0.8, elitism_count=4, tournament_size=3,
            weights=None) -> GAResult:
        if weights:
            self.weights.update({k: float(v) for k, v in weights.items() if v is not None})
        engine = GeneticEngine(
            random_chromosome_fn=self.random_chromosome,
            fitness_fn=self.fitness,
            crossover_fn=self.crossover,
            mutate_fn=self.mutate,
            repair_fn=self.repair,
            population_size=population_size,
            generations=generations,
            mutation_rate=mutation_rate,
            crossover_rate=crossover_rate,
            elitism_count=elitism_count,
            tournament_size=tournament_size,
            rng=self.rng,
        )
        return engine.run()

    @transaction.atomic
    def save_result(self, result: GAResult, ga_run: GARun, duration_minutes=120):
        created = []
        skipped_clashes = []
        by_room = defaultdict(list)
        slot_duration = {ts.id: ts.duration_minutes() for ts in self.time_slots}

        for gene, unit in zip(result.best_chromosome, self.units):
            date, slot_id, room_id = gene
            if date is None:
                continue
            # Same backstop as the Course GA: the DB's unique constraint on
            # (room, exam_date, time_slot) is the final line of defence if
            # repair couldn't fully clear a room clash. Skip + log instead of
            # letting one bad row abort the whole save.
            try:
                with transaction.atomic():
                    exam = Exam.objects.create(
                        course_offering_id=unit['offering_id'],
                        exam_type=self.exam_type,
                        academic_session=self.academic_session,
                        room_id=room_id,
                        time_slot_id=slot_id,
                        exam_date=date,
                        duration_minutes=min(duration_minutes, slot_duration.get(slot_id, duration_minutes)),
                        status='draft',
                        generated_by_ga=True,
                        ga_run=ga_run,
                        fitness_score=Decimal(str(round(result.best_fitness, 4))),
                    )
            except IntegrityError as e:
                skipped_clashes.append((unit['course_code'], str(e)))
                continue
            created.append(exam)
            by_room[(room_id, date, slot_id)].append(exam)

        catalog, _ = ConstraintCatalog.objects.get_or_create(
            constraint_name='Exam Room Double Booking',
            defaults={
                'constraint_type': 'hard',
                'target_table': 'exams',
                'rule_definition': {'rule': 'no_exam_room_clash'},
                'error_message': 'Room booked for two exams at the same time.',
            },
        )
        for (_, _, _), exams in by_room.items():
            if len(exams) > 1:
                for e in exams:
                    ConstraintViolation.objects.create(
                        exam=e, constraint_catalog=catalog, severity='critical',
                        fitness_penalty=self.weights['room_clash'],
                        description='Unresolved exam room clash after GA + repair.',
                        ga_run=ga_run,
                    )

        ga_run.fitness_best = Decimal(str(round(result.best_fitness, 4)))
        ga_run.fitness_avg = Decimal(str(round(result.avg_fitness, 4)))
        ga_run.fitness_worst = Decimal(str(round(result.worst_fitness, 4)))
        ga_run.convergence_generation = result.converged_at
        ga_run.status = 'completed'
        ga_run.completed_at = timezone.now()
        ga_run.save()

        if skipped_clashes:
            print(f"WARNING: skipped {len(skipped_clashes)} exam row(s) with an "
                  f"unresolved room/date/slot clash after GA + repair:")
            for course_code, err in skipped_clashes:
                print(f"  - {course_code}: {err.splitlines()[0]}")

        # ---- LEDGER: one tamper-evident block per exam row this run created ----
        for exam in created:
            Ledger.create_block(
                action='GA_RUN',
                table='exams',
                record_id=exam.id,
                data_dict={
                    'course': exam.course_offering.course.code,
                    'exam_type': exam.exam_type,
                    'room': exam.room.name,
                    'time_slot': str(exam.time_slot),
                    'exam_date': str(exam.exam_date),
                    'academic_session': self.academic_session.name,
                    'fitness_score': str(exam.fitness_score),
                },
                user=ga_run.triggered_by,
                ga_run=ga_run,
            )

        return created
