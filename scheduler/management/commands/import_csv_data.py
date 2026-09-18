"""
Loads a CSV constraint dataset into the ChronosFair database. This is the
ONLY data-entry path the system needs to run: load constraints -> run a GA
-> the GA writes its own Schedule rows. Nothing here pre-writes a schedule.

v2 — fully data-driven. Earlier versions hardcoded the university, one
faculty, and exactly two programs (BSCE/BSSE). This version reads the org
structure (university / faculties / departments / programs / buildings)
from its own CSVs, so it works for any number of departments and programs
without touching this file. See data/csv_template/README.md for the full
column reference and a filled two-department example.

Usage:
    python manage.py import_csv_data --dir data/csv_template
    python manage.py import_csv_data --dir data/csv_template --wipe

Optional — comparing against a real, already-known timetable is a SEPARATE,
opt-in step for benchmarking only. It is never required to run the system
and the GA never reads it:
    python manage.py import_csv_data --dir data/csv --with-ground-truth
"""
import csv
import datetime
import os

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction, IntegrityError

from scheduler.models import (
    University, Faculty, Department, Program, Semester, AcademicSession,
    Batch, StudentGroup, Building, RoomType, Room, TimeSlot, Teacher,
    Course, CourseOffering, CourseOfferingGroup, Schedule,
)

DEFAULT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                            "..", "data", "csv")

REQUIRED_FILES = [
    "university.csv", "faculties.csv", "departments.csv", "programs.csv",
    "buildings.csv", "rooms.csv", "time_slots.csv", "teachers.csv",
    "sections.csv", "courses.csv", "course_offerings.csv",
]


def read_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


