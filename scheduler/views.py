import os
import shutil
import tempfile
from io import StringIO

from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.permissions import IsAdminUser
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone
from django.core.management import call_command
from django.core.management.base import CommandError

from .models import (
    User, University, Faculty, Department, Program, Semester,
    AcademicSession, Batch, StudentGroup,
    Building, RoomType, Room, RoomAvailability,
    TimeSlot, Holiday, AcademicCalendar,
    Teacher, TeacherPreference, InvigilationPreference, TeacherLeave,
    Course, CourseOffering, CourseOfferingGroup,
    Schedule, Exam, InvigilationDuty,
    GARun, FairnessRecord, GlobalFairnessSnapshot, TeacherWorkload,
    StudentConflict, ConstraintViolation, RepairHistory,
    Ledger, ConstraintCatalog,
)
from .serializers import (
    UserSerializer, UniversitySerializer, FacultySerializer, DepartmentSerializer,
    ProgramSerializer, SemesterSerializer, AcademicSessionSerializer, BatchSerializer,
    StudentGroupSerializer, BuildingSerializer, RoomTypeSerializer, RoomSerializer,
    RoomAvailabilitySerializer, TimeSlotSerializer, HolidaySerializer,
    AcademicCalendarSerializer, TeacherSerializer, TeacherPreferenceSerializer,
    InvigilationPreferenceSerializer, TeacherLeaveSerializer, CourseSerializer,
    CourseOfferingSerializer, CourseOfferingGroupSerializer, ScheduleSerializer,
    ExamSerializer, InvigilationDutySerializer, GARunSerializer,
    FairnessRecordSerializer, GlobalFairnessSnapshotSerializer, TeacherWorkloadSerializer,
    StudentConflictSerializer, ConstraintViolationSerializer, RepairHistorySerializer,
    LedgerSerializer, ConstraintCatalogSerializer,
)


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    filterset_fields = ['role', 'department', 'is_active']
    search_fields = ['username', 'email', 'first_name', 'last_name']


class UniversityViewSet(viewsets.ModelViewSet):
    queryset = University.objects.all()
    serializer_class = UniversitySerializer
    filterset_fields = ['is_active']
    search_fields = ['code', 'name']


class FacultyViewSet(viewsets.ModelViewSet):
    queryset = Faculty.objects.all()
    serializer_class = FacultySerializer
    filterset_fields = ['university', 'is_active']
    search_fields = ['code', 'name']


class DepartmentViewSet(viewsets.ModelViewSet):
    queryset = Department.objects.all()
    serializer_class = DepartmentSerializer
    filterset_fields = ['faculty', 'is_active']
    search_fields = ['code', 'name']


class ProgramViewSet(viewsets.ModelViewSet):
    queryset = Program.objects.all()
    serializer_class = ProgramSerializer
    filterset_fields = ['department', 'degree_type', 'is_active']
    search_fields = ['code', 'name']


class SemesterViewSet(viewsets.ModelViewSet):
    queryset = Semester.objects.all()
    serializer_class = SemesterSerializer
    filterset_fields = ['program', 'is_active']


class AcademicSessionViewSet(viewsets.ModelViewSet):
    queryset = AcademicSession.objects.all()
    serializer_class = AcademicSessionSerializer
    filterset_fields = ['status', 'is_active']
    search_fields = ['name']


class BatchViewSet(viewsets.ModelViewSet):
    queryset = Batch.objects.all()
    serializer_class = BatchSerializer
    filterset_fields = ['program', 'intake_session', 'is_active']


class StudentGroupViewSet(viewsets.ModelViewSet):
    queryset = StudentGroup.objects.all()
    serializer_class = StudentGroupSerializer
    filterset_fields = ['batch', 'is_active']
    search_fields = ['section_name']


class BuildingViewSet(viewsets.ModelViewSet):
    queryset = Building.objects.all()
    serializer_class = BuildingSerializer
    filterset_fields = ['university', 'is_active']
    search_fields = ['code', 'name']


class RoomTypeViewSet(viewsets.ModelViewSet):
    queryset = RoomType.objects.all()
    serializer_class = RoomTypeSerializer
    search_fields = ['code', 'name']


class RoomViewSet(viewsets.ModelViewSet):
    queryset = Room.objects.all()
    serializer_class = RoomSerializer
    filterset_fields = ['building', 'room_type', 'department', 'is_active',
                        'has_projector', 'has_ac', 'has_whiteboard', 'has_smart_board']
    search_fields = ['code', 'name', 'room_number']


