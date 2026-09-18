from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
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


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('username', 'email', 'role', 'department', 'is_active', 'last_login')
    list_filter = ('role', 'is_active', 'department')
    search_fields = ('username', 'email', 'first_name', 'last_name')
    fieldsets = BaseUserAdmin.fieldsets + (
        ('ChronosFair', {'fields': ('role', 'department', 'phone', 'last_login_ip')}),
    )


@admin.register(University)
class UniversityAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'location', 'is_active')
    search_fields = ('code', 'name')
    list_filter = ('is_active',)


@admin.register(Faculty)
class FacultyAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'university', 'dean', 'is_active')
    list_filter = ('university', 'is_active')
    search_fields = ('code', 'name')
    autocomplete_fields = ('dean',)


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'faculty', 'head', 'student_count', 'is_active')
    list_filter = ('faculty', 'is_active')
    search_fields = ('code', 'name')
    autocomplete_fields = ('head',)


@admin.register(Program)
class ProgramAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'department', 'degree_type', 'duration_semesters', 'is_active')
    list_filter = ('department', 'degree_type', 'is_active')
    search_fields = ('code', 'name')


@admin.register(Semester)
class SemesterAdmin(admin.ModelAdmin):
    list_display = ('program', 'semester_number', 'name', 'is_active')
    list_filter = ('program', 'is_active')
    ordering = ('program', 'semester_number')


@admin.register(AcademicSession)
class AcademicSessionAdmin(admin.ModelAdmin):
    list_display = ('name', 'start_date', 'end_date', 'status', 'is_active')
    list_filter = ('status', 'is_active')
    date_hierarchy = 'start_date'
    search_fields = ('name',)


@admin.register(Batch)
class BatchAdmin(admin.ModelAdmin):
    list_display = ('program', 'batch_year', 'name', 'current_semester', 'total_students', 'is_active')
    list_filter = ('program', 'is_active')
    search_fields = ('name', 'batch_year')


@admin.register(StudentGroup)
class StudentGroupAdmin(admin.ModelAdmin):
    list_display = ('batch', 'section_name', 'size', 'is_active')
    list_filter = ('batch__program', 'is_active')
    search_fields = ('section_name', 'batch__name')


@admin.register(Building)
class BuildingAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'university', 'floors', 'room_count', 'is_active')
    list_filter = ('university', 'is_active')
    search_fields = ('code', 'name')


@admin.register(RoomType)
class RoomTypeAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'is_schedulable')
    search_fields = ('code', 'name')


@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'building', 'room_type', 'capacity', 'floor', 'department', 'is_active')
    list_filter = ('building', 'room_type', 'department', 'is_active', 'has_projector', 'has_ac')
    search_fields = ('code', 'name', 'room_number')
    autocomplete_fields = ('department',)


@admin.register(RoomAvailability)
class RoomAvailabilityAdmin(admin.ModelAdmin):
    list_display = ('room', 'date', 'time_slot', 'status', 'reason', 'academic_session')
    list_filter = ('status', 'academic_session', 'room__building')
    date_hierarchy = 'date'
    search_fields = ('room__name', 'reason')
    autocomplete_fields = ('room', 'time_slot', 'academic_session')


@admin.register(TimeSlot)
class TimeSlotAdmin(admin.ModelAdmin):
    list_display = ('day_of_week', 'start_time', 'end_time', 'slot_type', 'is_active', 'is_friday')
    list_filter = ('day_of_week', 'slot_type', 'is_active', 'is_friday')
    ordering = ('day_of_week', 'start_time')
    search_fields = ['id']

@admin.register(Holiday)
class HolidayAdmin(admin.ModelAdmin):
    list_display = ('name', 'holiday_date', 'is_recurring', 'academic_session')
    list_filter = ('is_recurring', 'academic_session')
    date_hierarchy = 'holiday_date'
    search_fields = ('name',)


