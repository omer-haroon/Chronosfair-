from rest_framework import serializers
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


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'role',
                  'department', 'phone', 'is_active', 'last_login', 'created_at']
        read_only_fields = ['last_login', 'created_at']


class UniversitySerializer(serializers.ModelSerializer):
    class Meta:
        model = University
        fields = '__all__'


class FacultySerializer(serializers.ModelSerializer):
    university_name = serializers.CharField(source='university.name', read_only=True)
    dean_name = serializers.CharField(source='dean.name', read_only=True, default=None)

    class Meta:
        model = Faculty
        fields = '__all__'


class DepartmentSerializer(serializers.ModelSerializer):
    faculty_name = serializers.CharField(source='faculty.name', read_only=True)
    head_name = serializers.CharField(source='head.name', read_only=True, default=None)

    class Meta:
        model = Department
        fields = '__all__'


class ProgramSerializer(serializers.ModelSerializer):
    department_name = serializers.CharField(source='department.name', read_only=True)

    class Meta:
        model = Program
        fields = '__all__'


class SemesterSerializer(serializers.ModelSerializer):
    program_name = serializers.CharField(source='program.name', read_only=True)

    class Meta:
        model = Semester
        fields = '__all__'


class AcademicSessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = AcademicSession
        fields = '__all__'


class BatchSerializer(serializers.ModelSerializer):
    program_name = serializers.CharField(source='program.name', read_only=True)
    intake_session_name = serializers.CharField(source='intake_session.name', read_only=True)

    class Meta:
        model = Batch
        fields = '__all__'


class StudentGroupSerializer(serializers.ModelSerializer):
    batch_name = serializers.CharField(source='batch.name', read_only=True)

    class Meta:
        model = StudentGroup
        fields = '__all__'


class BuildingSerializer(serializers.ModelSerializer):
    university_name = serializers.CharField(source='university.name', read_only=True)
    room_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Building
        fields = '__all__'


class RoomTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = RoomType
        fields = '__all__'


class RoomSerializer(serializers.ModelSerializer):
    building_name = serializers.CharField(source='building.name', read_only=True)
    room_type_name = serializers.CharField(source='room_type.name', read_only=True)
    department_name = serializers.CharField(source='department.name', read_only=True, default=None)

    class Meta:
        model = Room
        fields = '__all__'


class RoomAvailabilitySerializer(serializers.ModelSerializer):
    room_name = serializers.CharField(source='room.name', read_only=True)
    time_slot_str = serializers.CharField(source='time_slot.__str__', read_only=True, default=None)

    class Meta:
        model = RoomAvailability
        fields = '__all__'


class TimeSlotSerializer(serializers.ModelSerializer):
    class Meta:
        model = TimeSlot
        fields = '__all__'


class HolidaySerializer(serializers.ModelSerializer):
    class Meta:
        model = Holiday
        fields = '__all__'


class AcademicCalendarSerializer(serializers.ModelSerializer):
    academic_session_name = serializers.CharField(source='academic_session.name', read_only=True)

    class Meta:
        model = AcademicCalendar
        fields = '__all__'


class TeacherSerializer(serializers.ModelSerializer):
    department_name = serializers.CharField(source='department.name', read_only=True)
    current_workload = serializers.FloatField(read_only=True)

    class Meta:
        model = Teacher
        fields = '__all__'


class TeacherPreferenceSerializer(serializers.ModelSerializer):
    teacher_name = serializers.CharField(source='teacher.name', read_only=True)
    time_slot_str = serializers.CharField(source='time_slot.__str__', read_only=True)

    class Meta:
        model = TeacherPreference
        fields = '__all__'


class InvigilationPreferenceSerializer(serializers.ModelSerializer):
    teacher_name = serializers.CharField(source='teacher.name', read_only=True)

    class Meta:
        model = InvigilationPreference
        fields = '__all__'


class TeacherLeaveSerializer(serializers.ModelSerializer):
    teacher_name = serializers.CharField(source='teacher.name', read_only=True)

    class Meta:
        model = TeacherLeave
        fields = '__all__'


