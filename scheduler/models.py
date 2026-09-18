"""
ChronosFair v3.1 — Improved Database Architecture
=================================================
Complete Django ORM for AI-Based Smart Academic Scheduling
with Fair Resource Allocation, Repair Engine, and Blockchain Audit.

Schema Version: 3.1 (Improved)
Total Tables: ~33
Design: Fully normalized (3NF) with documented denormalization for performance

Hierarchy:
    University → Faculty → Department → Program → Semester (lookup)
    AcademicSession → Batch → StudentGroup (Section)
    University → Building → Room → RoomAvailability
    Course → CourseOffering → [Schedule | Exam]
    Teacher → [TeacherPreference | InvigilationPreference | TeacherWorkload | TeacherLeave]
    GARun → [Schedule | Exam | InvigilationDuty | ConstraintViolation]
    StudentConflict → fast conflict lookup cache
"""

from django.db import models
from django.db.models import Sum, F, Q, Count, Avg, UniqueConstraint
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
import hashlib
import json
from datetime import datetime, timedelta
from decimal import Decimal
from django.utils import timezone as django_timezone


# ============================================================
# 1. AUTHENTICATION & RBAC
# ============================================================

class User(AbstractUser):
    """Extended user model with RBAC roles for ChronosFair"""
    ROLE_CHOICES = [
        ('admin', 'System Administrator'),
        ('coordinator', 'Scheduling Coordinator'),
        ('dept_head', 'Department Head'),
        ('faculty', 'Faculty Member'),
        ('auditor', 'Auditor'),
        ('lab_engineer', 'Lab Engineer'),
    ]

    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='faculty')
    department = models.ForeignKey(
        'Department', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='users'
    )
    phone = models.CharField(max_length=20, blank=True, null=True)
    is_active = models.BooleanField(default=True)
    last_login_ip = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'users'
        indexes = [
            models.Index(fields=['role'], name='idx_users_role'),
            models.Index(fields=['department'], name='idx_users_dept'),
            models.Index(fields=['is_active'], name='idx_users_active'),
        ]

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"

    @property
    def is_coordinator(self):
        return self.role == 'coordinator'

    @property
    def is_admin(self):
        return self.role == 'admin'


# ============================================================
# 2. ACADEMIC HIERARCHY
# ============================================================

class University(models.Model):
    """Top-level academic institution"""
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=20, unique=True)
    location = models.CharField(max_length=200, blank=True)
    established_date = models.DateField(null=True, blank=True)
    website = models.URLField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'universities'
        ordering = ['code']
        verbose_name_plural = 'Universities'

    def __str__(self):
        return f"{self.code} — {self.name}"


class Faculty(models.Model):
    """Faculty / School within the university (e.g., Faculty of Engineering)"""
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=20, unique=True)
    university = models.ForeignKey(
        University, on_delete=models.RESTRICT, related_name='faculties'
    )
    dean = models.ForeignKey(
        'Teacher', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='faculties_dean'
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'faculties'
        ordering = ['code']
        verbose_name_plural = 'Faculties'
        constraints = [
            UniqueConstraint(fields=['university', 'code'], name='uq_faculty_univ_code')
        ]

    def __str__(self):
        return f"{self.code} — {self.name}"


class Department(models.Model):
    """Academic department (EE, CE, Math, Physics, etc.)"""
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=20, unique=True)
    faculty = models.ForeignKey(
        Faculty, on_delete=models.RESTRICT, related_name='departments'
    )
    head = models.ForeignKey(
        'Teacher', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='departments_head'
    )
    student_count = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'departments'
        ordering = ['code']
        indexes = [
            models.Index(fields=['faculty'], name='idx_dept_faculty'),
        ]

    def __str__(self):
        return f"{self.code} — {self.name}"


class Program(models.Model):
    """Academic program (BS CE, MS CE, PhD CE, etc.)"""
    DEGREE_TYPES = [
        ('bs', 'Bachelor of Science'),
        ('ms', 'Master of Science'),
        ('phd', 'Doctor of Philosophy'),
        ('diploma', 'Diploma'),
        ('certificate', 'Certificate'),
    ]

    name = models.CharField(max_length=200)
    code = models.CharField(max_length=20)
    department = models.ForeignKey(
        Department, on_delete=models.RESTRICT, related_name='programs'
    )
    degree_type = models.CharField(max_length=20, choices=DEGREE_TYPES, default='bs')
    duration_semesters = models.PositiveSmallIntegerField(default=8)
    total_credit_hours = models.PositiveSmallIntegerField(default=130)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'programs'
        ordering = ['code']
        constraints = [
            UniqueConstraint(fields=['department', 'code'], name='uq_program_dept_code')
        ]
        indexes = [
            models.Index(fields=['department'], name='idx_program_dept'),
            models.Index(fields=['degree_type'], name='idx_program_degree'),
        ]

    def __str__(self):
        return f"{self.code} ({self.get_degree_type_display()})"


class Semester(models.Model):
    """Semester lookup within a program (1st, 2nd, ..., 8th Semester)"""
    program = models.ForeignKey(
        Program, on_delete=models.CASCADE, related_name='semesters'
    )
    semester_number = models.PositiveSmallIntegerField()
    name = models.CharField(max_length=50)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'semesters'
        ordering = ['program', 'semester_number']
        constraints = [
            UniqueConstraint(fields=['program', 'semester_number'], name='uq_semester_program_num')
        ]

    def __str__(self):
        return f"{self.program.code} — Semester {self.semester_number}"


class AcademicSession(models.Model):
    """Academic session / term (Fall 2026, Spring 2027, Summer 2027)"""
    STATUS_CHOICES = [
        ('upcoming', 'Upcoming'),
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('archived', 'Archived'),
    ]

    name = models.CharField(max_length=50, unique=True)
    start_date = models.DateField()
    end_date = models.DateField()
    registration_start = models.DateField(null=True, blank=True)
    registration_end = models.DateField(null=True, blank=True)
    exam_start_date = models.DateField(null=True, blank=True)
    exam_end_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='upcoming')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'academic_sessions'
        ordering = ['-start_date']
        indexes = [
            models.Index(fields=['status'], name='idx_session_status'),
            models.Index(fields=['start_date', 'end_date'], name='idx_session_dates'),
        ]

    def __str__(self):
        return self.name

    def clean(self):
        if self.end_date <= self.start_date:
            raise ValidationError("End date must be after start date.")


class Batch(models.Model):
    """Student intake batch (e.g., BS CE Batch 2023)"""
    program = models.ForeignKey(
        Program, on_delete=models.RESTRICT, related_name='batches'
    )
    intake_session = models.ForeignKey(
        AcademicSession, on_delete=models.RESTRICT, related_name='batches'
    )
    batch_year = models.PositiveSmallIntegerField()
    name = models.CharField(max_length=50)
    current_semester = models.ForeignKey(
        Semester, on_delete=models.RESTRICT, related_name='batches'
    )
    total_students = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'batches'
        ordering = ['-batch_year']
        constraints = [
            UniqueConstraint(fields=['program', 'batch_year'], name='uq_batch_program_year')
        ]
        indexes = [
            models.Index(fields=['program'], name='idx_batch_program'),
            models.Index(fields=['intake_session'], name='idx_batch_session'),
            models.Index(fields=['current_semester'], name='idx_batch_semester'),
        ]

    def __str__(self):
        return f"{self.program.code} Batch {self.batch_year}"


