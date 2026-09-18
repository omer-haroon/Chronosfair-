from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from scheduler.models import AcademicSession, Department, GARun
from scheduler.genetic.course_ga import CourseGAProblem


class Command(BaseCommand):
    help = "Run the Course Scheduler Genetic Algorithm for an academic session."

    def add_arguments(self, parser):
        parser.add_argument('--session', type=str, required=True, help="AcademicSession.name, e.g. 'Fall 2026'")
        parser.add_argument('--department', type=str, default=None, help="Department.code (optional — run just one department, e.g. 'CE')")
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
            name=f"Course GA — {session.name}" + (f" ({department.code})" if department else ""),
            algorithm='ga_simple',
            schedule_type='course',
            academic_session=session,
            department=department,
            population_size=options['population'],
            generations=options['generations'],
            mutation_rate=options['mutation_rate'],
            status='running',
            started_at=timezone.now(),
        )

        self.stdout.write(f"Building problem for {session.name}" + (f" / {department.code}" if department else "") + "...")
        problem = CourseGAProblem(academic_session=session, department=department)
        self.stdout.write(f"{len(problem.units)} units to schedule "
                           f"({sum(1 for d in problem.domains if not d)} with no valid room).")

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

        schedules = problem.save_result(result, ga_run)
        self.stdout.write(self.style.SUCCESS(
            f"Saved {len(schedules)} Schedule rows under GARun #{ga_run.id}."
        ))
