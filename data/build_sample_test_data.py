"""
Builds a SYNTHETIC sample/test dataset for ChronosFair.

This is the ONE dataset the system needs to run end-to-end:
    rooms.csv, teachers.csv, time_slots.csv, sections.csv, courses.csv,
    course_offerings.csv

There is deliberately NO schedule.csv here. This generator only produces
*constraints* (who can teach what, which rooms exist, which sections need
which courses) — never a finished timetable. The business logic layer
(scheduler/genetic/course_ga.py, run via `manage.py run_course_ga`) is what
reads these constraints and decides the actual slot+room assignments.

This is intentionally separate from build_csv_from_timetable.py, which
scrapes a REAL Air University timetable into data/csv/ (including a
schedule.csv "answer key" used only for optional, later benchmarking —
see import_csv_data.py --with-ground-truth). Keep the two folders apart:
never let a schedule.csv from the real data leak into this one.

Usage:
    python data/build_sample_test_data.py
    python manage.py import_csv_data --dir data/csv_sample
    python manage.py run_course_ga --session "Fall 2026"
"""
import csv
import os
import random

OUT = os.path.join(os.path.dirname(__file__), "csv_sample")
os.makedirs(OUT, exist_ok=True)

rng = random.Random(7)  # fixed seed -> reproducible sample data

SLOT_TIMES = {
    1: ("08:00", "09:20"),
    2: ("09:20", "10:40"),
    3: ("10:40", "12:00"),
    4: ("12:00", "13:20"),
    5: ("13:20", "14:40"),
    6: ("14:40", "16:00"),
}
DAYS = [(1, "Monday", "Mo"), (2, "Tuesday", "Tu"), (3, "Wednesday", "We"),
        (4, "Thursday", "Th"), (5, "Friday", "Fr")]

# ---------------------------------------------------------------- rooms ----
ROOMS = [
    ("R-101", "lecture_room", 60),
    ("R-102", "lecture_room", 60),
    ("R-103", "lecture_room", 45),
    ("R-104", "lecture_room", 45),
    ("LAB-1", "computer_lab", 45),
    ("LAB-2", "computer_lab", 45),
]

# ------------------------------------------------------------- teachers ----
TEACHERS = [
    ("T001", "Dr. Sara Ahmed", "assistant_professor"),
    ("T002", "Dr. Bilal Hussain", "associate_professor"),
    ("T003", "Faisal Iqbal", "lecturer"),
    ("T004", "Hina Malik", "lecturer"),
    ("T005", "Dr. Omar Farooq", "assistant_professor"),
    ("T006", "Zainab Riaz", "visiting_faculty"),
    ("T007", "Dr. Kamran Aziz", "associate_professor"),
    ("T008", "Sania Butt", "lecturer"),
]

# ------------------------------------------------------------- sections ----
# (section_code, program_code, batch_year, section_letter, semester_number, size)
SECTIONS = [
    ("TEST-CE-1A", "BSCE", 2026, "A", 1, 40),
    ("TEST-CE-1B", "BSCE", 2026, "B", 1, 40),
    ("TEST-CE-3A", "BSCE", 2025, "A", 3, 38),
    ("TEST-SE-1A", "BSSE", 2026, "A", 1, 35),
]

# ------------------------------------------------------------- courses -----
# (code, name, program_code, semester_number, credit_hours, course_type, weekly_hours)
COURSES = [
    ("T-CE101", "Intro to Programming", "BSCE", 1, 3, "theory", 3),
    ("T-CE101L", "Intro to Programming Lab", "BSCE", 1, 1, "theory_lab", 3),
    ("T-CE102", "Calculus I", "BSCE", 1, 3, "theory", 3),
    ("T-CE103", "Applied Physics", "BSCE", 1, 3, "theory", 3),
    ("T-CE301", "Data Structures", "BSCE", 3, 3, "theory", 3),
    ("T-CE301L", "Data Structures Lab", "BSCE", 3, 1, "theory_lab", 3),
    ("T-CE302", "Digital Logic Design", "BSCE", 3, 3, "theory", 3),
    ("T-SE101", "Intro to Programming", "BSSE", 1, 3, "theory", 3),
    ("T-SE101L", "Intro to Programming Lab", "BSSE", 1, 1, "theory_lab", 3),
    ("T-SE102", "Discrete Structures", "BSSE", 1, 3, "theory", 3),
]

# section_code -> list of course codes that section takes
SECTION_COURSES = {
    "TEST-CE-1A": ["T-CE101", "T-CE101L", "T-CE102", "T-CE103"],
    "TEST-CE-1B": ["T-CE101", "T-CE101L", "T-CE102", "T-CE103"],
    "TEST-CE-3A": ["T-CE301", "T-CE301L", "T-CE302"],
    "TEST-SE-1A": ["T-SE101", "T-SE101L", "T-SE102"],
}


def write_csv(name, fieldnames, rows):
    with open(os.path.join(OUT, name), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)