@admin.register(AcademicCalendar)
class AcademicCalendarAdmin(admin.ModelAdmin):
    list_display = ('title', 'event_type', 'start_date', 'end_date', 'is_blocking', 'academic_session')
    list_filter = ('event_type', 'is_blocking', 'academic_session')
    date_hierarchy = 'start_date'
    search_fields = ('title',)


@admin.register(Teacher)
class TeacherAdmin(admin.ModelAdmin):
    list_display = ('employee_id', 'name', 'department', 'designation', 'employment_type', 'is_active')
    list_filter = ('department', 'designation', 'employment_type', 'is_active')
    search_fields = ('name', 'email', 'employee_id', 'specialization')
    autocomplete_fields = ('user', 'department')


@admin.register(TeacherPreference)
class TeacherPreferenceAdmin(admin.ModelAdmin):
    list_display = ('teacher', 'academic_session', 'time_slot', 'is_available', 'preference_level')
    list_filter = ('is_available', 'preference_level', 'academic_session', 'day_of_week')
    search_fields = ('teacher__name',)
    autocomplete_fields = ('teacher', 'time_slot', 'academic_session')


@admin.register(InvigilationPreference)
class InvigilationPreferenceAdmin(admin.ModelAdmin):
    list_display = ('teacher', 'academic_session', 'max_per_week', 'max_per_day', 'no_consecutive_days')
    list_filter = ('academic_session', 'no_consecutive_days')
    search_fields = ('teacher__name',)
    filter_horizontal = ('preferred_rooms',)
    autocomplete_fields = ('teacher', 'academic_session')


@admin.register(TeacherLeave)
class TeacherLeaveAdmin(admin.ModelAdmin):
    list_display = ('teacher', 'start_date', 'end_date', 'is_approved', 'academic_session')
    list_filter = ('is_approved', 'academic_session')
    date_hierarchy = 'start_date'
    search_fields = ('teacher__name', 'reason')
    autocomplete_fields = ('teacher', 'academic_session')


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'program', 'semester', 'course_type', 'credit_hours', 'weekly_hours', 'is_active')
    list_filter = ('program', 'course_type', 'is_active', 'semester')
    search_fields = ('code', 'name')
    filter_horizontal = ('prerequisites',)


@admin.register(CourseOffering)
class CourseOfferingAdmin(admin.ModelAdmin):
    list_display = ('course', 'academic_session', 'section_name', 'primary_teacher', 'lab_teacher', 'status', 'requires_lab')
    list_filter = ('academic_session', 'status', 'requires_lab')
    search_fields = ('course__code', 'course__name', 'section_name')
    autocomplete_fields = ('course', 'primary_teacher', 'lab_teacher', 'academic_session')


@admin.register(CourseOfferingGroup)
class CourseOfferingGroupAdmin(admin.ModelAdmin):
    list_display = ('course_offering', 'student_group', 'is_primary')
    list_filter = ('is_primary',)
    autocomplete_fields = ('course_offering', 'student_group')


@admin.register(Schedule)
class ScheduleAdmin(admin.ModelAdmin):
    list_display = ('schedule_type', 'course_offering', 'teacher', 'room', 'time_slot', 'student_group', 'status', 'ga_run')
    list_filter = ('schedule_type', 'status', 'academic_session', 'generated_by_ga')
    search_fields = ('course_offering__course__code', 'teacher__name', 'room__name')
    autocomplete_fields = ('course_offering', 'teacher', 'room', 'time_slot', 'student_group', 'academic_session', 'ga_run')
    date_hierarchy = 'created_at'


@admin.register(Exam)
class ExamAdmin(admin.ModelAdmin):
    list_display = ('exam_type', 'course_offering', 'exam_date', 'room', 'time_slot', 'duration_minutes', 'status')
    list_filter = ('exam_type', 'status', 'academic_session')
    date_hierarchy = 'exam_date'
    search_fields = ('course_offering__course__code',)
    autocomplete_fields = ('course_offering', 'room', 'time_slot', 'academic_session', 'ga_run')