class CourseSerializer(serializers.ModelSerializer):
    program_name = serializers.CharField(source='program.name', read_only=True)
    semester_name = serializers.CharField(source='semester.name', read_only=True)
    room_type_name = serializers.CharField(source='room_type_required.name', read_only=True)
    lab_room_type_name = serializers.CharField(source='lab_room_type_required.name', read_only=True, default=None)

    class Meta:
        model = Course
        fields = '__all__'


class CourseOfferingSerializer(serializers.ModelSerializer):
    course_code = serializers.CharField(source='course.code', read_only=True)
    course_name = serializers.CharField(source='course.name', read_only=True)
    academic_session_name = serializers.CharField(source='academic_session.name', read_only=True)
    primary_teacher_name = serializers.CharField(source='primary_teacher.name', read_only=True)
    lab_teacher_name = serializers.CharField(source='lab_teacher.name', read_only=True, default=None)

    class Meta:
        model = CourseOffering
        fields = '__all__'


class CourseOfferingGroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = CourseOfferingGroup
        fields = '__all__'


class ScheduleSerializer(serializers.ModelSerializer):
    course_code = serializers.CharField(source='course_offering.course.code', read_only=True)
    teacher_name = serializers.CharField(source='teacher.name', read_only=True)
    room_name = serializers.CharField(source='room.name', read_only=True)
    time_slot_str = serializers.CharField(source='time_slot.__str__', read_only=True)
    student_group_name = serializers.CharField(source='student_group.__str__', read_only=True)
    academic_session_name = serializers.CharField(source='academic_session.name', read_only=True)

    class Meta:
        model = Schedule
        fields = '__all__'


class ExamSerializer(serializers.ModelSerializer):
    course_code = serializers.CharField(source='course_offering.course.code', read_only=True)
    room_name = serializers.CharField(source='room.name', read_only=True)
    time_slot_str = serializers.CharField(source='time_slot.__str__', read_only=True)

    class Meta:
        model = Exam
        fields = '__all__'


class InvigilationDutySerializer(serializers.ModelSerializer):
    teacher_name = serializers.CharField(source='teacher.name', read_only=True)
    exam_str = serializers.CharField(source='exam.__str__', read_only=True)

    class Meta:
        model = InvigilationDuty
        fields = '__all__'


class GARunSerializer(serializers.ModelSerializer):
    academic_session_name = serializers.CharField(source='academic_session.name', read_only=True)
    triggered_by_username = serializers.CharField(source='triggered_by.username', read_only=True, default=None)

    class Meta:
        model = GARun
        fields = '__all__'
        read_only_fields = ['fitness_best', 'fitness_avg', 'fitness_worst',
                           'fairness_score_before', 'fairness_score_after',
                           'jain_index', 'execution_time_ms', 'memory_peak_mb',
                           'cpu_time_ms', 'convergence_generation', 'started_at',
                           'completed_at', 'error_message', 'log_output']


class FairnessRecordSerializer(serializers.ModelSerializer):
    department_code = serializers.CharField(source='department.code', read_only=True)

    class Meta:
        model = FairnessRecord
        fields = '__all__'


class GlobalFairnessSnapshotSerializer(serializers.ModelSerializer):
    teacher_name = serializers.CharField(source='teacher.name', read_only=True)

    class Meta:
        model = GlobalFairnessSnapshot
        fields = '__all__'


class TeacherWorkloadSerializer(serializers.ModelSerializer):
    teacher_name = serializers.CharField(source='teacher.name', read_only=True)

    class Meta:
        model = TeacherWorkload
        fields = '__all__'
        read_only_fields = ['calculated_at']


class StudentConflictSerializer(serializers.ModelSerializer):
    student_group_name = serializers.CharField(source='student_group.__str__', read_only=True)

    class Meta:
        model = StudentConflict
        fields = '__all__'


class ConstraintViolationSerializer(serializers.ModelSerializer):
    constraint_name = serializers.CharField(source='constraint_catalog.constraint_name', read_only=True)

    class Meta:
        model = ConstraintViolation
        fields = '__all__'


class RepairHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = RepairHistory
        fields = '__all__'


class LedgerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ledger
        fields = '__all__'
        read_only_fields = ['block_number', 'timestamp', 'data_hash',
                           'previous_hash', 'current_hash']


class ConstraintCatalogSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConstraintCatalog
        fields = '__all__'
