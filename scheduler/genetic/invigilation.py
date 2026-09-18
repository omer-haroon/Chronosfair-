"""
Invigilation Duty GA — ChronosFair v4.0 (GA #3 of 3)
====================================================
Assigns invigilators to already-scheduled exams.

Chromosome = list of genes, one per exam:
    a gene is a tuple of teacher_ids, length = invigilators required for the
    exam's room (1 per 30 students, at least 1; first teacher becomes the
    Head Invigilator on save).

Objectives:
  HARD  — no teacher in two exams at the same (date, slot)
          no duplicate teacher inside one exam's gene
  SOFT  — respect max_per_day / max_per_week (InvigilationPreference)
          respect unavailable_dates and teacher leaves
  PRIORITY — reward preferred weekdays / preferred rooms
  FAIRNESS — Jain's index over per-teacher invigilation hours so duties are
             shared evenly instead of piling onto the same few people
"""
import math
import random
from collections import defaultdict
from datetime import timedelta
from decimal import Decimal

from django.db import transaction, IntegrityError
from django.utils import timezone

from scheduler.models import (
    Exam, Teacher, TeacherLeave, InvigilationDuty, InvigilationPreference,
    GARun, ConstraintViolation, ConstraintCatalog, Ledger,
)
from .engine import GeneticEngine, GAResult
from .fairness import jain_index


DEFAULT_WEIGHTS = {
    'same_slot_clash': 10.0,     # teacher in two exams at once
    'duplicate_in_exam': 10.0,   # same teacher twice in one gene
    'over_max_day': 4.0,
    'over_max_week': 4.0,
    'unavailable': 6.0,          # leave / unavailable_date clash
    'no_valid_domain': 15.0,
    'priority': 1.0,             # preferred weekday / preferred room reward
    'fairness': 5.0,             # weight of (1 - JFI) over invigilation hours
}

STUDENTS_PER_INVIGILATOR = 30


