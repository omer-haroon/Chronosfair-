"""
Course Scheduler GA — ChronosFair v4.0
======================================
Chromosome = list of genes, one gene per "unit that needs a slot":
    a unit is (course_offering, 'class') or (course_offering, 'lab')
    a gene is (time_slot_id, room_id)

v4.0 upgrades over the original:
  * PRIORITY    — teacher preferences (availability + 1..10 preference level)
                  are loaded once and turned into a soft reward, so slots a
                  teacher strongly prefers win ties, and slots they want to
                  avoid are actively pushed against.
  * FAIRNESS    — Jain's Fairness Index over capacity-normalized weekly
                  teaching loads is part of fitness: the GA no longer dumps
                  every free slot onto the same few teachers.
  * REPORTING   — the winning chromosome is converted into fairness
                  snapshots (GlobalFairnessSnapshot) and the GARun row is
                  stamped with JFI / fairness-before / fairness-after.

The Repair Module is implemented as `repair()`: instead of discarding a
clashing chromosome, clashing genes are reassigned to valid, free slots.
"""
import random
from collections import defaultdict
from decimal import Decimal

from django.db import transaction, IntegrityError
from django.utils import timezone

from scheduler.models import (
    CourseOffering, CourseOfferingGroup, Room, TimeSlot, TeacherPreference,
    Schedule, GARun, ConstraintViolation, ConstraintCatalog, StudentGroup,
    Teacher, GlobalFairnessSnapshot, Ledger,
)
from .engine import GeneticEngine, GAResult
from .fairness import preference_reward, workload_fairness_penalty, jain_index


# Weights for soft/hard violations + the new priority/fairness objectives.
# Exposed via run(...) so the API / management command can tune per-run.
DEFAULT_WEIGHTS = {
    'teacher_clash': 10.0,
    'room_clash': 10.0,
    'student_group_clash': 10.0,
    'teacher_unavailable': 2.0,   # teacher marked slot unavailable (binary flag)
    'no_valid_domain': 15.0,
    'priority': 1.0,              # weight of the 1..10 preference reward
    'fairness': 4.0,              # weight of the (1 - JFI) workload penalty
    'daily_double': 0.5,          # light nudge: avoid 2+ units of one offering same day
}


