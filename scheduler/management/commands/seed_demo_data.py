import datetime
import random

from django.core.management.base import BaseCommand
from django.db import transaction

from scheduler.models import (
    University, Faculty, Department, Program, Semester, AcademicSession,
    Batch, StudentGroup, Building, RoomType, Room, TimeSlot, Teacher,
    Course, CourseOffering, CourseOfferingGroup, ConstraintCatalog,
)


class Command(BaseCommand):
    help = "Seed a small, realistic dataset so the Course/Exam/Invigilation GAs have something to schedule."

    @transaction.atomic
    def handle(self, *args, **options):
        rng = random.Random(42)

        university, _ = University.objects.get_or_create(
            code='AU', defaults={'name': 'Air University', 'location': 'Islamabad'}
        )
        faculty, _ = Faculty.objects.get_or_create(
            code='ENG', university=university, defaults={'name': 'Faculty of Engineering'}
        )
        dept_ce, _ = Department.objects.get_or_create(
            code='CE', faculty=faculty, defaults={'name': 'Computer Engineering'}
        )
        dept_ee, _ = Department.objects.get_or_create(
            code='EE', faculty=faculty, defaults={'name': 'Electrical Engineering'}
        )

        prog_ce, _ = Program.objects.get_or_create(
            code='BSCE', department=dept_ce, defaults={'name': 'BS Computer Engineering'}
        )
        prog_ee, _ = Program.objects.get_or_create(
            code='BSEE', department=dept_ee, defaults={'name': 'BS Electrical Engineering'}
        )

        semesters = {}
        for prog in (prog_ce, prog_ee):
            sem, _ = Semester.objects.get_or_create(
                program=prog, semester_number=5, defaults={'name': '5th Semester'}
            )
            semesters[prog.code] = sem

        session, _ = AcademicSession.objects.get_or_create(
            name='Fall 2026',
            defaults=dict(
                start_date=datetime.date(2026, 9, 1),
                end_date=datetime.date(2026, 12, 31),
                exam_start_date=datetime.date(2026, 12, 8),
                exam_end_date=datetime.date(2026, 12, 19),
                status='active',
            ),
        )

        batches = {}
        for prog in (prog_ce, prog_ee):
            batch, _ = Batch.objects.get_or_create(
                program=prog, batch_year=2023,
                defaults=dict(name=f"{prog.code} 2023", intake_session=session,
                              current_semester=semesters[prog.code], total_students=90)
            )
            batches[prog.code] = batch

        groups = {}
        for prog_code, batch in batches.items():
            for section in ('A', 'B'):
                group, _ = StudentGroup.objects.get_or_create(
                    batch=batch, section_name=section, defaults={'size': 45}
                )
                groups.setdefault(prog_code, []).append(group)

        building, _ = Building.objects.get_or_create(
            code='BLK-A', university=university, defaults={'name': 'Block A', 'floors': 3}
        )

        rt_lecture, _ = RoomType.objects.get_or_create(
            code='LECTURE', defaults={'name': 'Lecture Room'}
        )
        rt_lab, _ = RoomType.objects.get_or_create(
            code='COMP_LAB', defaults={'name': 'Computer Lab'}
        )

        rooms = []
        for i in range(1, 5):
            r, _ = Room.objects.get_or_create(
                code=f'A-{100+i}', defaults=dict(
                    name=f'Room A-{100+i}', room_type=rt_lecture, building=building,
                    capacity=60, has_projector=True,
                )
            )
            rooms.append(r)
        for i in range(1, 3):
            r, _ = Room.objects.get_or_create(
                code=f'LAB-{i}', defaults=dict(
                    name=f'Computer Lab {i}', room_type=rt_lab, building=building,
                    capacity=45, has_projector=True,
                )
            )
            rooms.append(r)

        # 5 days x 4 slots/day = 20 time slots
        slot_times = [
            (datetime.time(8, 30), datetime.time(9, 50)),
            (datetime.time(10, 0), datetime.time(11, 20)),
            (datetime.time(11, 30), datetime.time(12, 50)),
            (datetime.time(14, 0), datetime.time(15, 20)),
        ]
        for day in range(1, 6):  # Mon-Fri
            for start, end in slot_times:
                TimeSlot.objects.get_or_create(
                    day_of_week=day, start_time=start, end_time=end,
                    defaults={'slot_type': 'morning' if start.hour < 12 else 'afternoon'},
                )

        designations = ['assistant_professor', 'associate_professor', 'lecturer', 'professor']
        teachers = []
        for i in range(1, 9):
            dept = dept_ce if i <= 5 else dept_ee
            t, _ = Teacher.objects.get_or_create(
                email=f'teacher{i}@au.edu.pk',
                defaults=dict(
                    name=f'Dr. Faculty {i}', department=dept,
                    designation=rng.choice(designations),
                    max_teaching_hours=18,
                )
            )
            teachers.append(t)

        course_catalog = [
            ('CE-301', 'Data Structures', 'theory_lab', dept_ce, prog_ce),
            ('CE-302', 'Computer Architecture', 'theory', dept_ce, prog_ce),
            ('CE-303', 'Operating Systems', 'theory_lab', dept_ce, prog_ce),
            ('CE-304', 'Database Systems', 'theory_lab', dept_ce, prog_ce),
            ('EE-301', 'Signals & Systems', 'theory', dept_ee, prog_ee),
            ('EE-302', 'Electromagnetics', 'theory', dept_ee, prog_ee),
            ('EE-303', 'Control Systems', 'theory_lab', dept_ee, prog_ee),
            ('EE-304', 'Power Electronics', 'theory_lab', dept_ee, prog_ee),
        ]

        offerings_created = 0
        for idx, (code, name, ctype, dept, prog) in enumerate(course_catalog):
            course, _ = Course.objects.get_or_create(
                code=code, defaults=dict(
                    name=name, program=prog, semester=semesters[prog.code],
                    credit_hours=3, theory_hours=3, lab_hours=1 if 'lab' in ctype else 0,
                    weekly_hours=4 if 'lab' in ctype else 3,
                    course_type=ctype, room_type_required=rt_lecture,
                    lab_room_type_required=rt_lab if 'lab' in ctype else None,
                    max_students_per_section=50,
                )
            )
            teacher = teachers[idx % len(teachers)]
            for section, group in zip(('A', 'B'), groups[prog.code]):
                offering, created = CourseOffering.objects.get_or_create(
                    course=course, academic_session=session, section_name=section,
                    defaults=dict(
                        primary_teacher=teacher, max_students=group.size,
                        current_enrollment=group.size, status='confirmed',
                        requires_lab='lab' in ctype,
                        lab_teacher=teacher if 'lab' in ctype else None,
                    )
                )
                CourseOfferingGroup.objects.get_or_create(
                    course_offering=offering, student_group=group, defaults={'is_primary': True}
                )
                if created:
                    offerings_created += 1

        for name, target in [
            ('No Teacher Clash', 'schedules'), ('No Room Clash', 'schedules'),
            ('No Student Group Clash', 'schedules'),
        ]:
            ConstraintCatalog.objects.get_or_create(
                constraint_name=name, defaults=dict(
                    constraint_type='hard', target_table=target,
                    rule_definition={'auto_seeded': True},
                )
            )

        self.stdout.write(self.style.SUCCESS(
            f"Seeded: {len(rooms)} rooms, {TimeSlot.objects.count()} time slots, "
            f"{len(teachers)} teachers, {len(course_catalog)} courses, "
            f"{offerings_created} new course offerings (session='{session.name}')."
        ))