class InvigilationGAProblem:
    def __init__(self, academic_session, exam_type=None, department=None,
                 rng=None, weights=None):
        self.academic_session = academic_session
        self.exam_type = exam_type
        self.department = department
        self.rng = rng or random.Random()
        self.weights = dict(DEFAULT_WEIGHTS)
        if weights:
            self.weights.update({k: float(v) for k, v in weights.items() if v is not None})

        exams = Exam.objects.filter(academic_session=academic_session)
        if exam_type:
            exams = exams.filter(exam_type=exam_type)
        self.exams = list(exams.select_related('room', 'time_slot', 'course_offering'))
        if not self.exams:
            raise ValueError("No exams found for this session — run the Exam GA first.")

        teachers = list(Teacher.objects.filter(is_active=True))
        if department is not None:
            dept_teachers = [t for t in teachers if t.department_id == department.id]
            if dept_teachers:
                teachers = dept_teachers
        self.teachers = teachers
        self.teacher_ids = [t.id for t in teachers]

        # ---- PRIORITY data ----
        self.pref_by_teacher = {}
        self.unavailable_dates = defaultdict(set)   # teacher_id -> {date, ...}
        self.leave_dates = defaultdict(set)         # teacher_id -> {date, ...}
        self.max_per_day = defaultdict(lambda: 2)
        self.max_per_week = defaultdict(lambda: 5)

        for pref in InvigilationPreference.objects.filter(academic_session=academic_session):
            self.pref_by_teacher[pref.teacher_id] = pref
            for d in (pref.unavailable_dates or []):
                try:
                    y, m, dd = str(d)[:10].split('-')
                    self.unavailable_dates[pref.teacher_id].add(f"{y}-{m}-{dd}")
                except ValueError:
                    pass
        for leave in TeacherLeave.objects.filter(
            academic_session=academic_session, is_approved=True,
            start_date__lte=max(e.exam_date for e in self.exams),
            end_date__gte=min(e.exam_date for e in self.exams),
        ):
            d = leave.start_date
            while d <= leave.end_date:
                self.leave_dates[leave.teacher_id].add(d.isoformat())
                d += timezone.timedelta(days=1) if hasattr(timezone, 'timedelta') else None
        # (timedelta import fix below)
        from datetime import timedelta as _td
        for leave in TeacherLeave.objects.filter(
            academic_session=academic_session, is_approved=True,
        ):
            d = leave.start_date
            while d <= leave.end_date:
                self.leave_dates[leave.teacher_id].add(d.isoformat())
                d += _td(days=1)

        # how many invigilators each exam needs
        self.required = {
            e.id: max(1, math.ceil((e.room.get_exam_capacity() if e.room_id else 30)
                                    / STUDENTS_PER_INVIGILATOR))
            for e in self.exams
        }
        self.exam_hours = {e.id: float(e.duration_minutes) / 60.0 for e in self.exams}

    # ------------------------------------------------------------------
    # GA hooks
    # ------------------------------------------------------------------
    def random_chromosome(self):
        return [tuple(self.rng.sample(self.teacher_ids,
                                      min(self.required[e.id], len(self.teacher_ids))))
                for e in self.exams]

    def fitness(self, chromosome):
        w = self.weights
        penalty = 0.0
        gain = 0.0
        by_teacher_slot = defaultdict(int)     # (teacher, date, slot) -> count
        per_teacher_hours = defaultdict(float)
        per_teacher_day = defaultdict(int)     # (teacher, date) -> count
        per_teacher_week = defaultdict(int)    # (teacher, iso-week) -> count

        for gene, exam in zip(chromosome, self.exams):
            if not gene or len(gene) < self.required[exam.id]:
                penalty += w['no_valid_domain']
            if len(set(gene)) != len(gene):
                penalty += w['duplicate_in_exam'] * (len(gene) - len(set(gene)))

            date_iso = exam.exam_date.isoformat()
            week_key = exam.exam_date.isocalendar()[:2]
            slot_key = (exam.exam_date, exam.time_slot_id)
            hours = self.exam_hours[exam.id]

            for tid in set(gene):
                by_teacher_slot[(tid,) + slot_key] += 1
                per_teacher_hours[tid] += hours
                per_teacher_day[(tid, date_iso)] += 1
                per_teacher_week[(tid,) + week_key] += 1

                if date_iso in self.unavailable_dates.get(tid, set()):
                    penalty += w['unavailable']
                if date_iso in self.leave_dates.get(tid, set()):
                    penalty += w['unavailable']

                # ---- PRIORITY rewards ----
                pref = self.pref_by_teacher.get(tid)
                if pref is not None:
                    if pref.preferred_weekdays and exam.exam_date.isoweekday() in pref.preferred_weekdays:
                        gain += 0.5 * w['priority']
                    if pref.preferred_rooms and exam.room_id:
                        if exam.room_id in pref.preferred_rooms.values_list('id', flat=True):
                            gain += 0.5 * w['priority']

        for count in by_teacher_slot.values():
            if count > 1:
                penalty += w['same_slot_clash'] * (count - 1)
        for (tid, date_iso), cnt in per_teacher_day.items():
            if cnt > self.max_per_day[tid]:
                penalty += w['over_max_day'] * (cnt - self.max_per_day[tid])
        for key, cnt in per_teacher_week.items():
            tid = key[0]
            if cnt > self.max_per_week[tid]:
                penalty += w['over_max_week'] * (cnt - self.max_per_week[tid])

        # ---- FAIRNESS: Jain over per-teacher invigilation hours ----
        if self.teacher_ids:
            vec = [per_teacher_hours.get(tid, 0.0) for tid in self.teacher_ids]
            penalty += w['fairness'] * (1.0 - jain_index(vec))
            gain /= max(1, len(self.exams))

        return 1.0 / (1.0 + penalty - gain)

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
        mutated = [list(gene) for gene in chromosome]
        for i, exam in enumerate(self.exams):
            if self.rng.random() < mutation_rate:
                need = self.required[exam.id]
                pool = [t for t in self.teacher_ids
                        if t not in mutated[i]]
                self.rng.shuffle(pool)
                mutated[i] = pool[:need] if len(pool) >= need else mutated[i]
        return [tuple(g) for g in mutated]

    def repair(self, chromosome, max_passes=3):
        chromosome = [list(g) for g in chromosome]
        for _ in range(max_passes):
            by_teacher_slot = defaultdict(list)  # (teacher,date,slot) -> [(exam_idx, pos)]
            seen = defaultdict(int)
            for i, exam in enumerate(self.exams):
                for pos, tid in enumerate(chromosome[i]):
                    by_teacher_slot[(tid, exam.exam_date, exam.time_slot_id)].append((i, pos))
                    seen[(i, tid)] += 1

            any_fixed = False
            for i, exam in enumerate(self.exams):
                date_iso = exam.exam_date.isoformat()
                for pos, tid in enumerate(list(chromosome[i])):
                    clashing = len(by_teacher_slot[(tid, exam.exam_date, exam.time_slot_id)]) > 1
                    dup = seen[(i, tid)] > 1
                    on_leave = (date_iso in self.unavailable_dates.get(tid, set())
                                or date_iso in self.leave_dates.get(tid, set()))
                    if not (clashing or dup or on_leave):
                        continue
                    # pick a replacement teacher that is free at this slot
                    free = [c for c in self.teacher_ids
                            if c != tid
                            and seen[(i, c)] == 0
                            and not any(idx == i for idx, _ in by_teacher_slot[(c, exam.exam_date, exam.time_slot_id)])
                            and date_iso not in self.unavailable_dates.get(c, set())
                            and date_iso not in self.leave_dates.get(c, set())]
                    if not free:
                        continue
                    replacement = self.rng.choice(free)
                    by_teacher_slot[(tid, exam.exam_date, exam.time_slot_id)] = [
                        p for p in by_teacher_slot[(tid, exam.exam_date, exam.time_slot_id)]
                        if p != (i, pos)]
                    seen[(i, tid)] -= 1
                    chromosome[i][pos] = replacement
                    by_teacher_slot[(replacement, exam.exam_date, exam.time_slot_id)].append((i, pos))
                    seen[(i, replacement)] += 1
                    any_fixed = True
            if not any_fixed:
                break
        return [tuple(g) for g in chromosome]

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
    def save_result(self, result: GAResult, ga_run: GARun):
        created = []
        skipped_clashes = []
        by_teacher_slot = defaultdict(list)
        for gene, exam in zip(result.best_chromosome, self.exams):
            for pos, tid in enumerate(gene):
                # Same backstop as the Course/Exam GA: repair() tries to
                # remove same-slot clashes and duplicate-teacher-in-exam
                # genes, but isn't guaranteed to find a free replacement.
                # The DB's unique constraint on (exam, teacher) is the final
                # line of defence — skip + log rather than crash the save.
                try:
                    with transaction.atomic():
                        duty = InvigilationDuty.objects.create(
                            exam=exam,
                            teacher_id=tid,
                            role='head_invigilator' if pos == 0 else 'invigilator',
                            hours=Decimal(str(round(self.exam_hours[exam.id], 2))),
                            status='assigned',
                            ga_run=ga_run,
                        )
                except IntegrityError as e:
                    skipped_clashes.append((exam.course_offering.course.code, tid, str(e)))
                    continue
                created.append(duty)
                by_teacher_slot[(tid, exam.exam_date, exam.time_slot_id)].append(duty)

        catalog, _ = ConstraintCatalog.objects.get_or_create(
            constraint_name='Invigilator Double Booking',
            defaults={
                'constraint_type': 'hard',
                'target_table': 'invigilation_duties',
                'rule_definition': {'rule': 'no_invigilator_clash'},
                'error_message': 'Teacher invigilating two exams at the same time.',
            },
        )
        for (_, _, _), duties in by_teacher_slot.items():
            if len(duties) > 1:
                for d in duties:
                    ConstraintViolation.objects.create(
                        invigilation=d, constraint_catalog=catalog,
                        severity='critical', fitness_penalty=self.weights['same_slot_clash'],
                        description='Unresolved invigilator clash after GA + repair.',
                        ga_run=ga_run,
                    )

        # ---- FAIRNESS metrics on the final assignment ----
        loads = defaultdict(float)
        for gene, exam in zip(result.best_chromosome, self.exams):
            for tid in gene:
                loads[tid] += self.exam_hours[exam.id]
        if loads:
            vec = [loads.get(tid, 0.0) for tid in self.teacher_ids]
            jfi = jain_index(vec)
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
            print(f"WARNING: skipped {len(skipped_clashes)} invigilation duty row(s) "
                  f"with an unresolved duplicate/clash after GA + repair:")
            for course_code, tid, err in skipped_clashes:
                print(f"  - {course_code} / teacher #{tid}: {err.splitlines()[0]}")

        # ---- LEDGER: one tamper-evident block per duty row this run created ----
        for duty in created:
            Ledger.create_block(
                action='GA_RUN',
                table='invigilation_duties',
                record_id=duty.id,
                data_dict={
                    'exam': duty.exam.course_offering.course.code,
                    'teacher': duty.teacher.name,
                    'role': duty.role,
                    'hours': str(duty.hours),
                },
                user=ga_run.triggered_by,
                ga_run=ga_run,
            )

        return created