class StudentGroup(models.Model):
    """Student section within a batch (e.g., Section A, B, C)"""
    batch = models.ForeignKey(
        Batch, on_delete=models.RESTRICT, related_name='student_groups'
    )
    section_name = models.CharField(max_length=20)
    size = models.PositiveIntegerField()
    representative_name = models.CharField(max_length=100, blank=True)
    representative_email = models.EmailField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'student_groups'
        ordering = ['batch', 'section_name']
        constraints = [
            UniqueConstraint(fields=['batch', 'section_name'], name='uq_group_batch_section')
        ]
        indexes = [
            models.Index(fields=['batch'], name='idx_group_batch'),
        ]

    def __str__(self):
        return f"{self.batch} — Section {self.section_name} ({self.size} students)"

    @property
    def program(self):
        return self.batch.program

    @property
    def department(self):
        return self.batch.program.department

    @property
    def current_semester_number(self):
        return self.batch.current_semester.semester_number


# ============================================================
# 3. BUILDINGS & ROOMS
# ============================================================

class Building(models.Model):
    """Physical building on campus (e.g., Building A, Building B)"""
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20, unique=True)
    university = models.ForeignKey(
        University, on_delete=models.RESTRICT, related_name='buildings'
    )
    location = models.CharField(max_length=200, blank=True)
    floors = models.PositiveSmallIntegerField(default=1)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'buildings'
        ordering = ['code']

    def __str__(self):
        return f"{self.code} — {self.name}"

    @property
    def room_count(self):
        return self.rooms.count()


class RoomType(models.Model):
    """Types of academic spaces"""
    TYPE_CHOICES = [
        ('lecture_room', 'Lecture Room'),
        ('computer_lab', 'Computer Lab'),
        ('electronics_lab', 'Electronics Lab'),
        ('physics_lab', 'Physics Lab'),
        ('chemistry_lab', 'Chemistry Lab'),
        ('mechanical_lab', 'Mechanical Lab'),
        ('civil_lab', 'Civil Lab'),
        ('exam_hall', 'Exam Hall'),
        ('seminar_room', 'Seminar Room'),
        ('auditorium', 'Auditorium'),
        ('conference_room', 'Conference Room'),
        ('library', 'Library Room'),
    ]

    code = models.CharField(max_length=30, unique=True)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    is_schedulable = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'room_types'
        ordering = ['name']

    def __str__(self):
        return self.name


class Room(models.Model):
    """Physical classrooms, labs, and halls"""
    name = models.CharField(max_length=50, unique=True)
    code = models.CharField(max_length=30, unique=True)
    room_type = models.ForeignKey(
        RoomType, on_delete=models.RESTRICT, related_name='rooms'
    )
    building = models.ForeignKey(
        Building, on_delete=models.RESTRICT, related_name='rooms'
    )
    capacity = models.PositiveIntegerField()
    exam_capacity = models.PositiveIntegerField(null=True, blank=True)
    floor = models.PositiveSmallIntegerField(default=1)
    room_number = models.CharField(max_length=20, blank=True)
    department = models.ForeignKey(
        Department, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='rooms'
    )
    has_projector = models.BooleanField(default=False)
    has_ac = models.BooleanField(default=False)
    has_whiteboard = models.BooleanField(default=False)
    has_smart_board = models.BooleanField(default=False)
    has_internet = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'rooms'
        indexes = [
            models.Index(fields=['room_type'], name='idx_room_type'),
            models.Index(fields=['capacity'], name='idx_room_capacity'),
            models.Index(fields=['building'], name='idx_room_building'),
            models.Index(fields=['department'], name='idx_room_dept'),
            models.Index(fields=['is_active'], name='idx_room_active'),
        ]

    def __str__(self):
        return f"{self.name} ({self.room_type.name}, cap: {self.capacity})"

    def get_exam_capacity(self):
        return self.exam_capacity or self.capacity


class RoomAvailability(models.Model):
    """Room availability status per date / time slot — prevents GA from booking unavailable rooms"""
    STATUS_CHOICES = [
        ('available', 'Available'),
        ('maintenance', 'Maintenance'),
        ('reserved', 'Reserved'),
        ('holiday', 'Holiday'),
        ('blocked', 'Blocked'),
    ]

    room = models.ForeignKey(
        Room, on_delete=models.CASCADE, related_name='availability_records'
    )
    date = models.DateField()
    time_slot = models.ForeignKey(
        'TimeSlot', on_delete=models.CASCADE, null=True, blank=True,
        related_name='room_availability'
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='available')
    reason = models.CharField(max_length=255, blank=True)
    academic_session = models.ForeignKey(
        AcademicSession, on_delete=models.CASCADE, null=True, blank=True,
        related_name='room_availability'
    )
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='room_availability_set'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'room_availability'
        constraints = [
            UniqueConstraint(
                fields=['room', 'date', 'time_slot'],
                name='uq_room_availability'
            )
        ]
        indexes = [
            models.Index(fields=['room', 'date'], name='idx_avail_room_date'),
            models.Index(fields=['status'], name='idx_avail_status'),
            models.Index(fields=['academic_session'], name='idx_avail_session'),
        ]

    def __str__(self):
        time_str = f" {self.time_slot}" if self.time_slot else " (all day)"
        return f"{self.room.name} — {self.date}{time_str}: {self.get_status_display()}"


# ============================================================
# 4. TIME SLOTS & CALENDAR
# ============================================================

class TimeSlot(models.Model):
    """Available scheduling periods"""
    SLOT_TYPES = [
        ('morning', 'Morning'),
        ('afternoon', 'Afternoon'),
        ('evening', 'Evening'),
    ]

    DAY_CHOICES = [(i, day) for i, day in enumerate(
        ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'], start=1
    )]

    day_of_week = models.PositiveSmallIntegerField(choices=DAY_CHOICES)
    start_time = models.TimeField()
    end_time = models.TimeField()
    slot_type = models.CharField(max_length=20, choices=SLOT_TYPES, default='morning')
    is_active = models.BooleanField(default=True)
    is_friday = models.BooleanField(default=False, help_text="True if this slot is on Friday")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'time_slots'
        constraints = [
            UniqueConstraint(fields=['day_of_week', 'start_time', 'end_time'], name='uq_time_slot')
        ]
        indexes = [
            models.Index(fields=['day_of_week'], name='idx_slot_day'),
            models.Index(fields=['slot_type'], name='idx_slot_type'),
            models.Index(fields=['is_friday'], name='idx_slot_friday'),
        ]
        ordering = ['day_of_week', 'start_time']

    def __str__(self):
        return f"{self.get_day_of_week_display()} {self.start_time.strftime('%H:%M')}-{self.end_time.strftime('%H:%M')}"

    def save(self, *args, **kwargs):
        self.is_friday = (self.day_of_week == 5)
        super().save(*args, **kwargs)

    def duration_minutes(self):
        from datetime import datetime
        start = datetime.combine(datetime.today(), self.start_time)
        end = datetime.combine(datetime.today(), self.end_time)
        return int((end - start).total_seconds() / 60)


