from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from scheduler.models import AcademicSession, Department, GARun
from scheduler.genetic.invigilation import InvigilationGAProblem


class Command(BaseCommand):
    help = "Run the Invigilation Duty Genetic Algorithm for an academic session. Requires exams to already exist (run run_exam_ga first)."

    def add_arguments(self, parser):
        parser.add_argument('--session', type=str, required=True, help="AcademicSession.name, e.g. 'Fall 2026'")
        parser.add_argument('--exam-type', type=str, default=None,
                             choices=['mid_term', 'final', 'quiz', 'lab_exam', 'presentation', 'viva'],
                             help="Optional filter — only assign invigilators to exams of this type.")
        parser.add_argument('--department', type=str, default=None, help="Department.code (optional filter on teacher pool, e.g. 'CE')")
        parser.add_argument('--population', type=int, default=60)
        parser.add_argument('--generations', type=int, default=200)
        parser.add_argument('--mutation-rate', type=float, default=0.05)

    def handle(self, *args, **options):
        try:
            session = AcademicSession.objects.get(name=options['session'])
        except AcademicSession.DoesNotExist:
            raise CommandError(f"AcademicSession '{options['session']}' not found.")

        department = None
        if options['department']:
            try:
                department = Department.objects.get(code=options['department'])
            except Department.DoesNotExist:
                raise CommandError(f"Department with code '{options['department']}' not found.")

        ga_run = GARun.objects.create(
            name=f"Invigilation GA — {session.name}",
            algorithm='ga_simple',
            schedule_type='invigilation',
            academic_session=session,
            department=department,
            population_size=options['population'],
            generations=options['generations'],
            mutation_rate=options['mutation_rate'],
            status='running',
            started_at=timezone.now(),
        )

        self.stdout.write(f"Building invigilation problem for {session.name}...")
        try:
            problem = InvigilationGAProblem(
                academic_session=session,
                exam_type=options['exam_type'],
                department=department,
            )
        except ValueError as e:
            ga_run.status = 'failed'
            ga_run.completed_at = timezone.now()
            ga_run.save()
            raise CommandError(str(e))

        self.stdout.write(f"{len(problem.exams)} exams to staff, {len(problem.teachers)} teachers available.")

        self.stdout.write("Running GA...")
        result = problem.run(
            population_size=options['population'],
            generations=options['generations'],
            mutation_rate=options['mutation_rate'],
        )
        self.stdout.write(self.style.SUCCESS(
            f"Best fitness: {result.best_fitness:.4f}  "
            f"(avg: {result.avg_fitness:.4f}, converged at gen {result.converged_at})"
        ))

        duties = problem.save_result(result, ga_run)
        self.stdout.write(self.style.SUCCESS(
            f"Saved {len(duties)} InvigilationDuty rows under GARun #{ga_run.id}."
        ))