class Command(BaseCommand):
    help = "Import a CSV constraint dataset (org structure + rooms/teachers/courses/sections) into the DB."

    def add_arguments(self, parser):
        parser.add_argument("--dir", default=os.path.normpath(DEFAULT_DIR),
                             help="Folder containing university.csv, faculties.csv, ..., course_offerings.csv")
        parser.add_argument("--session", default="Fall 2026")
        parser.add_argument("--session-start", default="2026-09-01", help="YYYY-MM-DD")
        parser.add_argument("--session-end", default="2026-12-31", help="YYYY-MM-DD")
        parser.add_argument("--exam-start", default="2026-12-08", help="YYYY-MM-DD")
        parser.add_argument("--exam-end", default="2026-12-19", help="YYYY-MM-DD")
        parser.add_argument("--wipe", action="store_true",
                             help="Delete existing Schedule rows for this session before importing (only relevant with --with-ground-truth).")
        parser.add_argument("--with-ground-truth", action="store_true",
                             help="Also load schedule.csv from --dir as a fixed, non-GA "
                                  "'Schedule' baseline (generated_by_ga=False), purely for "
                                  "diffing against the GA's own output later. Optional; the "
                                  "GA never reads these rows. Requires schedule.csv to exist "
                                  "in --dir.")

    @transaction.atomic
    def handle(self, *args, **opts):
        d = opts["dir"]
        session_name = opts["session"]

        missing = [f for f in REQUIRED_FILES if not os.path.exists(os.path.join(d, f))]
        if missing:
            raise CommandError(
                f"Missing CSV file(s) in {d}: {', '.join(missing)}. "
                "See data/csv_template/README.md for the full column reference."
            )

        university_rows = read_csv(os.path.join(d, "university.csv"))
        faculty_rows = read_csv(os.path.join(d, "faculties.csv"))
        department_rows = read_csv(os.path.join(d, "departments.csv"))
        program_rows = read_csv(os.path.join(d, "programs.csv"))
        building_rows = read_csv(os.path.join(d, "buildings.csv"))
        rooms = read_csv(os.path.join(d, "rooms.csv"))
        teachers = read_csv(os.path.join(d, "teachers.csv"))
        time_slots = read_csv(os.path.join(d, "time_slots.csv"))
        sections = read_csv(os.path.join(d, "sections.csv"))
        courses = read_csv(os.path.join(d, "courses.csv"))
        offerings = read_csv(os.path.join(d, "course_offerings.csv"))

        schedule = []
        if opts["with_ground_truth"]:
            schedule_path = os.path.join(d, "schedule.csv")
            if not os.path.exists(schedule_path):
                raise CommandError(
                    f"--with-ground-truth was passed but {schedule_path} does not exist."
                )
            schedule = read_csv(schedule_path)

        # ---- university (exactly one row expected) ----
        if not university_rows:
            raise CommandError("university.csv is empty — needs exactly one row.")
        u = university_rows[0]
        university, _ = University.objects.get_or_create(
            code=u["code"], defaults={"name": u["name"], "location": u.get("location", "")}
        )

        # ---- faculties ----
        faculty_objs = {}
        for row in faculty_rows:
            fac, _ = Faculty.objects.get_or_create(
                code=row["code"], university=university, defaults={"name": row["name"]}
            )
            faculty_objs[row["code"]] = fac

        # ---- departments (any number, any codes) ----
        department_objs = {}
        for row in department_rows:
            fac = faculty_objs.get(row["faculty_code"])
            if fac is None:
                raise CommandError(f"departments.csv: unknown faculty_code '{row['faculty_code']}' for department '{row['code']}'.")
            dept, _ = Department.objects.get_or_create(
                code=row["code"], faculty=fac, defaults={"name": row["name"]}
            )
            department_objs[row["code"]] = dept

        # ---- programs (any number, mapped to a department) ----
        program_objs = {}
        for row in program_rows:
            dept = department_objs.get(row["department_code"])
            if dept is None:
                raise CommandError(f"programs.csv: unknown department_code '{row['department_code']}' for program '{row['code']}'.")
            prog, _ = Program.objects.get_or_create(
                code=row["code"], department=dept,
                defaults=dict(
                    name=row["name"],
                    degree_type=row.get("degree_type", "bs"),
                    duration_semesters=int(row.get("duration_semesters", 8)),
                ),
            )
            program_objs[row["code"]] = prog

        # ---- academic session ----
        def parse_date(s):
            return datetime.date.fromisoformat(s)
        session, _ = AcademicSession.objects.get_or_create(
            name=session_name,
            defaults=dict(
                start_date=parse_date(opts["session_start"]),
                end_date=parse_date(opts["session_end"]),
                exam_start_date=parse_date(opts["exam_start"]),
                exam_end_date=parse_date(opts["exam_end"]),
                status="active",
            ),
        )

        # ---- buildings ----
        building_objs = {}
        for row in building_rows:
            b, _ = Building.objects.get_or_create(
                code=row["code"], university=university,
                defaults={"name": row["name"], "floors": int(row.get("floors", 1))},
            )
            building_objs[row["code"]] = b
        if not building_objs:
            raise CommandError("buildings.csv is empty — need at least one building for rooms.csv to reference.")

        # ---- room types + rooms ----
        room_types = {}
        room_objs = {}
        for row in rooms:
            rt_code = row["room_type"]
            if rt_code not in room_types:
                rt, _ = RoomType.objects.get_or_create(
                    code=rt_code.upper(), defaults={"name": rt_code.replace("_", " ").title()}
                )
                room_types[rt_code] = rt
        for row in rooms:
            building = building_objs.get(row.get("building_code"), next(iter(building_objs.values())))
            room_objs[row["code"]] = Room.objects.get_or_create(
                code=row["code"],
                defaults=dict(
                    name=row["name"], room_type=room_types[row["room_type"]],
                    building=building, capacity=int(row["capacity"]),
                    has_projector=True, has_whiteboard=True,
                ),
            )[0]

        # ---- time slots ----
        slot_objs = {}
        for row in time_slots:
            h1, m1 = map(int, row["start_time"].split(":"))
            h2, m2 = map(int, row["end_time"].split(":"))
            ts, _ = TimeSlot.objects.get_or_create(
                day_of_week=int(row["day_of_week"]),
                start_time=datetime.time(h1, m1),
                end_time=datetime.time(h2, m2),
                defaults={"slot_type": row["slot_type"]},
            )
            slot_objs[row["slot_key"]] = ts

        # ---- teachers (department resolved dynamically now) ----
        teacher_objs = {}
        fallback_dept = next(iter(department_objs.values())) if department_objs else None
        for row in teachers:
            dept = department_objs.get(row["department_code"], fallback_dept)
            if dept is None:
                raise CommandError(f"teachers.csv: unknown department_code '{row['department_code']}' for teacher '{row['name']}' and no fallback department exists.")
            t, _ = Teacher.objects.get_or_create(
                email=row["email"],
                defaults=dict(
                    employee_id=row["employee_id"], name=row["name"],
                    department=dept,
                    designation=row["designation"],
                    max_teaching_hours=int(row["max_teaching_hours"]),
                    max_lab_hours=int(row["max_lab_hours"]),
                ),
            )
            teacher_objs[row["name"]] = t

        # ---- semesters, batches, sections/student groups ----
        semester_objs = {}
        batch_objs = {}
        group_objs = {}
        for row in sections:
            prog = program_objs.get(row["program_code"])
            if prog is None:
                raise CommandError(f"sections.csv: unknown program_code '{row['program_code']}' for section '{row['section_code']}'.")
            sem_num = int(row["semester_number"])
            sem, _ = Semester.objects.get_or_create(
                program=prog, semester_number=sem_num,
                defaults={"name": f"Semester {sem_num}"},
            )
            semester_objs[(prog.code, sem_num)] = sem

            batch, _ = Batch.objects.get_or_create(
                program=prog, batch_year=int(row["batch_year"]),
                defaults=dict(
                    name=f"{prog.code} {row['batch_year']}", intake_session=session,
                    current_semester=sem, total_students=int(row["size"]),
                ),
            )
            batch_objs[(prog.code, row["batch_year"])] = batch

            group, _ = StudentGroup.objects.get_or_create(
                batch=batch, section_name=row["section_name"],
                defaults={"size": int(row["size"])},
            )
            group_objs[row["section_code"]] = group

        # ---- room type lookups for courses (lecture vs lab) ----
        rt_lecture, _ = RoomType.objects.get_or_create(
            code="LECTURE_ROOM", defaults={"name": "Lecture Room"}
        )
        rt_lab, _ = RoomType.objects.get_or_create(
            code="COMPUTER_LAB", defaults={"name": "Computer Lab"}
        )

        # ---- courses ----
        course_objs = {}
        for row in courses:
            prog = program_objs.get(row["program_code"])
            if prog is None:
                raise CommandError(f"courses.csv: unknown program_code '{row['program_code']}' for course '{row['code']}'.")
            sem_num = int(row["semester_number"])
            sem = semester_objs.get((prog.code, sem_num))
            if sem is None:
                # A course can reference a semester no section uses yet — create it.
                sem, _ = Semester.objects.get_or_create(
                    program=prog, semester_number=sem_num,
                    defaults={"name": f"Semester {sem_num}"},
                )
                semester_objs[(prog.code, sem_num)] = sem
            has_lab = row["course_type"] == "theory_lab"
            course, _ = Course.objects.get_or_create(
                code=row["code"],
                defaults=dict(
                    name=row["name"], program=prog, semester=sem,
                    credit_hours=int(row["credit_hours"]),
                    theory_hours=int(row["credit_hours"]),
                    lab_hours=1 if has_lab else 0,
                    weekly_hours=int(row["weekly_hours"]),
                    course_type=row["course_type"],
                    room_type_required=rt_lecture,
                    lab_room_type_required=rt_lab if has_lab else None,
                    max_students_per_section=50,
                ),
            )
            course_objs[row["code"]] = course

        # ---- course offerings ----
        offering_objs = {}
        skipped_offerings = []
        for row in offerings:
            course = course_objs.get(row["course_code"])
            group = group_objs.get(row["section_code"])
            if not course or not group:
                skipped_offerings.append((row["course_code"], row["section_code"]))
                continue
            primary = teacher_objs.get(row["primary_teacher"])
            lab_t = teacher_objs.get(row["lab_teacher"]) if row.get("lab_teacher") else None
            requires_lab = row["requires_lab"].strip().lower() == "true"
            offering, _ = CourseOffering.objects.get_or_create(
                course=course, academic_session=session, section_name=group.section_name,
                defaults=dict(
                    primary_teacher=primary, lab_teacher=lab_t,
                    max_students=group.size, current_enrollment=group.size,
                    status="confirmed", requires_lab=requires_lab,
                ),
            )
            CourseOfferingGroup.objects.get_or_create(
                course_offering=offering, student_group=group, defaults={"is_primary": True}
            )
            offering_objs[(row["course_code"], row["section_code"])] = offering

        # ---- optional ground-truth schedule rows (--with-ground-truth only) ----
        if opts["wipe"] and opts["with_ground_truth"]:
            Schedule.objects.filter(academic_session=session, generated_by_ga=False).delete()

        created = 0
        skipped_conflicts = []
        for row in schedule:
            key = (row["course_code"], row["section_code"])
            offering = offering_objs.get(key)
            group = group_objs.get(row["section_code"])
            room = room_objs.get(row["room_code"])
            slot = slot_objs.get(row["slot_key"])
            teacher = teacher_objs.get(row["teacher"])
            if not (offering and group and room and slot and teacher):
                continue
            try:
                with transaction.atomic():
                    _, created_flag = Schedule.objects.get_or_create(
                        course_offering=offering, time_slot=slot, room=room,
                        defaults=dict(
                            schedule_type=row["schedule_type"], teacher=teacher,
                            student_group=group, academic_session=session,
                            status="active", generated_by_ga=False,
                        ),
                    )
                if created_flag:
                    created += 1
            except IntegrityError as e:
                skipped_conflicts.append((row["section_code"], row["slot_key"], row["course_name"], str(e)))

        lab_offering_count = sum(1 for o in offering_objs.values() if o.requires_lab)
        self.stdout.write(self.style.SUCCESS(
            f"Imported: {len(department_objs)} department(s), {len(program_objs)} program(s), "
            f"{len(room_objs)} rooms, {len(teacher_objs)} teachers, "
            f"{len(group_objs)} sections, {len(course_objs)} courses, "
            f"{len(offering_objs)} offerings ({lab_offering_count} requiring a lab) "
            f"(session='{session.name}')."
        ))
        if skipped_offerings:
            self.stdout.write(self.style.WARNING(
                f"Skipped {len(skipped_offerings)} row(s) in course_offerings.csv with an "
                f"unknown course_code or section_code:"
            ))
            for cc, sc in skipped_offerings:
                self.stdout.write(f"  - course_code='{cc}' section_code='{sc}'")
        if opts["with_ground_truth"]:
            self.stdout.write(self.style.SUCCESS(
                f"Also loaded {created} ground-truth schedule rows (generated_by_ga=False) "
                f"for later comparison — the GA does not read these."
            ))
        else:
            self.stdout.write(
                "No schedule rows loaded (constraints only). Run "
                "`python manage.py run_course_ga --session "
                f"\"{session.name}\"` next to have the GA generate one."
            )
        if skipped_conflicts:
            self.stdout.write(self.style.WARNING(
                f"Skipped {len(skipped_conflicts)} rows due to real room/teacher/group "
                f"clashes across the merged timetables (expected — see below):"
            ))
            for sec, slot_key, cname, err in skipped_conflicts:
                self.stdout.write(f"  - {sec} {slot_key} '{cname}': {err.splitlines()[0]}")