class Holiday(models.Model):
    """Holiday calendar — GA will skip these dates"""
    name = models.CharField(max_length=100)
    holiday_date = models.DateField()
    reason = models.TextField(blank=True)
    is_recurring = models.BooleanField(
        default=False, help_text="True if this holiday repeats annually"
    )
    academic_session = models.ForeignKey(
        AcademicSession, on_delete=models.CASCADE, null=True, blank=True,
        related_name='holidays'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'holidays'
        ordering = ['holiday_date']
        constraints = [
            UniqueConstraint(
                fields=['holiday_date', 'academic_session'],
                name='uq_holiday_date_session'
            )
        ]
        indexes = [
            models.Index(fields=['holiday_date'], name='idx_holiday_date'),
            models.Index(fields=['is_recurring'], name='idx_holiday_recurring'),
        ]

    def __str__(self):
        return f"{self.name} ({self.holiday_date})"


class AcademicCalendar(models.Model):
    """Academic calendar events — defines scheduling boundaries for GA"""
    EVENT_TYPES = [
        ('semester_start', 'Semester Start'),
        ('semester_end', 'Semester End'),
        ('classes_start', 'Classes Start'),
        ('classes_end', 'Classes End'),
        ('exam_week_start', 'Exam Week Start'),
        ('exam_week_end', 'Exam Week End'),
        ('registration_week_start', 'Registration Week Start'),
        ('registration_week_end', 'Registration Week End'),
        ('add_drop_start', 'Add/Drop Start'),
        ('add_drop_end', 'Add/Drop End'),
        ('break_start', 'Break Start'),
        ('break_end', 'Break End'),
        ('custom', 'Custom Event'),
    ]

    academic_session = models.ForeignKey(
        AcademicSession, on_delete=models.CASCADE, related_name='calendar_events'
    )
    event_type = models.CharField(max_length=30, choices=EVENT_TYPES)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    is_blocking = models.BooleanField(
        default=True, help_text="If True, GA will not schedule during this period"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'academic_calendar'
        ordering = ['start_date']
        indexes = [
            models.Index(fields=['academic_session', 'event_type'], name='idx_cal_session_event'),
            models.Index(fields=['start_date', 'end_date'], name='idx_cal_dates'),
            models.Index(fields=['is_blocking'], name='idx_cal_blocking'),
        ]

    def __str__(self):
        return f"{self.title} ({self.start_date})"

    def clean(self):
        if self.end_date and self.end_date < self.start_date:
            raise ValidationError("End date must be after start date.")


# ============================================================
# 5. TEACHERS, PREFERENCES & LEAVES
# ============================================================

class Teacher(models.Model):
    """Faculty profiles with workload constraints"""
    DESIGNATION_CHOICES = [
        ('professor', 'Professor'),
        ('associate_professor', 'Associate Professor'),
        ('assistant_professor', 'Assistant Professor'),
        ('lecturer', 'Lecturer'),
        ('lab_engineer', 'Lab Engineer'),
        ('visiting_faculty', 'Visiting Faculty'),
        ('research_associate', 'Research Associate'),
    ]

    EMPLOYMENT_TYPES = [
        ('full_time', 'Full Time'),
        ('part_time', 'Part Time'),
        ('contract', 'Contract'),
        ('visiting', 'Visiting'),
    ]

    user = models.OneToOneField(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='teacher_profile'
    )
    employee_id = models.CharField(max_length=30, unique=True, blank=True, null=True)
    name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=20, blank=True)
    department = models.ForeignKey(
        Department, on_delete=models.RESTRICT, related_name='teachers'
    )
    designation = models.CharField(max_length=30, choices=DESIGNATION_CHOICES, default='lecturer')
    employment_type = models.CharField(max_length=20, choices=EMPLOYMENT_TYPES, default='full_time')
    max_teaching_hours = models.PositiveSmallIntegerField(default=18)
    max_lab_hours = models.PositiveSmallIntegerField(default=6)
    max_invigilation_hours = models.PositiveSmallIntegerField(default=20)
    max_consecutive_invigilation = models.PositiveSmallIntegerField(default=2)
    join_date = models.DateField(null=True, blank=True)
    specialization = models.CharField(max_length=200, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'teachers'
        indexes = [
            models.Index(fields=['department'], name='idx_teacher_dept'),
            models.Index(fields=['designation'], name='idx_teacher_designation'),
            models.Index(fields=['employment_type'], name='idx_teacher_emp_type'),
            models.Index(fields=['is_active'], name='idx_teacher_active'),
        ]

    def __str__(self):
        return f"{self.name} ({self.department.code})"

    @property
    def current_workload(self):
        try:
            return self.workload.combined_workload
        except TeacherWorkload.DoesNotExist:
            return 0.0

    def can_teach_labs(self):
        return self.designation in ['lab_engineer', 'assistant_professor', 'associate_professor', 'professor']


class TeacherPreference(models.Model):
    """Teacher availability and preferences per time slot — replaces JSON preferences"""
    teacher = models.ForeignKey(
        Teacher, on_delete=models.CASCADE, related_name='preferences'
    )
    academic_session = models.ForeignKey(
        AcademicSession, on_delete=models.CASCADE, related_name='teacher_preferences'
    )
    day_of_week = models.PositiveSmallIntegerField(choices=TimeSlot.DAY_CHOICES)
    time_slot = models.ForeignKey(
        TimeSlot, on_delete=models.CASCADE, related_name='teacher_preferences'
    )
    is_available = models.BooleanField(default=True)
    preference_level = models.PositiveSmallIntegerField(
        default=5, help_text="1=Strongly Avoid, 10=Strongly Prefer"
    )
    reason = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'teacher_preferences'
        constraints = [
            UniqueConstraint(
                fields=['teacher', 'academic_session', 'time_slot'],
                name='uq_teacher_pref_session_slot'
            )
        ]
        indexes = [
            models.Index(fields=['teacher', 'academic_session'], name='idx_pref_teacher_session'),
            models.Index(fields=['day_of_week'], name='idx_pref_day'),
            models.Index(fields=['is_available'], name='idx_pref_available'),
            models.Index(fields=['preference_level'], name='idx_pref_level'),
        ]

    def __str__(self):
        status = "Available" if self.is_available else "Unavailable"
        return f"{self.teacher.name} — {self.time_slot} — {status} (P:{self.preference_level})"


class InvigilationPreference(models.Model):
    """Teacher preferences for exam invigilation duties"""
    teacher = models.ForeignKey(
        Teacher, on_delete=models.CASCADE, related_name='invigilation_preferences'
    )
    academic_session = models.ForeignKey(
        AcademicSession, on_delete=models.CASCADE, related_name='invigilation_preferences'
    )
    max_per_week = models.PositiveSmallIntegerField(default=5)
    max_per_day = models.PositiveSmallIntegerField(default=2)
    no_consecutive_days = models.BooleanField(default=False)
    preferred_weekdays = models.JSONField(default=list, blank=True, help_text="[1,2,3,4,5] for Mon-Fri")
    unavailable_dates = models.JSONField(default=list, blank=True, help_text="['2026-12-15', '2022026-12-16']")
    preferred_rooms = models.ManyToManyField(
        Room, blank=True, related_name='invigilator_preferences'
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'invigilation_preferences'
        constraints = [
            UniqueConstraint(
                fields=['teacher', 'academic_session'],
                name='uq_invig_pref_teacher_session'
            )
        ]
        indexes = [
            models.Index(fields=['teacher', 'academic_session'], name='idx_invig_pref_teacher_session'),
        ]

    def __str__(self):
        return f"{self.teacher.name} — Max {self.max_per_week}/week, {self.max_per_day}/day"


class TeacherLeave(models.Model):
    """Teacher leave records — critical input for Repair GA"""
    teacher = models.ForeignKey(
        Teacher, on_delete=models.CASCADE, related_name='leaves'
    )
    academic_session = models.ForeignKey(
        AcademicSession, on_delete=models.CASCADE, null=True, blank=True,
        related_name='teacher_leaves'
    )
    start_date = models.DateField()
    end_date = models.DateField()
    reason = models.CharField(max_length=255, blank=True)
    is_approved = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'teacher_leaves'
        indexes = [
            models.Index(fields=['teacher', 'start_date', 'end_date'], name='idx_leave_teacher_dates'),
            models.Index(fields=['is_approved'], name='idx_leave_approved'),
            models.Index(fields=['academic_session'], name='idx_leave_session'),
        ]

    def __str__(self):
        return f"{self.teacher.name}: {self.start_date} to {self.end_date}"

    def clean(self):
        if self.end_date < self.start_date:
            raise ValidationError("End date must be after start date.")


# ============================================================
# 6. COURSES & OFFERINGS
# ============================================================

class Course(models.Model):
    """Course catalog — master reference for all courses"""
    COURSE_TYPES = [
        ('theory', 'Theory Only'),
        ('lab', 'Lab Only'),
        ('theory_lab', 'Theory + Lab'),
        ('project', 'Project'),
        ('thesis', 'Thesis'),
        ('seminar', 'Seminar'),
    ]

    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=200)
    program = models.ForeignKey(
        Program, on_delete=models.RESTRICT, related_name='courses'
    )
    semester = models.ForeignKey(
        Semester, on_delete=models.RESTRICT, related_name='courses',
        help_text="Which semester of the program this course belongs to"
    )
    credit_hours = models.PositiveSmallIntegerField()
    theory_hours = models.PositiveSmallIntegerField(default=0)
    lab_hours = models.PositiveSmallIntegerField(default=0)
    weekly_hours = models.PositiveSmallIntegerField()
    course_type = models.CharField(max_length=20, choices=COURSE_TYPES, default='theory')
    room_type_required = models.ForeignKey(
        RoomType, on_delete=models.RESTRICT, related_name='courses',
        help_text="Preferred room type for theory classes"
    )
    lab_room_type_required = models.ForeignKey(
        RoomType, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='lab_courses',
        help_text="Required room type for lab sessions"
    )
    max_students_per_section = models.PositiveSmallIntegerField(default=50)
    is_active = models.BooleanField(default=True)
    description = models.TextField(blank=True)
    prerequisites = models.ManyToManyField(
        'self', symmetrical=False, blank=True, related_name='prerequisite_for'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'courses'
        indexes = [
            models.Index(fields=['program'], name='idx_course_program'),
            models.Index(fields=['semester'], name='idx_course_semester'),
            models.Index(fields=['course_type'], name='idx_course_type'),
            models.Index(fields=['is_active'], name='idx_course_active'),
        ]

    def __str__(self):
        return f"{self.code}: {self.name}"

    def has_lab_component(self):
        return self.course_type in ['lab', 'theory_lab']

    def total_contact_hours(self):
        return self.theory_hours + self.lab_hours


class CourseOffering(models.Model):
    """Specific offering of a course in an academic session
    
    THIS is what the GA schedules, not Course.
    Example: CE-337 offered in Fall 2026, Section A, taught by Prof. Khan
    """
    STATUS_CHOICES = [
        ('planned', 'Planned'),
        ('confirmed', 'Confirmed'),
        ('scheduling', 'In Scheduling'),
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]

    course = models.ForeignKey(
        Course, on_delete=models.RESTRICT, related_name='offerings'
    )
    academic_session = models.ForeignKey(
        AcademicSession, on_delete=models.RESTRICT, related_name='course_offerings'
    )
    primary_teacher = models.ForeignKey(
        Teacher, on_delete=models.RESTRICT, related_name='primary_offerings',
        help_text="Main instructor for theory"
    )
    lab_teacher = models.ForeignKey(
        Teacher, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='lab_offerings',
        help_text="Lab instructor (if different from primary)"
    )
    section_name = models.CharField(max_length=20, default='A')
    max_students = models.PositiveSmallIntegerField(default=50)
    current_enrollment = models.PositiveSmallIntegerField(default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='planned')
    requires_lab = models.BooleanField(default=False)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'course_offerings'
        constraints = [
            UniqueConstraint(
                fields=['course', 'academic_session', 'section_name'],
                name='uq_offering_course_session_section'
            )
        ]
        indexes = [
            models.Index(fields=['course'], name='idx_offering_course'),
            models.Index(fields=['academic_session'], name='idx_offering_session'),
            models.Index(fields=['primary_teacher'], name='idx_offering_teacher'),
            models.Index(fields=['status'], name='idx_offering_status'),
        ]

    def __str__(self):
        return f"{self.course.code} — {self.academic_session.name} — Sec {self.section_name}"

    def clean(self):
        if self.requires_lab and not self.course.has_lab_component():
            raise ValidationError("This course does not have a lab component.")
        if self.lab_teacher and not self.lab_teacher.can_teach_labs():
            raise ValidationError("Selected lab instructor is not qualified to teach labs.")


class CourseOfferingGroup(models.Model):
    """Links course offerings to student groups (sections that attend together)"""
    course_offering = models.ForeignKey(
        CourseOffering, on_delete=models.CASCADE, related_name='student_groups'
    )
    student_group = models.ForeignKey(
        StudentGroup, on_delete=models.CASCADE, related_name='course_offerings'
    )
    is_primary = models.BooleanField(default=True, help_text="True if this is the home section")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'course_offering_groups'
        constraints = [
            UniqueConstraint(
                fields=['course_offering', 'student_group'],
                name='uq_offering_group'
            )
        ]
        indexes = [
            models.Index(fields=['course_offering'], name='idx_offergroup_offering'),
            models.Index(fields=['student_group'], name='idx_offergroup_group'),
        ]

    def __str__(self):
        return f"{self.course_offering} <- {self.student_group}"


# ============================================================
# 7. SCHEDULING TABLES (Core of the System)
# ============================================================

class Schedule(models.Model):
    """Unified timetable entries for BOTH theory classes and labs — scheduled by GA"""
    SCHEDULE_TYPES = [
        ('class', 'Class'),
        ('lab', 'Lab'),
    ]
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('repairing', 'Under Repair'),
        ('archived', 'Archived'),
    ]

    schedule_type = models.CharField(max_length=10, choices=SCHEDULE_TYPES, default='class')
    course_offering = models.ForeignKey(
        CourseOffering, on_delete=models.RESTRICT, related_name='schedules'
    )
    teacher = models.ForeignKey(
        Teacher, on_delete=models.RESTRICT, related_name='schedules'
    )
    room = models.ForeignKey(
        Room, on_delete=models.RESTRICT, related_name='schedules'
    )
    time_slot = models.ForeignKey(
        TimeSlot, on_delete=models.RESTRICT, related_name='schedules'
    )
    student_group = models.ForeignKey(
        StudentGroup, on_delete=models.RESTRICT, related_name='schedules'
    )
    academic_session = models.ForeignKey(
        AcademicSession, on_delete=models.RESTRICT, related_name='schedules'
    )
    lab_batch = models.CharField(max_length=20, blank=True, help_text="Lab batch if groups are split")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    generated_by_ga = models.BooleanField(default=False)
    ga_run = models.ForeignKey(
        'GARun', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='schedules'
    )
    fitness_score = models.DecimalField(max_digits=5, decimal_places=4, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'schedules'
        constraints = [
            UniqueConstraint(
                fields=['room', 'time_slot', 'academic_session'],
                name='uq_sched_room_time_session',
                violation_error_message="Room is already booked at this time."
            ),
            UniqueConstraint(
                fields=['teacher', 'time_slot', 'academic_session'],
                name='uq_sched_teacher_time_session',
                violation_error_message="Teacher is already assigned at this time."
            ),
            UniqueConstraint(
                fields=['student_group', 'time_slot', 'academic_session'],
                name='uq_sched_group_time_session',
                violation_error_message="Student group already has a class at this time."
            ),
        ]
        indexes = [
            models.Index(fields=['schedule_type'], name='idx_sched_type'),
            models.Index(fields=['course_offering'], name='idx_sched_offering'),
            models.Index(fields=['teacher'], name='idx_sched_teacher'),
            models.Index(fields=['room'], name='idx_sched_room'),
            models.Index(fields=['time_slot'], name='idx_sched_slot'),
            models.Index(fields=['academic_session'], name='idx_sched_session'),
            models.Index(fields=['status'], name='idx_sched_status'),
            models.Index(fields=['ga_run'], name='idx_sched_ga_run'),
        ]

    def __str__(self):
        prefix = "LAB" if self.schedule_type == 'lab' else "CLASS"
        return f"{prefix}: {self.course_offering.course.code} | {self.teacher.name} | {self.room.name} | {self.time_slot}"

    def clean(self):
        course = self.course_offering.course

        if self.schedule_type == 'class':
            if self.room.room_type != course.room_type_required:
                raise ValidationError(
                    f"Room type mismatch: {self.room.room_type.name} != {course.room_type_required.name}"
                )
            if self.teacher.department != course.program.department:
                if self.teacher.employment_type != 'visiting':
                    raise ValidationError(
                        f"Teacher {self.teacher.name} is not from the course department."
                    )
        else:  # lab
            if not course.has_lab_component():
                raise ValidationError("This course does not have a lab component.")
            if self.room.room_type != course.lab_room_type_required:
                raise ValidationError(
                    f"Lab room type mismatch: {self.room.room_type.name} != {course.lab_room_type_required.name}"
                )
            if not self.teacher.can_teach_labs():
                raise ValidationError(f"Teacher {self.teacher.name} is not qualified to teach labs.")

        if self.lab_batch and self.schedule_type != 'lab':
            raise ValidationError("Lab batch is only applicable to lab schedules.")

        # Common validation
        if self.room.capacity < self.student_group.size:
            raise ValidationError(
                f"Room capacity ({self.room.capacity}) < Group size ({self.student_group.size})"
            )


class Exam(models.Model):
    """Scheduled examinations"""
    EXAM_TYPES = [
        ('mid_term', 'Mid Term'),
        ('final', 'Final'),
        ('quiz', 'Quiz'),
        ('lab_exam', 'Lab Exam'),
        ('presentation', 'Presentation'),
        ('viva', 'Viva Voce'),
    ]

    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('repairing', 'Under Repair'),
        ('archived', 'Archived'),
    ]

    course_offering = models.ForeignKey(
        CourseOffering, on_delete=models.RESTRICT, related_name='exams'
    )
    exam_type = models.CharField(max_length=20, choices=EXAM_TYPES, default='mid_term')
    academic_session = models.ForeignKey(
        AcademicSession, on_delete=models.RESTRICT, related_name='exams'
    )
    room = models.ForeignKey(
        Room, on_delete=models.RESTRICT, related_name='exams'
    )
    time_slot = models.ForeignKey(
        TimeSlot, on_delete=models.RESTRICT, related_name='exams'
    )
    exam_date = models.DateField()
    duration_minutes = models.PositiveSmallIntegerField()
    max_marks = models.PositiveSmallIntegerField(default=100)
    passing_marks = models.PositiveSmallIntegerField(default=40)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    generated_by_ga = models.BooleanField(default=False)
    ga_run = models.ForeignKey(
        'GARun', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='exams'
    )
    fitness_score = models.DecimalField(max_digits=5, decimal_places=4, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'exams'
        constraints = [
            UniqueConstraint(
                fields=['room', 'exam_date', 'time_slot'],
                name='uq_exam_room_date_slot'
            ),
        ]
        indexes = [
            models.Index(fields=['course_offering'], name='idx_exam_offering'),
            models.Index(fields=['exam_type'], name='idx_exam_type'),
            models.Index(fields=['room'], name='idx_exam_room'),
            models.Index(fields=['exam_date'], name='idx_exam_date'),
            models.Index(fields=['academic_session'], name='idx_exam_session'),
            models.Index(fields=['status'], name='idx_exam_status'),
            models.Index(fields=['ga_run'], name='idx_exam_ga_run'),
        ]

    def __str__(self):
        return f"{self.get_exam_type_display()}: {self.course_offering.course.code} on {self.exam_date}"

    def clean(self):
        if self.exam_date < self.academic_session.start_date or self.exam_date > self.academic_session.end_date:
            raise ValidationError("Exam date must be within the academic session dates.")
        if self.duration_minutes > 180:
            raise ValidationError("Exam duration cannot exceed 180 minutes (3 hours).")


class InvigilationDuty(models.Model):
    """Faculty assigned to supervise exams"""
    ROLE_CHOICES = [
        ('head_invigilator', 'Head Invigilator'),
        ('invigilator', 'Invigilator'),
        ('relief', 'Relief'),
        ('supervisor', 'Supervisor'),
        ('coordinator', 'Exam Coordinator'),
    ]

    STATUS_CHOICES = [
        ('assigned', 'Assigned'),
        ('confirmed', 'Confirmed'),
        ('replaced', 'Replaced'),
        ('declined', 'Declined'),
    ]

    exam = models.ForeignKey(
        Exam, on_delete=models.RESTRICT, related_name='invigilation_duties'
    )
    teacher = models.ForeignKey(
        Teacher, on_delete=models.RESTRICT, related_name='invigilation_duties'
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='invigilator')
    hours = models.DecimalField(max_digits=4, decimal_places=2, default=2.00)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='assigned')
    ga_run = models.ForeignKey(
        'GARun', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='invigilation_duties'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'invigilation_duties'
        constraints = [
            UniqueConstraint(fields=['exam', 'teacher'], name='uq_invig_exam_teacher')
        ]
        indexes = [
            models.Index(fields=['exam'], name='idx_invig_exam'),
            models.Index(fields=['teacher'], name='idx_invig_teacher'),
            models.Index(fields=['role'], name='idx_invig_role'),
            models.Index(fields=['status'], name='idx_invig_status'),
            models.Index(fields=['ga_run'], name='idx_invig_ga_run'),
        ]

    def __str__(self):
        return f"{self.teacher.name} -> {self.exam} ({self.role})"


# ============================================================
# 8. GENETIC ALGORITHM ENGINE
# ============================================================

class GARun(models.Model):
    """Tracks every GA execution — invaluable for analysis, debugging, and FYP results"""
    ALGORITHM_CHOICES = [
        ('nsga2', 'NSGA-II'),
        ('nsga3', 'NSGA-III'),
        ('moead', 'MOEA/D'),
        ('spea2', 'SPEA2'),
        ('ga_simple', 'Simple GA'),
        ('ga_adaptive', 'Adaptive GA'),
        ('repair_ga', 'Repair GA'),
    ]

    STATUS_CHOICES = [
        ('queued', 'Queued'),
        ('running', 'Running'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]

    SCHEDULE_TYPES = [
        ('course', 'Course Scheduling'),
        ('lab', 'Lab Scheduling'),
        ('exam', 'Exam Scheduling'),
        ('invigilation', 'Invigilation Scheduling'),
        ('combined', 'Combined Scheduling'),
    ]

    name = models.CharField(max_length=100)
    algorithm = models.CharField(max_length=20, choices=ALGORITHM_CHOICES, default='nsga2')
    schedule_type = models.CharField(max_length=20, choices=SCHEDULE_TYPES, default='course')
    academic_session = models.ForeignKey(
        AcademicSession, on_delete=models.RESTRICT, related_name='ga_runs'
    )
    department = models.ForeignKey(
        Department, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='ga_runs'
    )

    # GA Parameters
    population_size = models.PositiveIntegerField(default=100)
    generations = models.PositiveIntegerField(default=500)
    mutation_rate = models.DecimalField(max_digits=5, decimal_places=4, default=0.05)
    crossover_rate = models.DecimalField(max_digits=5, decimal_places=4, default=0.80)
    elitism_count = models.PositiveIntegerField(default=5)
    tournament_size = models.PositiveSmallIntegerField(default=3)
    convergence_threshold = models.DecimalField(max_digits=5, decimal_places=4, default=0.001)

    # Fitness Results
    fitness_best = models.DecimalField(max_digits=5, decimal_places=4, null=True, blank=True)
    fitness_avg = models.DecimalField(max_digits=5, decimal_places=4, null=True, blank=True)
    fitness_worst = models.DecimalField(max_digits=5, decimal_places=4, null=True, blank=True)
    fairness_score_before = models.DecimalField(max_digits=5, decimal_places=4, null=True, blank=True)
    fairness_score_after = models.DecimalField(max_digits=5, decimal_places=4, null=True, blank=True)
    jain_index = models.DecimalField(max_digits=5, decimal_places=4, null=True, blank=True)

    # Performance Metrics
    execution_time_ms = models.PositiveIntegerField(null=True, blank=True)
    memory_peak_mb = models.PositiveIntegerField(null=True, blank=True)
    cpu_time_ms = models.PositiveIntegerField(null=True, blank=True)
    convergence_generation = models.PositiveIntegerField(null=True, blank=True)

    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='queued')
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    log_output = models.TextField(blank=True)

    # Metadata
    triggered_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='ga_runs'
    )
    parameters_json = models.JSONField(default=dict, blank=True, help_text="Additional GA parameters")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'ga_runs'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['algorithm'], name='idx_ga_algorithm'),
            models.Index(fields=['schedule_type'], name='idx_ga_schedule_type'),
            models.Index(fields=['academic_session'], name='idx_ga_session'),
            models.Index(fields=['department'], name='idx_ga_dept'),
            models.Index(fields=['status'], name='idx_ga_status'),
            models.Index(fields=['created_at'], name='idx_ga_created'),
        ]

    def __str__(self):
        return f"GA Run #{self.id}: {self.name} ({self.get_algorithm_display()})"

    def duration_seconds(self):
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None