@admin.register(InvigilationDuty)
class InvigilationDutyAdmin(admin.ModelAdmin):
    list_display = ('exam', 'teacher', 'role', 'hours', 'status')
    list_filter = ('role', 'status')
    search_fields = ('teacher__name', 'exam__course_offering__course__code')
    autocomplete_fields = ('exam', 'teacher', 'ga_run')


@admin.register(GARun)
class GARunAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'algorithm', 'schedule_type', 'academic_session', 'status', 'fitness_best', 'started_at')
    list_filter = ('algorithm', 'schedule_type', 'status', 'academic_session')
    search_fields = ('name',)
    readonly_fields = ('duration_seconds',)
    date_hierarchy = 'created_at'


@admin.register(FairnessRecord)
class FairnessRecordAdmin(admin.ModelAdmin):
    list_display = ('schedule', 'department', 'fairness_score', 'calculated_at')
    list_filter = ('department',)
    autocomplete_fields = ('schedule', 'department')


@admin.register(GlobalFairnessSnapshot)
class GlobalFairnessSnapshotAdmin(admin.ModelAdmin):
    list_display = ('teacher', 'academic_session', 'combined_workload', 'jain_index', 'snapshot_at')
    list_filter = ('academic_session',)
    autocomplete_fields = ('teacher', 'schedule', 'academic_session')


@admin.register(TeacherWorkload)
class TeacherWorkloadAdmin(admin.ModelAdmin):
    list_display = ('teacher', 'department', 'academic_session', 'combined_workload', 'overload_score', 'calculated_at')
    list_filter = ('department', 'academic_session')
    readonly_fields = ('calculated_at',)
    autocomplete_fields = ('teacher', 'department', 'academic_session')


@admin.register(StudentConflict)
class StudentConflictAdmin(admin.ModelAdmin):
    list_display = ('student_group', 'conflict_type', 'conflict_date', 'time_slot', 'is_resolved')
    list_filter = ('conflict_type', 'is_resolved', 'academic_session')
    date_hierarchy = 'conflict_date'
    autocomplete_fields = ('student_group', 'academic_session', 'first_schedule', 'second_schedule', 'first_exam', 'second_exam', 'time_slot')


@admin.register(ConstraintViolation)
class ConstraintViolationAdmin(admin.ModelAdmin):
    list_display = ('id', 'constraint_catalog', 'severity', 'fitness_penalty', 'resolved', 'repair_iteration', 'ga_run')
    list_filter = ('severity', 'resolved', 'repair_iteration', 'ga_run')
    search_fields = ('description',)
    autocomplete_fields = ('schedule', 'exam', 'invigilation', 'constraint_catalog', 'ga_run')


@admin.register(RepairHistory)
class RepairHistoryAdmin(admin.ModelAdmin):
    list_display = ('id', 'disruption_type', 'status', 'stability_percent', 'fairness_before', 'fairness_after', 'repair_time_ms', 'created_at')
    list_filter = ('disruption_type', 'status')
    date_hierarchy = 'created_at'
    autocomplete_fields = ('original_schedule', 'repaired_schedule', 'triggered_by', 'ga_run')


@admin.register(Ledger)
class LedgerAdmin(admin.ModelAdmin):
    list_display = ('block_number', 'action_type', 'table_name', 'record_id', 'timestamp', 'user', 'ga_run')
    list_filter = ('action_type', 'table_name')
    search_fields = ('table_name', 'record_id')
    readonly_fields = ('block_number', 'timestamp', 'data_hash', 'previous_hash', 'current_hash')
    date_hierarchy = 'timestamp'


@admin.register(ConstraintCatalog)
class ConstraintCatalogAdmin(admin.ModelAdmin):
    list_display = ('constraint_name', 'constraint_type', 'target_table', 'priority', 'weight', 'is_active')
    list_filter = ('constraint_type', 'target_table', 'is_active')
    search_fields = ('constraint_name', 'error_message')
    autocomplete_fields = ('applies_to_session',)