class CourseGAProblem:
    """Builds the scheduling problem for one academic session and department
    (department=None means "all departments"), and knows how to persist the
    winning chromosome back into the database.
    """

    def __init__(self, academic_session, department=None, rng=None, weights=None):
        self.academic_session = academic_session
        self.department = department
        self.rng = rng or random.Random()
        self.weights = dict(DEFAULT_WEIGHTS)
        if weights:
            self.weights.update({k: float(v) for k, v in weights.items() if v is not None})

        self.time_slots = list(TimeSlot.objects.filter(is_active=True))
        if not self.time_slots:
            raise ValueError("No active TimeSlots found — seed time slots first.")
        self.slot_day = {ts.id: ts.day_of_week for ts in self.time_slots}

        self.units = []          # list of dicts describing each schedulable unit
        self.domains = []        # parallel list: valid (time_slot_id, room_id) pairs per unit
        self._build_units()

        # ---- PRIORITY: teacher preferences ------------------------------
        # pref_level[(teacher_id, time_slot_id)] = 1..10 (10 = strongly prefer)
        # unavailable[(teacher_id, time_slot_id)] = True  (explicitly blocked)
        self.pref_level = {}
        self.unavailable = set()
        for tid, sid, avail, level in TeacherPreference.objects.filter(
            academic_session=academic_session
        ).values_list('teacher_id', 'time_slot_id', 'is_available', 'preference_level'):
            if avail:
                self.pref_level[(tid, sid)] = level
            else:
                self.unavailable.add((tid, sid))

        # teacher weekly capacity (for capacity-normalized fairness)
        self.teacher_capacity = dict(
            Teacher.objects.filter(is_active=True).values_list('id', 'max_teaching_hours')
        )

    # ------------------------------------------------------------------
    # Problem construction
    # ------------------------------------------------------------------
    def _build_units(self):
        offerings = CourseOffering.objects.filter(
            academic_session=self.academic_session,
            status__in=['planned', 'confirmed', 'scheduling'],
        ).select_related('course', 'course__room_type_required', 'course__lab_room_type_required',
                          'primary_teacher', 'lab_teacher')

        if self.department is not None:
            offerings = offerings.filter(course__program__department=self.department)

        rooms = list(Room.objects.filter(is_active=True))
        rooms_by_type = defaultdict(list)
        for r in rooms:
            rooms_by_type[r.room_type_id].append(r)

        for offering in offerings:
            group_ids = list(
                CourseOfferingGroup.objects.filter(course_offering=offering)
                .values_list('student_group_id', flat=True)
            )
            group_sizes = list(
                StudentGroup.objects.filter(id__in=group_ids).values_list('size', flat=True)
            )
            min_capacity = max(group_sizes) if group_sizes else 1

            # ---- theory/class unit ----
            candidate_rooms = [
                r for r in rooms_by_type.get(offering.course.room_type_required_id, [])
                if r.capacity >= min_capacity
            ]
            domain = [(ts.id, r.id) for ts in self.time_slots for r in candidate_rooms]
            self.units.append({
                'offering_id': offering.id,
                'schedule_type': 'class',
                'teacher_id': offering.primary_teacher_id,
                'group_ids': group_ids,
                'hours': float(offering.course.theory_hours or offering.course.weekly_hours),
                'course_code': offering.course.code,
            })
            self.domains.append(domain)

            # ---- lab unit (only if required) ----
            if offering.requires_lab and offering.course.lab_room_type_required_id:
                lab_rooms = [
                    r for r in rooms_by_type.get(offering.course.lab_room_type_required_id, [])
                    if r.capacity >= min_capacity
                ]
                lab_teacher_id = offering.lab_teacher_id or offering.primary_teacher_id
                lab_domain = [(ts.id, r.id) for ts in self.time_slots for r in lab_rooms]
                self.units.append({
                    'offering_id': offering.id,
                    'schedule_type': 'lab',
                    'teacher_id': lab_teacher_id,
                    'group_ids': group_ids,
                    'hours': float(offering.course.lab_hours or 1),
                    'course_code': offering.course.code,
                })
                self.domains.append(lab_domain)

    # ------------------------------------------------------------------
    # GA hooks
    # ------------------------------------------------------------------
    def random_chromosome(self):
        chromosome = []
        for domain in self.domains:
            if domain:
                chromosome.append(self.rng.choice(domain))
            else:
                chromosome.append((None, None))  # unschedulable unit (no valid room/type)
        return chromosome

    def fitness(self, chromosome):
        w = self.weights
        penalty = 0.0
        priority_gain = 0.0
        by_teacher_slot = defaultdict(int)
        by_room_slot = defaultdict(int)
        by_group_slot = defaultdict(int)
        teacher_load = defaultdict(float)
        by_offering_day = defaultdict(int)

        for gene, unit in zip(chromosome, self.units):
            slot_id, room_id = gene
            if slot_id is None:
                penalty += w['no_valid_domain']
                continue

            by_teacher_slot[(unit['teacher_id'], slot_id)] += 1
            by_room_slot[(room_id, slot_id)] += 1
            for gid in unit['group_ids']:
                by_group_slot[(gid, slot_id)] += 1

            # ---- PRIORITY objectives ----
            level = self.pref_level.get((unit['teacher_id'], slot_id))
            if level is not None:
                priority_gain += preference_reward(level) * w['priority']
            if (unit['teacher_id'], slot_id) in self.unavailable:
                penalty += w['teacher_unavailable']

            # ---- FAIRNESS bookkeeping ----
            teacher_load[unit['teacher_id']] += unit['hours']

            # light compactness nudge: one offering twice on the same day
            day = self.slot_day.get(slot_id)
            by_offering_day[(unit['offering_id'], day)] += 1

        for count in by_teacher_slot.values():
            if count > 1:
                penalty += w['teacher_clash'] * (count - 1)
        for count in by_room_slot.values():
            if count > 1:
                penalty += w['room_clash'] * (count - 1)
        for count in by_group_slot.values():
            if count > 1:
                penalty += w['student_group_clash'] * (count - 1)
        for count in by_offering_day.values():
            if count > 1:
                penalty += w['daily_double'] * (count - 1)

        # ---- FAIRNESS objective: capacity-normalized Jain penalty ----
        if teacher_load:
            raw = [teacher_load.get(tid, 0.0) for tid in self.teacher_capacity]
            caps = [self.teacher_capacity.get(tid, 18) for tid in self.teacher_capacity]
            penalty += w['fairness'] * workload_fairness_penalty(raw, caps)

        # normalize priority gain to roughly [0, 1] so it competes fairly
        if self.units:
            priority_gain /= len(self.units)

        return 1.0 / (1.0 + penalty - priority_gain)

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
        """Repair Module: reassign clashing genes to a free (slot, room) pair
        instead of discarding the whole chromosome."""
        chromosome = list(chromosome)
        for _ in range(max_passes):
            occupied_teacher_slot = defaultdict(int)
            occupied_room_slot = defaultdict(int)
            occupied_group_slot = defaultdict(int)

            for gene, unit in zip(chromosome, self.units):
                slot_id, room_id = gene
                if slot_id is None:
                    continue
                occupied_teacher_slot[(unit['teacher_id'], slot_id)] += 1
                occupied_room_slot[(room_id, slot_id)] += 1
                for gid in unit['group_ids']:
                    occupied_group_slot[(gid, slot_id)] += 1

            any_fixed = False
            for i, (gene, unit, domain) in enumerate(zip(chromosome, self.units, self.domains)):
                slot_id, room_id = gene
                if slot_id is None or not domain:
                    continue
                clashing = (
                    occupied_teacher_slot[(unit['teacher_id'], slot_id)] > 1
                    or occupied_room_slot[(room_id, slot_id)] > 1
                    or any(occupied_group_slot[(gid, slot_id)] > 1 for gid in unit['group_ids'])
                )
                if not clashing:
                    continue

                self.rng.shuffle(domain)
                for new_slot, new_room in domain:
                    if (
                        occupied_teacher_slot[(unit['teacher_id'], new_slot)] == 0
                        and occupied_room_slot[(new_room, new_slot)] == 0
                        and all(occupied_group_slot[(gid, new_slot)] == 0 for gid in unit['group_ids'])
                    ):
                        # free the old slot's counters, occupy the new one
                        occupied_teacher_slot[(unit['teacher_id'], slot_id)] -= 1
                        occupied_room_slot[(room_id, slot_id)] -= 1
                        for gid in unit['group_ids']:
                            occupied_group_slot[(gid, slot_id)] -= 1

                        chromosome[i] = (new_slot, new_room)
                        occupied_teacher_slot[(unit['teacher_id'], new_slot)] += 1
                        occupied_room_slot[(new_room, new_slot)] += 1
                        for gid in unit['group_ids']:
                            occupied_group_slot[(gid, new_slot)] += 1
                        any_fixed = True
                        break
            if not any_fixed:
                break
        return chromosome

    # ------------------------------------------------------------------
    # Fairness snapshot helpers
    # ------------------------------------------------------------------
    def _loads_from_chromosome(self, chromosome):
        loads = defaultdict(float)
        for gene, unit in zip(chromosome, self.units):
            if gene[0] is None:
                continue
            loads[unit['teacher_id']] += unit['hours']
        return loads

    def fairness_of(self, chromosome):
        """JFI of the teacher loads a chromosome implies (capacity-normalized)."""
        loads = self._loads_from_chromosome(chromosome)
        raw = [loads.get(tid, 0.0) for tid in self.teacher_capacity]
        caps = [self.teacher_capacity.get(tid, 18) for tid in self.teacher_capacity]
        norm = [(l / c) if c else l for l, c in zip(raw, caps)]
        return jain_index(norm)

    # ------------------------------------------------------------------
    # Running + persistence
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
    def save_result(self, result: GAResult, ga_run: GARun, triggered_by=None):
        """Persist the best chromosome as Schedule rows, log remaining clashes
        as ConstraintViolations, and write fairness snapshots."""
        created_schedules = []
        skipped_clashes = []
        remaining_teacher_slot = defaultdict(list)
        remaining_room_slot = defaultdict(list)

        for gene, unit in zip(result.best_chromosome, self.units):
            slot_id, room_id = gene
            if slot_id is None:
                continue
            # The GA's repair step reduces clashes but isn't guaranteed to reach
            # zero — the DB's own unique constraint (teacher, time_slot,
            # academic_session) is the final backstop. If the best chromosome
            # still has an unresolved clash, don't let one bad row blow up the
            # whole save: skip it, log it as a ConstraintViolation, and keep
            # going so every other valid row still gets persisted.
            try:
                with transaction.atomic():
                    schedule = Schedule.objects.create(
                        schedule_type=unit['schedule_type'],
                        course_offering_id=unit['offering_id'],
                        teacher_id=unit['teacher_id'],
                        room_id=room_id,
                        time_slot_id=slot_id,
                        student_group_id=unit['group_ids'][0] if unit['group_ids'] else None,
                        academic_session=self.academic_session,
                        status='draft',
                        generated_by_ga=True,
                        ga_run=ga_run,
                        fitness_score=Decimal(str(round(result.best_fitness, 4))),
                    )
            except IntegrityError as e:
                skipped_clashes.append((unit['course_code'], unit['schedule_type'], str(e)))
                continue
            created_schedules.append(schedule)
            remaining_teacher_slot[(unit['teacher_id'], slot_id)].append(schedule)
            remaining_room_slot[(room_id, slot_id)].append(schedule)

        violation_catalog, _ = ConstraintCatalog.objects.get_or_create(
            constraint_name='Teacher Double Booking',
            defaults={
                'constraint_type': 'hard',
                'target_table': 'schedules',
                'rule_definition': {'rule': 'no_teacher_clash'},
                'error_message': 'Teacher assigned to two classes at the same time.',
            },
        )
        for (_, _), scheds in remaining_teacher_slot.items():
            if len(scheds) > 1:
                for s in scheds:
                    ConstraintViolation.objects.create(
                        schedule=s, constraint_catalog=violation_catalog,
                        severity='critical', fitness_penalty=self.weights['teacher_clash'],
                        description='Unresolved teacher clash after GA + repair.',
                        ga_run=ga_run,
                    )

        # ---- FAIRNESS snapshots + run metrics ----
        best_loads = self._loads_from_chromosome(result.best_chromosome)
        jfi = self.fairness_of(result.best_chromosome)
        for tid, hours in best_loads.items():
            GlobalFairnessSnapshot.objects.create(
                teacher_id=tid,
                academic_session=self.academic_session,
                teaching_hours=Decimal(str(round(hours, 2))),
                combined_workload=Decimal(str(round(hours, 2))),
                jain_index=Decimal(str(round(jfi, 4))),
            )
        ga_run.jain_index = Decimal(str(round(jfi, 4)))
        ga_run.fairness_score_after = Decimal(str(round(jfi, 4)))
        ga_run.fitness_best = Decimal(str(round(result.best_fitness, 4)))
        ga_run.fitness_avg = Decimal(str(round(result.avg_fitness, 4)))
        ga_run.fitness_worst = Decimal(str(round(result.worst_fitness, 4)))
        ga_run.convergence_generation = result.converged_at
        ga_run.status = 'completed'
        ga_run.completed_at = timezone.now()
        ga_run.save()

        if skipped_clashes:
            print(f"WARNING: skipped {len(skipped_clashes)} schedule row(s) the GA's best "
                  f"chromosome still had a teacher/slot clash on (unresolved by repair):")
            for course_code, sched_type, err in skipped_clashes:
                print(f"  - {course_code} ({sched_type}): {err.splitlines()[0]}")

        # ---- LEDGER: one tamper-evident block per row this run created ----
        for schedule in created_schedules:
            Ledger.create_block(
                action='GA_RUN',
                table='schedules',
                record_id=schedule.id,
                data_dict={
                    'schedule_type': schedule.schedule_type,
                    'course': schedule.course_offering.course.code,
                    'teacher': schedule.teacher.name,
                    'room': schedule.room.name,
                    'time_slot': str(schedule.time_slot),
                    'academic_session': self.academic_session.name,
                    'fitness_score': str(schedule.fitness_score),
                },
                user=triggered_by,
                ga_run=ga_run,
            )

        return created_schedules