def main():
    # rooms.csv
    room_rows = [
        {"code": code, "name": code, "room_type": rtype, "capacity": cap, "building_code": "TEST-BLK"}
        for code, rtype, cap in ROOMS
    ]
    write_csv("rooms.csv", ["code", "name", "room_type", "capacity", "building_code"], room_rows)

    # teachers.csv
    teacher_rows = [
        {
            "employee_id": emp_id, "name": name,
            "email": name.lower().replace("dr. ", "").replace(" ", ".") + "@test.edu.pk",
            "department_code": "CE", "designation": designation,
            "max_teaching_hours": 18, "max_lab_hours": 6,
        }
        for emp_id, name, designation in TEACHERS
    ]
    write_csv(
        "teachers.csv",
        ["employee_id", "name", "email", "department_code", "designation",
         "max_teaching_hours", "max_lab_hours"],
        teacher_rows,
    )

    # time_slots.csv (same grid as the real data, kept consistent on purpose)
    slot_rows = []
    for day_num, day_name, day_abbr in DAYS:
        for slot_num, (start, end) in SLOT_TIMES.items():
            slot_rows.append({
                "slot_key": f"{day_abbr}{slot_num}", "day_of_week": day_num,
                "day_name": day_name, "start_time": start, "end_time": end,
                "slot_type": "morning" if slot_num <= 3 else "afternoon",
            })
    write_csv("time_slots.csv",
              ["slot_key", "day_of_week", "day_name", "start_time", "end_time", "slot_type"],
              slot_rows)

    # sections.csv
    section_rows = [
        {
            "section_code": code, "program_code": prog, "batch_year": year,
            "section_name": letter, "semester_number": sem, "size": size,
        }
        for code, prog, year, letter, sem, size in SECTIONS
    ]
    write_csv("sections.csv",
              ["section_code", "program_code", "batch_year", "section_name",
               "semester_number", "size"],
              section_rows)

    # courses.csv
    course_rows = [
        {
            "code": code, "name": name, "program_code": prog,
            "semester_number": sem, "credit_hours": ch,
            "course_type": ctype, "weekly_hours": wh,
        }
        for code, name, prog, sem, ch, ctype, wh in COURSES
    ]
    write_csv("courses.csv",
              ["code", "name", "program_code", "semester_number", "credit_hours",
               "course_type", "weekly_hours"],
              course_rows)

    # course_offerings.csv — randomly (but reproducibly) assign teachers per
    # section+course. This is where the GA gets its real freedom: it decides
    # WHEN and WHERE each offering meets, not this script.
    teacher_names = [t[1] for t in TEACHERS]
    offering_rows = []
    for sec_code, course_codes in SECTION_COURSES.items():
        for course_code in course_codes:
            is_lab = course_code.endswith("L")
            primary = rng.choice(teacher_names)
            lab_teacher = rng.choice(teacher_names) if is_lab else ""
            offering_rows.append({
                "course_code": course_code, "section_code": sec_code,
                "primary_teacher": primary, "lab_teacher": lab_teacher,
                "requires_lab": is_lab,
            })
    write_csv("course_offerings.csv",
              ["course_code", "section_code", "primary_teacher", "lab_teacher", "requires_lab"],
              offering_rows)

    # ---- org-structure CSVs (university/faculties/departments/programs/buildings) ----
    # import_csv_data.py v2 is fully data-driven and needs these alongside the
    # constraint CSVs above — write them here too so this script stays a
    # complete, self-sufficient dataset generator.
    write_csv("university.csv", ["code", "name", "location"],
              [{"code": "AU", "name": "Air University", "location": "Islamabad"}])
    write_csv("faculties.csv", ["code", "name", "university_code"],
              [{"code": "ENG", "name": "Faculty of Engineering", "university_code": "AU"}])
    write_csv("departments.csv", ["code", "name", "faculty_code"], [
        {"code": "CE", "name": "Computer Engineering", "faculty_code": "ENG"},
        {"code": "SE", "name": "Software Engineering", "faculty_code": "ENG"},
    ])
    write_csv("programs.csv", ["code", "name", "department_code", "degree_type", "duration_semesters"], [
        {"code": "BSCE", "name": "BS Computer Engineering", "department_code": "CE", "degree_type": "bs", "duration_semesters": 8},
        {"code": "BSSE", "name": "BS Software Engineering", "department_code": "SE", "degree_type": "bs", "duration_semesters": 8},
    ])
    write_csv("buildings.csv", ["code", "name", "floors", "university_code"],
              [{"code": "TEST-BLK", "name": "Test Block", "floors": 3, "university_code": "AU"}])

    print(f"Wrote sample/test constraint data to {OUT}/")
    print(f"  Rooms: {len(room_rows)}, Teachers: {len(teacher_rows)}, "
          f"Time slots: {len(slot_rows)}, Sections: {len(section_rows)}, "
          f"Courses: {len(course_rows)}, Offerings: {len(offering_rows)}")
    print("  (no schedule.csv written — the GA generates that)")


if __name__ == "__main__":
    main()