# ============================================================
# 9. FAIRNESS & ANALYTICS
# ============================================================

class FairnessRecord(models.Model):
    """Per-schedule, per-department fairness metrics"""
    schedule = models.ForeignKey(
        Schedule, on_delete=models.RESTRICT, related_name='fairness_records'
    )
    department = models.ForeignKey(
        Department, on_delete=models.RESTRICT, related_name='fairness_records'
    )
    total_hours = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    per_student_hours = models.DecimalField(max_digits=8, decimal_places=4, default=0)
    fairness_score = models.DecimalField(max_digits=5, decimal_places=4, default=0)
    calculated_at = models.DateTimeField(auto_now_add=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'fairness_records'
        indexes = [
            models.Index(fields=['schedule'], name='idx_fair_sched'),
            models.Index(fields=['department'], name='idx_fair_dept'),
        ]

    def __str__(self):
        return f"Fairness: {self.department.code} = {self.fairness_score}"


class GlobalFairnessSnapshot(models.Model):
    """Point-in-time JFI and workload per teacher"""
    teacher = models.ForeignKey(
        Teacher, on_delete=models.RESTRICT, related_name='fairness_snapshots'
    )
    schedule = models.ForeignKey(
        Schedule, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='fairness_snapshots'
    )
    academic_session = models.ForeignKey(
        AcademicSession, on_delete=models.RESTRICT, related_name='fairness_snapshots'
    )
    teaching_hours = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    lab_hours = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    exam_hours = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    invigilation_hours = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    combined_workload = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    jain_index = models.DecimalField(max_digits=5, decimal_places=4, default=0)
    snapshot_at = models.DateTimeField(auto_now_add=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'global_fairness_snapshots'
        indexes = [
            models.Index(fields=['teacher'], name='idx_gfs_teacher'),
            models.Index(fields=['academic_session'], name='idx_gfs_session'),
            models.Index(fields=['snapshot_at'], name='idx_gfs_snapshot_at'),
        ]

    def __str__(self):
        return f"JFI Snapshot: {self.teacher.name} = {self.jain_index}"


class TeacherWorkload(models.Model):
    """Real-time aggregated workload per teacher"""
    teacher = models.OneToOneField(
        Teacher, on_delete=models.RESTRICT, related_name='workload'
    )
    department = models.ForeignKey(Department, on_delete=models.RESTRICT)
    academic_session = models.ForeignKey(
        AcademicSession, on_delete=models.RESTRICT, related_name='teacher_workloads'
    )
    teaching_hours = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    lab_hours = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    exam_hours = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    invigilation_hours = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    combined_workload = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    overload_score = models.DecimalField(max_digits=5, decimal_places=4, default=0)
    calculated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'teacher_workload'
        constraints = [
            UniqueConstraint(fields=['teacher', 'academic_session'], name='uq_workload_teacher_session')
        ]
        indexes = [
            models.Index(fields=['teacher'], name='idx_workload_teacher'),
            models.Index(fields=['department'], name='idx_workload_dept'),
            models.Index(fields=['academic_session'], name='idx_workload_session'),
        ]

    def calculate_overload(self):
        max_hours = self.teacher.max_teaching_hours + self.teacher.max_lab_hours
        if max_hours > 0:
            self.overload_score = max(0, (self.combined_workload - max_hours) / max_hours)
        return self.overload_score

    def recalculate(self):
        session = self.academic_session
        self.teaching_hours = Schedule.objects.filter(
            teacher=self.teacher, academic_session=session, status='active', schedule_type='class'
        ).aggregate(total=models.Sum('course_offering__course__theory_hours'))['total'] or 0

        self.lab_hours = Schedule.objects.filter(
            teacher=self.teacher, academic_session=session, status='active', schedule_type='lab'
        ).aggregate(total=models.Sum('course_offering__course__lab_hours'))['total'] or 0

        self.invigilation_hours = InvigilationDuty.objects.filter(
            teacher=self.teacher, exam__academic_session=session, status='confirmed'
        ).aggregate(total=models.Sum('hours'))['total'] or 0

        self.combined_workload = (
            self.teaching_hours +
            self.lab_hours * Decimal('0.8') +
            self.exam_hours * Decimal('0.5') +
            self.invigilation_hours * Decimal('0.5')
        )
        self.calculate_overload()
        self.save()


# ============================================================
# 10. STUDENT CONFLICTS (Fast Lookup Cache)
# ============================================================

class StudentConflict(models.Model):
    """Pre-computed conflict cache for fast GA validation and Repair module"""
    CONFLICT_TYPES = [
        ('exam_exam', 'Exam-Exam'),
        ('class_class', 'Class-Class'),
        ('exam_class', 'Exam-Class'),
        ('lab_lab', 'Lab-Lab'),
        ('class_lab', 'Class-Lab'),
    ]

    student_group = models.ForeignKey(
        StudentGroup, on_delete=models.CASCADE, related_name='conflicts'
    )
    academic_session = models.ForeignKey(
        AcademicSession, on_delete=models.CASCADE, related_name='student_conflicts'
    )
    conflict_type = models.CharField(max_length=20, choices=CONFLICT_TYPES)

    first_schedule = models.ForeignKey(
        Schedule, on_delete=models.CASCADE, related_name='first_conflicts',
        null=True, blank=True
    )
    second_schedule = models.ForeignKey(
        Schedule, on_delete=models.CASCADE, related_name='second_conflicts',
        null=True, blank=True
    )
    first_exam = models.ForeignKey(
        Exam, on_delete=models.CASCADE, related_name='first_exam_conflicts',
        null=True, blank=True
    )
    second_exam = models.ForeignKey(
        Exam, on_delete=models.CASCADE, related_name='second_exam_conflicts',
        null=True, blank=True
    )

    conflict_date = models.DateField()
    time_slot = models.ForeignKey(
        TimeSlot, on_delete=models.CASCADE, related_name='student_conflicts',
        null=True, blank=True
    )
    description = models.CharField(max_length=255, blank=True)
    is_resolved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'student_conflicts'
        indexes = [
            models.Index(fields=['student_group', 'academic_session'], name='idx_conflict_group_session'),
            models.Index(fields=['conflict_date'], name='idx_conflict_date'),
            models.Index(fields=['is_resolved'], name='idx_conflict_resolved'),
            models.Index(fields=['conflict_type'], name='idx_conflict_type'),
        ]

    def __str__(self):
        return f"Conflict #{self.id}: {self.student_group} — {self.conflict_type} on {self.conflict_date}"

    def clean(self):
        has_schedule_pair = self.first_schedule and self.second_schedule
        has_exam_pair = self.first_exam and self.second_exam
        has_mixed = (self.first_schedule and self.second_exam) or (self.first_exam and self.second_schedule)

        if not any([has_schedule_pair, has_exam_pair, has_mixed]):
            raise ValidationError("A conflict must involve at least two scheduled items.")

    def get_conflicting_items(self):
        """Returns a tuple of the two conflicting items"""
        if self.first_schedule and self.second_schedule:
            return (self.first_schedule, self.second_schedule)
        elif self.first_exam and self.second_exam:
            return (self.first_exam, self.second_exam)
        elif self.first_schedule and self.second_exam:
            return (self.first_schedule, self.second_exam)
        elif self.first_exam and self.second_schedule:
            return (self.first_exam, self.second_schedule)
        return (None, None)


# ============================================================
# 11. CONSTRAINT VIOLATIONS (GA Analysis & Repair)
# ============================================================

class ConstraintViolation(models.Model):
    """Every violated constraint is stored here — extremely useful for Repair, analysis, and research"""
    SEVERITY_CHOICES = [
        ('critical', 'Critical'),
        ('high', 'High'),
        ('medium', 'Medium'),
        ('low', 'Low'),
    ]

    schedule = models.ForeignKey(
        Schedule, on_delete=models.CASCADE, related_name='constraint_violations',
        null=True, blank=True
    )
    exam = models.ForeignKey(
        Exam, on_delete=models.CASCADE, related_name='constraint_violations',
        null=True, blank=True
    )
    invigilation = models.ForeignKey(
        InvigilationDuty, on_delete=models.CASCADE, related_name='constraint_violations',
        null=True, blank=True
    )
    constraint_catalog = models.ForeignKey(
        'ConstraintCatalog', on_delete=models.CASCADE, related_name='violations'
    )
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES, default='medium')
    fitness_penalty = models.DecimalField(max_digits=8, decimal_places=4, default=0)
    description = models.TextField(blank=True)
    resolved = models.BooleanField(default=False)
    repair_iteration = models.PositiveIntegerField(default=0)
    ga_run = models.ForeignKey(
        GARun, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='constraint_violations'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'constraint_violations'
        indexes = [
            models.Index(fields=['schedule', 'resolved'], name='idx_cv_sched_resolved'),
            models.Index(fields=['exam', 'resolved'], name='idx_cv_exam_resolved'),
            models.Index(fields=['constraint_catalog'], name='idx_cv_constraint'),
            models.Index(fields=['severity'], name='idx_cv_severity'),
            models.Index(fields=['ga_run'], name='idx_cv_ga_run'),
            models.Index(fields=['repair_iteration'], name='idx_cv_repair_iter'),
        ]

    def __str__(self):
        target = self.schedule or self.exam or self.invigilation
        return f"Violation #{self.id}: {self.constraint_catalog.constraint_name} on {target} ({self.severity})"


# ============================================================
# 12. REPAIR ENGINE
# ============================================================

class RepairHistory(models.Model):
    """Log of all disruption repairs with stability/fairness metrics"""
    DISRUPTION_TYPES = [
        ('teacher_absence', 'Teacher Absence'),
        ('room_unavailable', 'Room Unavailable'),
        ('time_conflict', 'Time Conflict'),
        ('fairness_violation', 'Fairness Violation'),
        ('priority_conflict', 'Priority Conflict'),
        ('manual_override', 'Manual Override'),
        ('lab_equipment_failure', 'Lab Equipment Failure'),
        ('student_group_merge', 'Student Group Merge'),
        ('ga_failure', 'GA Failure'),
    ]

    STATUS_CHOICES = [
        ('success', 'Success'),
        ('failed', 'Failed'),
        ('rolled_back', 'Rolled Back'),
        ('partial', 'Partial Success'),
    ]

    original_schedule = models.ForeignKey(
        Schedule, on_delete=models.RESTRICT, related_name='repair_original',
        null=True, blank=True
    )
    repaired_schedule = models.ForeignKey(
        Schedule, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='repair_result'
    )
    disruption_type = models.CharField(max_length=30, choices=DISRUPTION_TYPES)
    stability_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    fairness_before = models.DecimalField(max_digits=5, decimal_places=4, default=0)
    fairness_after = models.DecimalField(max_digits=5, decimal_places=4, default=0)
    repair_time_ms = models.PositiveIntegerField(default=0)
    action_taken = models.JSONField(default=dict, blank=True)
    triggered_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='repairs_triggered'
    )
    ga_run = models.ForeignKey(
        GARun, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='repairs'
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='success')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'repair_history'
        indexes = [
            models.Index(fields=['original_schedule'], name='idx_repair_orig_sched'),
            models.Index(fields=['disruption_type'], name='idx_repair_type'),
            models.Index(fields=['status'], name='idx_repair_status'),
            models.Index(fields=['ga_run'], name='idx_repair_ga_run'),
            models.Index(fields=['created_at'], name='idx_repair_created'),
        ]

    def __str__(self):
        return f"Repair #{self.id}: {self.disruption_type} ({self.status})"


# ============================================================
# 13. BLOCKCHAIN AUDIT LEDGER
# ============================================================

class Ledger(models.Model):
    """Tamper-evident audit log using SHA-256 hash chaining"""
    ACTION_TYPES = [
        ('CREATE', 'Create'),
        ('UPDATE', 'Update'),
        ('DELETE', 'Delete'),
        ('REPAIR', 'Repair'),
        ('PRIORITY_RESOLUTION', 'Priority Resolution'),
        ('FAIRNESS_CHECK', 'Fairness Check'),
        ('GENERATION', 'Schedule Generation'),
        ('ROLLBACK', 'Rollback'),
        ('GA_RUN', 'GA Execution'),
    ]

    block_number = models.PositiveIntegerField(unique=True)
    timestamp = models.DateTimeField()
    action_type = models.CharField(max_length=30, choices=ACTION_TYPES)
    table_name = models.CharField(max_length=50)
    record_id = models.PositiveIntegerField()
    data_hash = models.CharField(max_length=64)
    previous_hash = models.CharField(max_length=64)
    current_hash = models.CharField(max_length=64, unique=True)
    user = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='ledger_entries'
    )
    ga_run = models.ForeignKey(
        GARun, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='ledger_entries'
    )
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'ledger'
        indexes = [
            models.Index(fields=['block_number'], name='idx_ledger_block'),
            models.Index(fields=['action_type'], name='idx_ledger_action'),
            models.Index(fields=['table_name'], name='idx_ledger_table'),
            models.Index(fields=['timestamp'], name='idx_ledger_timestamp'),
            models.Index(fields=['user'], name='idx_ledger_user'),
            models.Index(fields=['ga_run'], name='idx_ledger_ga_run'),
        ]
        ordering = ['block_number']

    def __str__(self):
        return f"Block #{self.block_number}: {self.action_type} on {self.table_name}"

    def verify_hash(self):
        combined = f"{self.previous_hash}{self.data_hash}{self.timestamp.isoformat()}"
        expected = hashlib.sha256(combined.encode()).hexdigest()
        return self.current_hash == expected

    @classmethod
    def get_next_block_number(cls):
        last = cls.objects.order_by('-block_number').first()
        return (last.block_number + 1) if last else 1

    @classmethod
    def get_previous_hash(cls):
        last = cls.objects.order_by('-block_number').first()
        return last.current_hash if last else '0' * 64

    @classmethod
    def create_block(cls, action, table, record_id, data_dict, user=None, ga_run=None):
        block_num = cls.get_next_block_number()
        prev_hash = cls.get_previous_hash()
        timestamp = django_timezone.now()

        data_string = json.dumps(data_dict, sort_keys=True, separators=(',', ':'))
        data_hash = hashlib.sha256(data_string.encode()).hexdigest()

        combined = f"{prev_hash}{data_hash}{timestamp.isoformat()}"
        current_hash = hashlib.sha256(combined.encode()).hexdigest()

        return cls.objects.create(
            block_number=block_num,
            timestamp=timestamp,
            action_type=action,
            table_name=table,
            record_id=record_id,
            data_hash=data_hash,
            previous_hash=prev_hash,
            current_hash=current_hash,
            user=user,
            ga_run=ga_run,
            metadata={'source': 'auto_log'}
        )

    @classmethod
    def verify_chain(cls):
        blocks = cls.objects.order_by('block_number')
        prev_hash = '0' * 64

        for block in blocks:
            if block.previous_hash != prev_hash:
                return False, f"Chain broken at block {block.block_number}"
            if not block.verify_hash():
                return False, f"Tampering detected at block {block.block_number}"
            prev_hash = block.current_hash

        return True, "Chain verified successfully"