class RoomAvailabilityViewSet(viewsets.ModelViewSet):
    queryset = RoomAvailability.objects.all()
    serializer_class = RoomAvailabilitySerializer
    filterset_fields = ['room', 'status', 'academic_session', 'date']
    search_fields = ['reason']


class TimeSlotViewSet(viewsets.ModelViewSet):
    queryset = TimeSlot.objects.all()
    serializer_class = TimeSlotSerializer
    filterset_fields = ['day_of_week', 'slot_type', 'is_active', 'is_friday']


class HolidayViewSet(viewsets.ModelViewSet):
    queryset = Holiday.objects.all()
    serializer_class = HolidaySerializer
    filterset_fields = ['is_recurring', 'academic_session']
    search_fields = ['name']


class AcademicCalendarViewSet(viewsets.ModelViewSet):
    queryset = AcademicCalendar.objects.all()
    serializer_class = AcademicCalendarSerializer
    filterset_fields = ['event_type', 'is_blocking', 'academic_session']
    search_fields = ['title']


class TeacherViewSet(viewsets.ModelViewSet):
    queryset = Teacher.objects.all()
    serializer_class = TeacherSerializer
    filterset_fields = ['department', 'designation', 'employment_type', 'is_active']
    search_fields = ['name', 'email', 'employee_id', 'specialization']

    @action(detail=True, methods=['get'])
    def preferences(self, request, pk=None):
        teacher = self.get_object()
        prefs = TeacherPreference.objects.filter(teacher=teacher)
        serializer = TeacherPreferenceSerializer(prefs, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def leaves(self, request, pk=None):
        teacher = self.get_object()
        leaves = TeacherLeave.objects.filter(teacher=teacher)
        serializer = TeacherLeaveSerializer(leaves, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def workload(self, request, pk=None):
        teacher = self.get_object()
        try:
            wl = TeacherWorkload.objects.get(teacher=teacher)
            serializer = TeacherWorkloadSerializer(wl)
            return Response(serializer.data)
        except TeacherWorkload.DoesNotExist:
            return Response({'detail': 'No workload record found.'}, status=404)


class TeacherPreferenceViewSet(viewsets.ModelViewSet):
    queryset = TeacherPreference.objects.all()
    serializer_class = TeacherPreferenceSerializer
    filterset_fields = ['teacher', 'academic_session', 'is_available', 'preference_level']


class InvigilationPreferenceViewSet(viewsets.ModelViewSet):
    queryset = InvigilationPreference.objects.all()
    serializer_class = InvigilationPreferenceSerializer
    filterset_fields = ['teacher', 'academic_session']


class TeacherLeaveViewSet(viewsets.ModelViewSet):
    queryset = TeacherLeave.objects.all()
    serializer_class = TeacherLeaveSerializer
    filterset_fields = ['teacher', 'academic_session', 'is_approved']


class CourseViewSet(viewsets.ModelViewSet):
    queryset = Course.objects.all()
    serializer_class = CourseSerializer
    filterset_fields = ['program', 'semester', 'course_type', 'is_active']
    search_fields = ['code', 'name']


class CourseOfferingViewSet(viewsets.ModelViewSet):
    queryset = CourseOffering.objects.all()
    serializer_class = CourseOfferingSerializer
    filterset_fields = ['course', 'academic_session', 'primary_teacher', 'status', 'requires_lab']
    search_fields = ['course__code', 'course__name', 'section_name']


class CourseOfferingGroupViewSet(viewsets.ModelViewSet):
    queryset = CourseOfferingGroup.objects.all()
    serializer_class = CourseOfferingGroupSerializer
    filterset_fields = ['course_offering', 'student_group', 'is_primary']


class ScheduleViewSet(viewsets.ModelViewSet):
    queryset = Schedule.objects.all()
    serializer_class = ScheduleSerializer
    filterset_fields = ['schedule_type', 'course_offering', 'teacher', 'room',
                        'time_slot', 'student_group', 'academic_session', 'status', 'ga_run']
    search_fields = ['course_offering__course__code', 'teacher__name', 'room__name']

    @action(detail=False, methods=['get'])
    def classes(self, request):
        qs = self.get_queryset().filter(schedule_type='class')
        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def labs(self, request):
        qs = self.get_queryset().filter(schedule_type='lab')
        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)


class ExamViewSet(viewsets.ModelViewSet):
    queryset = Exam.objects.all()
    serializer_class = ExamSerializer
    filterset_fields = ['exam_type', 'course_offering', 'room', 'academic_session', 'status']
    search_fields = ['course_offering__course__code']


class InvigilationDutyViewSet(viewsets.ModelViewSet):
    queryset = InvigilationDuty.objects.all()
    serializer_class = InvigilationDutySerializer
    filterset_fields = ['exam', 'teacher', 'role', 'status']


class GARunViewSet(viewsets.ModelViewSet):
    queryset = GARun.objects.all()
    serializer_class = GARunSerializer
    filterset_fields = ['algorithm', 'schedule_type', 'academic_session',
                        'department', 'status']
    search_fields = ['name']

    @action(detail=True, methods=['get'])
    def schedules(self, request, pk=None):
        ga_run = self.get_object()
        schedules = Schedule.objects.filter(ga_run=ga_run)
        serializer = ScheduleSerializer(schedules, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def exams(self, request, pk=None):
        ga_run = self.get_object()
        exams = Exam.objects.filter(ga_run=ga_run)
        serializer = ExamSerializer(exams, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def violations(self, request, pk=None):
        ga_run = self.get_object()
        violations = ConstraintViolation.objects.filter(ga_run=ga_run)
        serializer = ConstraintViolationSerializer(violations, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['post'], url_path='generate-course-schedule')
    def generate_course_schedule(self, request):
        """
        Runs the Course Scheduler GA synchronously and returns the resulting
        GARun + schedule count. Body: {
            "academic_session": <id>, "department": <id, optional>,
            "population_size": 60, "generations": 200, "mutation_rate": 0.05
        }
        NOTE: for a real deployment this should run as a background/Celery
        task instead of blocking the request — fine for an FYP demo dataset.
        """
        from scheduler.genetic.course_ga import CourseGAProblem

        session_id = request.data.get('academic_session')
        if not session_id:
            return Response({'detail': 'academic_session is required.'},
                             status=status.HTTP_400_BAD_REQUEST)

        population_size = int(request.data.get('population_size', 60))
        generations = int(request.data.get('generations', 200))
        mutation_rate = float(request.data.get('mutation_rate', 0.05))
        department_id = request.data.get('department')

        session = AcademicSession.objects.filter(id=session_id).first()
        if session is None:
            return Response({'detail': 'AcademicSession not found.'}, status=404)

        ga_run = GARun.objects.create(
            name=f"Course GA — {session.name}",
            algorithm='ga_simple', schedule_type='course',
            academic_session=session, department_id=department_id,
            population_size=population_size, generations=generations,
            mutation_rate=mutation_rate, status='running',
            started_at=timezone.now(), triggered_by=request.user,
        )
        try:
            department = Department.objects.filter(id=department_id).first() if department_id else None
            problem = CourseGAProblem(academic_session=session, department=department)
            result = problem.run(
                population_size=population_size, generations=generations,
                mutation_rate=mutation_rate,
            )
            schedules = problem.save_result(result, ga_run, triggered_by=request.user)
        except Exception as exc:
            ga_run.status = 'failed'
            ga_run.error_message = str(exc)
            ga_run.completed_at = timezone.now()
            ga_run.save()
            return Response({'detail': str(exc), 'ga_run': GARunSerializer(ga_run).data},
                             status=status.HTTP_400_BAD_REQUEST)

        return Response({
            'ga_run': GARunSerializer(ga_run).data,
            'schedules_created': len(schedules),
        })

    @action(detail=False, methods=['post'], url_path='generate-exam-schedule')
    def generate_exam_schedule(self, request):
        """
        Runs the Exam Scheduler GA synchronously. Body: {
            "academic_session": <id>, "exam_type": "final", "department": <id, optional>,
            "population_size": 60, "generations": 200, "mutation_rate": 0.05
        }
        """
        from scheduler.genetic.exam_ga import ExamGAProblem

        session_id = request.data.get('academic_session')
        if not session_id:
            return Response({'detail': 'academic_session is required.'},
                             status=status.HTTP_400_BAD_REQUEST)

        exam_type = request.data.get('exam_type', 'final')
        population_size = int(request.data.get('population_size', 60))
        generations = int(request.data.get('generations', 200))
        mutation_rate = float(request.data.get('mutation_rate', 0.05))
        department_id = request.data.get('department')

        session = AcademicSession.objects.filter(id=session_id).first()
        if session is None:
            return Response({'detail': 'AcademicSession not found.'}, status=404)

        ga_run = GARun.objects.create(
            name=f"Exam GA — {session.name} ({exam_type})",
            algorithm='ga_simple', schedule_type='exam',
            academic_session=session, department_id=department_id,
            population_size=population_size, generations=generations,
            mutation_rate=mutation_rate, status='running',
            started_at=timezone.now(), triggered_by=request.user,
        )
        try:
            department = Department.objects.filter(id=department_id).first() if department_id else None
            problem = ExamGAProblem(academic_session=session, exam_type=exam_type, department=department)
            result = problem.run(
                population_size=population_size, generations=generations,
                mutation_rate=mutation_rate,
            )
            exams = problem.save_result(result, ga_run)
        except Exception as exc:
            ga_run.status = 'failed'
            ga_run.error_message = str(exc)
            ga_run.completed_at = timezone.now()
            ga_run.save()
            return Response({'detail': str(exc), 'ga_run': GARunSerializer(ga_run).data},
                             status=status.HTTP_400_BAD_REQUEST)

        return Response({
            'ga_run': GARunSerializer(ga_run).data,
            'exams_created': len(exams),
        })

    @action(detail=False, methods=['post'], url_path='generate-invigilation-schedule')
    def generate_invigilation_schedule(self, request):
        """
        Runs the Invigilation Duty GA synchronously. Requires exams to already
        exist for the session (run generate-exam-schedule first). Body: {
            "academic_session": <id>, "exam_type": <optional filter>,
            "department": <id, optional>,
            "population_size": 60, "generations": 200, "mutation_rate": 0.05
        }
        """
        from scheduler.genetic.invigilation import InvigilationGAProblem

        session_id = request.data.get('academic_session')
        if not session_id:
            return Response({'detail': 'academic_session is required.'},
                             status=status.HTTP_400_BAD_REQUEST)

        exam_type = request.data.get('exam_type') or None
        population_size = int(request.data.get('population_size', 60))
        generations = int(request.data.get('generations', 200))
        mutation_rate = float(request.data.get('mutation_rate', 0.05))
        department_id = request.data.get('department')

        session = AcademicSession.objects.filter(id=session_id).first()
        if session is None:
            return Response({'detail': 'AcademicSession not found.'}, status=404)

        ga_run = GARun.objects.create(
            name=f"Invigilation GA — {session.name}",
            algorithm='ga_simple', schedule_type='invigilation',
            academic_session=session, department_id=department_id,
            population_size=population_size, generations=generations,
            mutation_rate=mutation_rate, status='running',
            started_at=timezone.now(), triggered_by=request.user,
        )
        try:
            department = Department.objects.filter(id=department_id).first() if department_id else None
            problem = InvigilationGAProblem(
                academic_session=session, exam_type=exam_type, department=department,
            )
            result = problem.run(
                population_size=population_size, generations=generations,
                mutation_rate=mutation_rate,
            )
            duties = problem.save_result(result, ga_run)
        except Exception as exc:
            ga_run.status = 'failed'
            ga_run.error_message = str(exc)
            ga_run.completed_at = timezone.now()
            ga_run.save()
            return Response({'detail': str(exc), 'ga_run': GARunSerializer(ga_run).data},
                             status=status.HTTP_400_BAD_REQUEST)

        return Response({
            'ga_run': GARunSerializer(ga_run).data,
            'duties_created': len(duties),
        })


class FairnessRecordViewSet(viewsets.ModelViewSet):
    queryset = FairnessRecord.objects.all()
    serializer_class = FairnessRecordSerializer
    filterset_fields = ['schedule', 'department']


class GlobalFairnessSnapshotViewSet(viewsets.ModelViewSet):
    queryset = GlobalFairnessSnapshot.objects.all()
    serializer_class = GlobalFairnessSnapshotSerializer
    filterset_fields = ['teacher', 'academic_session']


class TeacherWorkloadViewSet(viewsets.ModelViewSet):
    queryset = TeacherWorkload.objects.all()
    serializer_class = TeacherWorkloadSerializer
    filterset_fields = ['teacher', 'department', 'academic_session']


class StudentConflictViewSet(viewsets.ModelViewSet):
    queryset = StudentConflict.objects.all()
    serializer_class = StudentConflictSerializer
    filterset_fields = ['student_group', 'academic_session', 'conflict_type',
                        'conflict_date', 'is_resolved']


class ConstraintViolationViewSet(viewsets.ModelViewSet):
    queryset = ConstraintViolation.objects.all()
    serializer_class = ConstraintViolationSerializer
    filterset_fields = ['schedule', 'exam', 'constraint_catalog', 'severity',
                        'resolved', 'repair_iteration', 'ga_run']


class RepairHistoryViewSet(viewsets.ModelViewSet):
    queryset = RepairHistory.objects.all()
    serializer_class = RepairHistorySerializer
    filterset_fields = ['disruption_type', 'status', 'ga_run']


class LedgerViewSet(viewsets.ModelViewSet):
    queryset = Ledger.objects.all()
    serializer_class = LedgerSerializer
    filterset_fields = ['action_type', 'table_name', 'user', 'ga_run']
    search_fields = ['table_name']

    @action(detail=False, methods=['get'])
    def verify_chain(self, request):
        """Phase 10 (BlockchainProof): walk the hash chain and confirm no
        block has been tampered with directly in the database."""
        is_valid, message = Ledger.verify_chain()
        return Response({'valid': is_valid, 'message': message,
                          'block_count': Ledger.objects.count()})


class ConstraintCatalogViewSet(viewsets.ModelViewSet):
    queryset = ConstraintCatalog.objects.all()
    serializer_class = ConstraintCatalogSerializer
    filterset_fields = ['constraint_type', 'target_table', 'is_active']
    search_fields = ['constraint_name', 'error_message']


class ImportCSVView(APIView):
    """
    POST /api/import-csv/

    Wraps the `import_csv_data` management command so the whole-database
    bootstrap dataset can be uploaded from the Database admin screen instead
    of only from the CLI against a local folder.

    Body (multipart/form-data):
      - One file per entry in REQUIRED_FILES, using the exact filename as
        the field name, e.g. a field literally named "university.csv".
      - "schedule.csv" (optional) — only read when with_ground_truth=true.
      - "session" (default "Fall 2026"), "session_start" (YYYY-MM-DD),
        "session_end", "exam_start", "exam_end" — same defaults as the
        management command.
      - "wipe" ("true"/"false") and "with_ground_truth" ("true"/"false").

    Every uploaded file is staged into a throwaway temp directory (never
    written into the repo), the command runs against that directory inside
    its own @transaction.atomic block, and the temp directory is removed
    afterwards whether the import succeeded or failed.
    """
    permission_classes = [IsAdminUser]
    parser_classes = [MultiPartParser, FormParser]

    REQUIRED_FILES = [
        "university.csv", "faculties.csv", "departments.csv", "programs.csv",
        "buildings.csv", "rooms.csv", "time_slots.csv", "teachers.csv",
        "sections.csv", "courses.csv", "course_offerings.csv",
    ]

    def _truthy(self, request, key, default=False):
        raw = request.data.get(key)
        if raw is None:
            return default
        return str(raw).strip().lower() in ('1', 'true', 'yes', 'on')

    def post(self, request):
        with_ground_truth = self._truthy(request, 'with_ground_truth')

        needed = list(self.REQUIRED_FILES)
        if with_ground_truth:
            needed.append('schedule.csv')

        missing = [name for name in needed if name not in request.FILES]
        if missing:
            return Response(
                {'detail': f"Missing required CSV file(s): {', '.join(missing)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        tmpdir = tempfile.mkdtemp(prefix='chronosfair_csv_import_')
        try:
            for name in needed:
                dest = os.path.join(tmpdir, name)
                with open(dest, 'wb') as fh:
                    for chunk in request.FILES[name].chunks():
                        fh.write(chunk)

            out, err = StringIO(), StringIO()
            call_command(
                'import_csv_data',
                dir=tmpdir,
                session=request.data.get('session', 'Fall 2026'),
                session_start=request.data.get('session_start', '2026-09-01'),
                session_end=request.data.get('session_end', '2026-12-31'),
                exam_start=request.data.get('exam_start', '2026-12-08'),
                exam_end=request.data.get('exam_end', '2026-12-19'),
                wipe=self._truthy(request, 'wipe'),
                with_ground_truth=with_ground_truth,
                stdout=out, stderr=err,
            )
            return Response({
                'detail': 'Import completed.',
                'log': out.getvalue(),
                'warnings': err.getvalue(),
            })
        except CommandError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as exc:
            return Response({'detail': f'Import failed: {exc}'},
                             status=status.HTTP_400_BAD_REQUEST)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)