# ============================================================
# 14. CONSTRAINTS CATALOG (Dynamic Rule Engine)
# ============================================================

class ConstraintCatalog(models.Model):
    """Dynamic constraint definitions for all three GA engines"""
    CONSTRAINT_TYPES = [
        ('hard', 'Hard Constraint'),
        ('soft', 'Soft Constraint'),
        ('priority', 'Priority Rule'),
        ('preference', 'Preference Rule'),
    ]

    TARGET_TABLES = [
        ('schedules', 'Schedule'),
        ('exams', 'Exam'),
        ('invigilation_duties', 'Invigilation Duty'),
        ('teachers', 'Teacher'),
        ('rooms', 'Room'),
        ('time_slots', 'Time Slot'),
    ]

    constraint_name = models.CharField(max_length=100)
    constraint_type = models.CharField(max_length=20, choices=CONSTRAINT_TYPES, default='hard')
    target_table = models.CharField(max_length=30, choices=TARGET_TABLES)
    target_column = models.CharField(max_length=50, blank=True, null=True)
    rule_definition = models.JSONField(help_text="JSON rule for GA validation engine")
    error_message = models.CharField(max_length=255, default='Constraint violation detected')
    weight = models.DecimalField(max_digits=5, decimal_places=4, default=1.0, help_text="Penalty weight for soft constraints")
    is_active = models.BooleanField(default=True)
    priority = models.PositiveSmallIntegerField(default=100, help_text="Lower = higher priority")
    applies_to_session = models.ForeignKey(
        AcademicSession, on_delete=models.CASCADE, null=True, blank=True,
        related_name='constraints',
        help_text="NULL = applies to all sessions"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'constraints_catalog'
        indexes = [
            models.Index(fields=['constraint_type'], name='idx_constraint_type'),
            models.Index(fields=['target_table'], name='idx_constraint_table'),
            models.Index(fields=['is_active'], name='idx_constraint_active'),
            models.Index(fields=['priority'], name='idx_constraint_priority'),
        ]

    def __str__(self):
        return f"{self.constraint_name} ({self.constraint_type})"


# ============================================================
# 15. DJANGO SIGNALS (Auto-update workload & ledger)
# ============================================================

@receiver(post_save, sender=Schedule)
def update_teacher_workload_on_schedule(sender, instance, created, **kwargs):
    if created:
        workload, _ = TeacherWorkload.objects.get_or_create(
            teacher=instance.teacher,
            academic_session=instance.academic_session,
            defaults={'department': instance.teacher.department}
        )
        if instance.schedule_type == 'class':
            workload.teaching_hours += instance.course_offering.course.theory_hours
        elif instance.schedule_type == 'lab':
            workload.lab_hours += instance.course_offering.course.lab_hours
        workload.combined_workload = (
            workload.teaching_hours +
            workload.lab_hours * Decimal('0.8') +
            workload.exam_hours * Decimal('0.5') +
            workload.invigilation_hours * Decimal('0.5')
        )
        workload.calculate_overload()
        workload.save()

        # NOTE: the Ledger entry for this row is written explicitly by the
        # GA's save_result() (see genetic/course_ga.py, exam_ga.py,
        # invigilation.py) rather than here. That path knows which user
        # triggered the GA run (ga_run.triggered_by) and writes one block
        # per created Schedule/Exam/InvigilationDuty row uniformly across
        # all three engines — doing it here too would double-log every
        # schedule and couldn't attribute a user.


@receiver(post_save, sender=InvigilationDuty)
def update_teacher_workload_on_invigilation(sender, instance, created, **kwargs):
    if created:
        workload, _ = TeacherWorkload.objects.get_or_create(
            teacher=instance.teacher,
            academic_session=instance.exam.academic_session,
            defaults={'department': instance.teacher.department}
        )
        workload.invigilation_hours += instance.hours
        workload.combined_workload = (
            workload.teaching_hours +
            workload.lab_hours * Decimal('0.8') +
            workload.exam_hours * Decimal('0.5') +
            workload.invigilation_hours * Decimal('0.5')
        )
        workload.calculate_overload()
        workload.save()


@receiver(post_delete, sender=Schedule)
def log_schedule_deletion(sender, instance, **kwargs):
    Ledger.create_block(
        action='DELETE',
        table='schedules',
        record_id=instance.id,
        data_dict={
            'deleted_schedule': instance.id,
            'schedule_type': instance.schedule_type,
            'course': instance.course_offering.course.code,
            'academic_session': instance.academic_session.name
        }
    )


# ============================================================
# 16. CUSTOM MANAGERS
# ============================================================

class ScheduleManager(models.Manager):
    def active_for_session(self, academic_session_id):
        return self.filter(academic_session_id=academic_session_id, status='active')

    def classes_for_session(self, academic_session_id):
        return self.filter(academic_session_id=academic_session_id, status='active', schedule_type='class')

    def labs_for_session(self, academic_session_id):
        return self.filter(academic_session_id=academic_session_id, status='active', schedule_type='lab')

    def conflicts_for_teacher(self, teacher_id, time_slot_id, academic_session_id):
        return self.filter(
            teacher_id=teacher_id,
            time_slot_id=time_slot_id,
            academic_session_id=academic_session_id
        )

    def department_schedule(self, department_id, academic_session_id):
        return self.filter(
            course_offering__course__program__department_id=department_id,
            academic_session_id=academic_session_id
        ).select_related(
            'course_offering__course',
            'teacher',
            'room',
            'time_slot',
            'student_group'
        )

    def by_ga_run(self, ga_run_id):
        return self.filter(ga_run_id=ga_run_id).select_related(
            'course_offering', 'teacher', 'room', 'time_slot'
        )


class ExamManager(models.Manager):
    def exams_for_student_group(self, group_id, academic_session_id):
        course_offering_ids = CourseOfferingGroup.objects.filter(
            student_group_id=group_id
        ).values_list('course_offering_id', flat=True)
        return self.filter(
            course_offering_id__in=course_offering_ids,
            academic_session_id=academic_session_id
        )

    def by_ga_run(self, ga_run_id):
        return self.filter(ga_run_id=ga_run_id).select_related(
            'course_offering', 'room', 'time_slot'
        )


class GARunManager(models.Manager):
    def successful_runs(self, academic_session_id=None):
        qs = self.filter(status='completed')
        if academic_session_id:
            qs = qs.filter(academic_session_id=academic_session_id)
        return qs.order_by('-fitness_best')

    def best_run_for_session(self, academic_session_id, schedule_type='course'):
        return self.filter(
            academic_session_id=academic_session_id,
            schedule_type=schedule_type,
            status='completed'
        ).order_by('-fitness_best').first()


# Attach custom managers
Schedule.objects = ScheduleManager()
Schedule.objects.model = Schedule

Exam.objects = ExamManager()
Exam.objects.model = Exam

GARun.objects = GARunManager()
GARun.objects.model = GARun
