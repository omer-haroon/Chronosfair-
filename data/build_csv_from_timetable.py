"""
Builds sample-data CSVs (matching the ChronosFair Django schema) from the
Fall-2026 Air University CE/SE timetable PDF you uploaded.

Run once to (re)generate the CSVs in data/csv/. These CSVs are the
"source of truth" sample dataset — edit them by hand for further tweaks,
or point scheduler/management/commands/import_csv_data.py at a different
folder to load a different semester's timetable later.
"""
import csv
import os

OUT = os.path.join(os.path.dirname(__file__), "csv")
os.makedirs(OUT, exist_ok=True)

SLOT_TIMES = {
    1: ("08:00", "09:20"),
    2: ("09:20", "10:40"),
    3: ("10:40", "12:00"),
    4: ("12:00", "13:20"),
    5: ("13:20", "14:40"),
    6: ("14:40", "16:00"),
}
DAY_NAME = {1: "Monday", 2: "Tuesday", 3: "Wednesday", 4: "Thursday", 5: "Friday"}
DAY_ABBR = {"Mo": 1, "Tu": 2, "We": 3, "Th": 4, "Fr": 5}

# section_code -> (program_code, batch_year, section_letter, semester_number)
SECTIONS = {
    "BCE-F-23-A": ("BSCE", 2023, "A", 7),
    "BCE-F-23-B": ("BSCE", 2023, "B", 7),
    "BCE-F-24-A": ("BSCE", 2024, "A", 5),
    "BCE-F-24-B": ("BSCE", 2024, "B", 5),
    "BCE-F-25-A": ("BSCE", 2025, "A", 3),
    "BCE-F-25-B": ("BSCE", 2025, "B", 3),
    "BCE-F26-A":  ("BSCE", 2026, "A", 1),
    "BCE-F-26-B": ("BSCE", 2026, "B", 1),
    "BSE-F-26-A": ("BSSE", 2026, "A", 1),
    "BSE-F-25-A": ("BSSE", 2025, "A", 3),
}

# (section, day_abbr, start_slot, duration_slots, kind, course_name, teacher, room)
# kind: 'class' (theory, 1 slot / 80 min) or 'lab' (2 slots / 160 min)
ENTRIES = [
    # ---------------- BCE-F-23-A ----------------
    ("BCE-F-23-A", "Mo", 1, 1, "class", "Digital System Design", "Usman Hameed", "B-001"),
    ("BCE-F-23-A", "Mo", 2, 1, "class", "Machine Learning", "Ayesha Sadiq", "B-001"),
    ("BCE-F-23-A", "Mo", 3, 1, "class", "Final Year Project-II", "Dr. Ayesha Salman", "B-203"),
    ("BCE-F-23-A", "Mo", 5, 1, "class", "Contemporary International Relations", "Awais Ali", "B-006"),
    ("BCE-F-23-A", "Tu", 3, 2, "lab", "Cloud and Distributed Computing Laboratory", "Maryam Sheikh", "Signal & Image Processing Lab"),
    ("BCE-F-23-A", "Tu", 5, 1, "class", "Cloud and Distributed Computing", "Dr. Fawad Salam Khan", "B-001"),
    ("BCE-F-23-A", "Tu", 6, 1, "class", "Machine Learning", "Ayesha Sadiq", "B-005"),
    ("BCE-F-23-A", "We", 3, 2, "lab", "Machine Learning Laboratory", "Ayesha Sadiq", "Computer Lab-21 (B Block Ground Floor)"),
    ("BCE-F-23-A", "We", 5, 1, "class", "Contemporary International Relations", "Awais Ali", "B-006"),
    ("BCE-F-23-A", "We", 6, 1, "class", "Digital System Design", "Usman Hameed", "B-001"),
    ("BCE-F-23-A", "Th", 1, 2, "lab", "Digital System Design Laboratory", "Usman Hameed", "Signal & Image Processing Lab"),
    ("BCE-F-23-A", "Th", 4, 1, "class", "Advisory Class", "Usman Hameed", "B-004"),
    ("BCE-F-23-A", "Th", 5, 1, "class", "Cloud and Distributed Computing", "Dr. Fawad Salam Khan", "B-004"),

    # ---------------- BCE-F-23-B ----------------
    ("BCE-F-23-B", "Mo", 2, 1, "class", "Machine Learning", "Maryam Sabir", "B-004"),
    ("BCE-F-23-B", "Mo", 3, 1, "class", "Digital System Design", "Usman Hameed", "B-001"),
    ("BCE-F-23-B", "Mo", 4, 1, "class", "Contemporary International Relations", "Awais Ali", "B-006"),
    ("BCE-F-23-B", "Mo", 5, 2, "lab", "Cloud and Distributed Computing Laboratory", "Maryam Sheikh", "Signal & Image Processing Lab"),
    ("BCE-F-23-B", "We", 3, 1, "class", "Final Year Project-II", "Dr. Ayesha Salman", "B-005"),
    ("BCE-F-23-B", "We", 4, 1, "class", "Cloud and Distributed Computing", "Muhammad Naveed Khurshed", "B-203"),
    ("BCE-F-23-B", "We", 5, 1, "class", "Digital System Design", "Usman Hameed", "B-005"),
    ("BCE-F-23-B", "We", 6, 1, "class", "Contemporary International Relations", "Awais Ali", "B-004"),
    ("BCE-F-23-B", "Th", 1, 1, "class", "Machine Learning", "Maryam Sabir", "B-004"),
    ("BCE-F-23-B", "Th", 3, 1, "class", "Cloud and Distributed Computing", "Muhammad Naveed Khurshed", "B-004"),
    ("BCE-F-23-B", "Th", 6, 1, "class", "Advisory Class", "Zo Afshan", "B-203"),
    ("BCE-F-23-B", "Fr", 1, 2, "lab", "Digital System Design Laboratory", "Usman Hameed", "Computer Systems Design Lab"),
    ("BCE-F-23-B", "Fr", 5, 2, "lab", "Machine Learning Laboratory", "Maryam Sabir", "Signal & Image Processing Lab"),

    # ---------------- BCE-F-24-A ----------------
    ("BCE-F-24-A", "Mo", 2, 1, "class", "Probability Methods in Engineering", "Dr. Jehanzeb Khan", "B-006"),
    ("BCE-F-24-A", "Mo", 3, 2, "lab", "Operating Systems Laboratory", "Javeria Razzaq", "Signal & Image Processing Lab"),
    ("BCE-F-24-A", "Mo", 5, 1, "class", "Computer Communication and Networks", "Basharat", "B-004"),
    ("BCE-F-24-A", "Tu", 1, 2, "lab", "Signals & Systems Laboratory", "Maryam Sheikh", "Computer Lab-9 (B Block Ground Floor)"),
    ("BCE-F-24-A", "Tu", 3, 1, "class", "Computer Communication and Networks", "Basharat", "B-001"),
    ("BCE-F-24-A", "Tu", 5, 1, "class", "Software Engineering", "Muhammad Naveed Khurshed", "B-203"),
    ("BCE-F-24-A", "We", 2, 1, "class", "Signals & Systems", "Dr. Ayesha Salman", "B-004"),
    ("BCE-F-24-A", "We", 3, 1, "class", "Operating Systems", "Dr. Hadi Abdullah", "B-001"),
    ("BCE-F-24-A", "We", 4, 1, "class", "Probability Methods in Engineering", "Dr. Jehanzeb Khan", "B-004"),
    ("BCE-F-24-A", "We", 5, 2, "lab", "Computer Communication and Networks Laboratory", "Basharat", "Telecom Networks Lab"),
    ("BCE-F-24-A", "Th", 2, 1, "class", "Signals & Systems", "Dr. Ayesha Salman", "B-005"),
    ("BCE-F-24-A", "Th", 4, 1, "class", "Software Engineering", "Muhammad Naveed Khurshed", "B-005"),
    ("BCE-F-24-A", "Th", 5, 1, "class", "Operating Systems", "Dr. Hadi Abdullah", "B-203"),
    ("BCE-F-24-A", "Th", 6, 1, "class", "Advisory Class", "Ayesha Sadiq", "B-001"),

    # ---------------- BCE-F-24-B ----------------
    ("BCE-F-24-B", "Mo", 1, 1, "class", "Advisory Class", "Maryam Sabir", "B-006"),
    ("BCE-F-24-B", "Mo", 2, 1, "class", "Signals & Systems", "Dr. Ayesha Salman", "B-005"),
    ("BCE-F-24-B", "Mo", 3, 1, "class", "Software Engineering", "Muhammad Atif Bajwa", "B-006"),
    ("BCE-F-24-B", "Mo", 5, 2, "lab", "Computer Communication and Networks Laboratory", "Aneeq Ahmad", "Telecom Networks Lab"),
    ("BCE-F-24-B", "Tu", 1, 1, "class", "Signals & Systems", "Dr. Ayesha Salman", "B-203"),
    ("BCE-F-24-B", "Tu", 4, 1, "class", "Probability Methods in Engineering", "Dr. Jehanzeb Khan", "B-004"),
    ("BCE-F-24-B", "Tu", 6, 1, "class", "Computer Communication and Networks", "Aneeq Ahmad", "B-004"),
    ("BCE-F-24-B", "We", 2, 1, "class", "Probability Methods in Engineering", "Dr. Jehanzeb Khan", "B-001"),
    ("BCE-F-24-B", "We", 4, 1, "class", "Operating Systems", "Dr. Hadi Abdullah", "B-005"),
    ("BCE-F-24-B", "We", 5, 2, "lab", "Operating Systems Laboratory", "Javeria Razzaq", "Signal & Image Processing Lab"),
    ("BCE-F-24-B", "Th", 1, 1, "class", "Computer Communication and Networks", "Aneeq Ahmad", "B-006"),
    ("BCE-F-24-B", "Th", 3, 1, "class", "Operating Systems", "Dr. Hadi Abdullah", "B-006"),
    ("BCE-F-24-B", "Th", 4, 1, "class", "Software Engineering", "Muhammad Atif Bajwa", "B-006"),
    ("BCE-F-24-B", "Th", 5, 2, "lab", "Signals & Systems Laboratory", "Maryam Sheikh", "Signal & Image Processing Lab"),

    # ---------------- BCE-F-25-A ----------------
    ("BCE-F-25-A", "Mo", 1, 2, "lab", "Digital Logic Design Laboratory", "Anwar Saeed", "Communication Lab"),
    ("BCE-F-25-A", "Mo", 3, 1, "class", "Linear Algebra and Differential Equations", "Nida Tanveer", "B-004"),
    ("BCE-F-25-A", "Mo", 4, 1, "class", "Islamic Studies and Ethics", "Hussain Mujtaba", "B-001"),
    ("BCE-F-25-A", "Mo", 6, 1, "class", "Electronic Devices and Circuits", "Dr. Muhammad Zaheer", "B-004"),
    ("BCE-F-25-A", "Tu", 2, 1, "class", "Islamic Studies and Ethics", "Hussain Mujtaba", "B-001"),
    ("BCE-F-25-A", "Tu", 3, 1, "class", "Electronic Devices and Circuits", "Dr. Muhammad Zaheer", "B-006"),
    ("BCE-F-25-A", "Tu", 4, 1, "class", "Linear Algebra and Differential Equations", "Nida Tanveer", "B-006"),
    ("BCE-F-25-A", "Tu", 5, 2, "lab", "Data Structures and Algorithms Laboratory", "Zo Afshan", "Computer Systems Design Lab"),
    ("BCE-F-25-A", "We", 2, 1, "class", "Data Structures and Algorithms", "Zo Afshan", "B-005"),
    ("BCE-F-25-A", "We", 4, 1, "class", "Linear Algebra and Differential Equations", "Nida Tanveer", "B-001"),
    ("BCE-F-25-A", "We", 6, 1, "class", "Digital Logic Design", "Anwar Saeed", "B-005"),
    ("BCE-F-25-A", "Th", 2, 1, "class", "Advisory Class", "Dr. Mumajjed Ul Mudassir", "B-203"),
    ("BCE-F-25-A", "Th", 3, 2, "lab", "Electronic Devices and Circuits Laboratory", "Laraib", "Electronics System Lab"),
    ("BCE-F-25-A", "Th", 5, 1, "class", "Data Structures and Algorithms", "Zo Afshan", "B-001"),
    ("BCE-F-25-A", "Th", 6, 1, "class", "Digital Logic Design", "Anwar Saeed", "B-005"),

    # ---------------- BCE-F-25-B ----------------
    ("BCE-F-25-B", "Mo", 1, 1, "class", "Linear Algebra and Differential Equations", "Nida Tanveer", "B-004"),
    ("BCE-F-25-B", "Mo", 4, 1, "class", "Data Structures and Algorithms", "Ayesha Sadiq", "B-005"),
    ("BCE-F-25-B", "Mo", 6, 1, "class", "Islamic Studies and Ethics", "Hussain Mujtaba", "B-001"),
    ("BCE-F-25-B", "Tu", 1, 1, "class", "Islamic Studies and Ethics", "Hussain Mujtaba", "B-004"),
    ("BCE-F-25-B", "Tu", 2, 1, "class", "Digital Logic Design", "Zo Afshan", "B-004"),
    ("BCE-F-25-B", "Tu", 3, 2, "lab", "Data Structures and Algorithms Laboratory", "Ayesha Sadiq", "Computer Lab-21 (B Block Ground Floor)"),
    ("BCE-F-25-B", "Tu", 5, 1, "class", "Linear Algebra and Differential Equations", "Nida Tanveer", "B-005"),
    ("BCE-F-25-B", "Tu", 6, 1, "class", "Electronic Devices and Circuits", "Tauseef Ur Rehman", "B-001"),
    ("BCE-F-25-B", "We", 1, 1, "class", "Data Structures and Algorithms", "Ayesha Sadiq", "B-005"),
    ("BCE-F-25-B", "We", 3, 2, "lab", "Digital Logic Design Laboratory", "Zo Afshan", "Digital Signal Processing Lab"),
    ("BCE-F-25-B", "We", 6, 1, "class", "Linear Algebra and Differential Equations", "Nida Tanveer", "B-202"),
    ("BCE-F-25-B", "Fr", 1, 1, "lab", "Electronic Devices and Circuits Laboratory", "Tauseef Ur Rehman", "Communication Lab"),
    ("BCE-F-25-B", "Fr", 2, 1, "class", "Digital Logic Design", "Zo Afshan", "B-006"),
    ("BCE-F-25-B", "Fr", 3, 1, "class", "Advisory Class", "Dr. Jehanzeb Khan", "B-001"),
    ("BCE-F-25-B", "Fr", 4, 1, "class", "Electronic Devices and Circuits", "Tauseef Ur Rehman", "B-006"),

    # ---------------- BCE-F26-A ----------------
    ("BCE-F26-A", "Mo", 1, 2, "lab", "Computer Programming Laboratory", "Zarkaish", "Computer Systems Design Lab"),
    ("BCE-F26-A", "Mo", 4, 1, "class", "Advisory Class", "Muhammad Atif Bajwa", "B-004"),
    ("BCE-F26-A", "Mo", 5, 2, "lab", "Applied Physics Laboratory", "Aqib Rauf", "Physics Lab 2"),
    ("BCE-F26-A", "Tu", 1, 1, "class", "Fehm-e-Quran-I", "Dr. Aftab Ahmad Rai", "B-001"),
    ("BCE-F26-A", "Tu", 2, 1, "class", "Calculus & Analytical Geometry", "Dr. Mahwish Bano", "B-006"),
    ("BCE-F26-A", "Tu", 4, 1, "class", "Information and Communication Technologies (ICT)", "Basharat", "B-001"),
    ("BCE-F26-A", "Tu", 5, 1, "class", "Computer Programming", "Dr. Mumajjed Ul Mudassir", "B-006"),
    ("BCE-F26-A", "Tu", 6, 1, "class", "Functional English", "Khansa Riaz", "B-006"),
    ("BCE-F26-A", "We", 3, 1, "class", "Information and Communication Technologies (ICT)", "Basharat", "B-004"),
    ("BCE-F26-A", "Th", 1, 1, "class", "Fehm-e-Quran-I", "Dr. Aftab Ahmad Rai", "B-005"),
    ("BCE-F26-A", "Th", 2, 1, "class", "Calculus & Analytical Geometry", "Dr. Mahwish Bano", "B-004"),
    ("BCE-F26-A", "Th", 3, 2, "lab", "Information and Communication Technologies (ICT) Laboratory", "Basharat", "Signal & Image Processing Lab"),
    ("BCE-F26-A", "Th", 5, 1, "lab", "Computer Engineering Workshop", "CE-VFM", "Computer Systems Design Lab"),
    ("BCE-F26-A", "Fr", 1, 1, "class", "Computer Programming", "Dr. Mumajjed Ul Mudassir", "B-001"),
    ("BCE-F26-A", "Fr", 2, 1, "class", "Functional English", "Khansa Riaz", "B-004"),
    ("BCE-F26-A", "Fr", 3, 1, "class", "Applied Physics", "Syed Muneeb Abbas Hamdani", "B-005"),
    ("BCE-F26-A", "Fr", 4, 1, "class", "Applied Physics", "Syed Muneeb Abbas Hamdani", "B-005"),

    # ---------------- BCE-F-26-B ----------------
    ("BCE-F-26-B", "Mo", 1, 2, "lab", "Applied Physics Laboratory", "Aqib Rauf", "Physics Lab 2"),
    ("BCE-F-26-B", "Mo", 3, 1, "class", "Computer Programming", "Maryam Sabir", "B-005"),
    ("BCE-F-26-B", "Mo", 5, 1, "class", "Calculus & Analytical Geometry", "Nida Tanveer", "B-005"),
    ("BCE-F-26-B", "Tu", 1, 1, "class", "Applied Physics", "Syed Muneeb Abbas Hamdani", "B-005"),
    ("BCE-F-26-B", "Tu", 2, 1, "class", "Information and Communication Technologies (ICT)", "Aneeq Ahmad", "B-005"),
    ("BCE-F-26-B", "Tu", 5, 1, "class", "Functional English", "Khansa Riaz", "B-004"),
    ("BCE-F-26-B", "Tu", 6, 1, "class", "Fehm-e-Quran-I", "Dr. Aftab Ahmad Rai", "B-106"),
    ("BCE-F-26-B", "We", 1, 1, "class", "Information and Communication Technologies (ICT)", "Aneeq Ahmad", "B-004"),
    ("BCE-F-26-B", "We", 2, 1, "class", "Calculus & Analytical Geometry", "Nida Tanveer", "B-006"),
    ("BCE-F-26-B", "We", 3, 2, "lab", "Computer Engineering Workshop", "CE-VFM4", "Signal & Image Processing Lab"),
    ("BCE-F-26-B", "We", 5, 1, "class", "Functional English", "Khansa Riaz", "B-001"),
    ("BCE-F-26-B", "Th", 1, 1, "class", "Advisory Class", "Basharat", "B-203"),
    ("BCE-F-26-B", "Th", 2, 1, "class", "Computer Programming", "Maryam Sabir", "B-001"),
    ("BCE-F-26-B", "Th", 3, 1, "lab", "Information and Communication Technologies (ICT) Laboratory", "Aneeq Ahmad", "Computer Systems Design Lab"),
    ("BCE-F-26-B", "Th", 4, 1, "class", "Applied Physics", "Syed Muneeb Abbas Hamdani", "B-005"),
    ("BCE-F-26-B", "Fr", 1, 1, "class", "Fehm-e-Quran-I", "Dr. Aftab Ahmad Rai", "B-006"),
    ("BCE-F-26-B", "Fr", 3, 2, "lab", "Computer Programming Laboratory", "Maryam Sabir", "Computer Lab-9 (B Block Ground Floor)"),

    # ---------------- BSE-F-26-A ----------------
    ("BSE-F-26-A", "Mo", 1, 2, "lab", "Information and Communication Technologies (ICT) Laboratory", "Alina Maryum", "Signal & Image Processing Lab"),
    ("BSE-F-26-A", "Mo", 3, 2, "lab", "Applied Physics Laboratory", "Sher Bano", "Physics Lab 2"),
    ("BSE-F-26-A", "Mo", 5, 1, "class", "Applied Physics", "Sher Bano", "B-001"),
    ("BSE-F-26-A", "Tu", 1, 2, "lab", "Computer Programming Laboratory", "Sidrish Ehsan", "Computer Systems Design Lab"),
    ("BSE-F-26-A", "Tu", 3, 1, "class", "Applied Physics", "Sher Bano", "B-005"),
    ("BSE-F-26-A", "Tu", 4, 1, "class", "Computer Programming", "Dr. Mumajjed Ul Mudassir", "B-005"),
    ("BSE-F-26-A", "We", 4, 1, "class", "Calculus & Analytical Geometry", "Dr. Shanza Behram", "B-006"),
    ("BSE-F-26-A", "We", 5, 1, "class", "Pakistan Studies", "Raham Maula", "B-004"),
    ("BSE-F-26-A", "We", 6, 1, "class", "Functional English", "Amina Khan", "B-006"),
    ("BSE-F-26-A", "Th", 2, 1, "class", "Information and Communication Technologies (ICT)", "Alina Maryum", "B-006"),
    ("BSE-F-26-A", "Th", 3, 1, "class", "Calculus & Analytical Geometry", "Dr. Shanza Behram", "B-005"),
    ("BSE-F-26-A", "Th", 4, 1, "class", "Functional English", "Amina Khan", "B-203"),
    ("BSE-F-26-A", "Th", 6, 1, "class", "Advisory Class", "Sidrish Ehsan", "B-004"),
    ("BSE-F-26-A", "Fr", 2, 1, "class", "Pakistan Studies", "Raham Maula", "B-005"),
    ("BSE-F-26-A", "Fr", 3, 1, "class", "Computer Programming", "Dr. Mumajjed Ul Mudassir", "B-001"),
    ("BSE-F-26-A", "Fr", 4, 1, "class", "Information and Communication Technologies (ICT)", "Alina Maryum", "B-004"),

    # ---------------- BSE-F-25-A ----------------
    ("BSE-F-25-A", "Tu", 1, 2, "lab", "Digital Logic Design Laboratory", "Alina Maryum", "Control & Instrumentation Lab"),
    ("BSE-F-25-A", "Tu", 3, 1, "class", "Database Management Systems", "Muhammad Naveed Khurshed", "B-004"),
    ("BSE-F-25-A", "Tu", 5, 2, "lab", "Data Structures and Algorithms Laboratory", "Sidrish Ehsan", "Computer Lab-21 (B Block Ground Floor)"),
    ("BSE-F-25-A", "We", 1, 1, "class", "Software Engineering", "Muhammad Atif Bajwa", "B-006"),
    ("BSE-F-25-A", "We", 3, 1, "class", "Probability Methods in Engineering", "Dr. Muhammad Zaheer", "B-006"),
    ("BSE-F-25-A", "We", 6, 1, "class", "Data Structures and Algorithms", "Sidrish Ehsan", "B-203"),
    ("BSE-F-25-A", "Th", 1, 1, "class", "Digital Logic Design", "Alina Maryum", "B-001"),
    ("BSE-F-25-A", "Th", 3, 1, "class", "Software Engineering", "Muhammad Atif Bajwa", "B-001"),
    ("BSE-F-25-A", "Th", 4, 1, "class", "Data Structures and Algorithms", "Sidrish Ehsan", "B-001"),
    ("BSE-F-25-A", "Th", 5, 1, "class", "Probability Methods in Engineering", "Dr. Muhammad Zaheer", "B-006"),
    ("BSE-F-25-A", "Th", 6, 1, "class", "Database Management Systems", "Muhammad Naveed Khurshed", "B-006"),
    ("BSE-F-25-A", "Fr", 1, 1, "lab", "Database Management Systems Laboratory", "Muhammad Naveed Khurshed", "Computer Lab-9 (B Block Ground Floor)"),
    ("BSE-F-25-A", "Fr", 2, 1, "class", "Digital Logic Design", "Alina Maryum", "B-004"),
    ("BSE-F-25-A", "Fr", 3, 1, "class", "Advisory Class", "Muhammad Naveed Khurshed", "B-006"),
]


def build_time_slots():
    rows = []
    for day_abbr, day_num in DAY_ABBR.items():
        for slot_num, (start, end) in SLOT_TIMES.items():
            rows.append({
                "slot_key": f"{day_abbr}{slot_num}",
                "day_of_week": day_num,
                "day_name": DAY_NAME[day_num],
                "start_time": start,
                "end_time": end,
                "slot_type": "morning" if int(start.split(":")[0]) < 12 else "afternoon",
            })
    return rows


def slot_key_range(day_abbr, start_slot, duration):
    return [f"{day_abbr}{s}" for s in range(start_slot, start_slot + duration)]


def main():
    # ---- rooms ----
    room_meta = {}  # code -> is_lab
    for e in ENTRIES:
        room_meta.setdefault(e[7], e[4] == "lab")
    room_rows = []
    for code, is_lab in sorted(room_meta.items()):
        room_rows.append({
            "code": code,
            "name": code,
            "room_type": "computer_lab" if is_lab else "lecture_room",
            "capacity": 45 if is_lab else 60,
            "building_code": "BLK-B",
        })
    with open(os.path.join(OUT, "rooms.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["code", "name", "room_type", "capacity", "building_code"])
        w.writeheader()
        w.writerows(room_rows)

    # ---- teachers ----
    teacher_names = sorted({e[6] for e in ENTRIES})
    teacher_rows = []
    for i, name in enumerate(teacher_names, start=1):
        designation = "professor" if name.lower().startswith("dr.") else (
            "visiting_faculty" if name in (
                "Awais Ali", "Nida Tanveer", "Hussain Mujtaba", "Khansa Riaz", "Sher Bano",
                "Raham Maula", "Amina Khan", "Aqib Rauf",
            ) else "assistant_professor"
        )
        dept = "EE" if name in ("Dr. Muhammad Zaheer", "Laraib", "Tauseef Ur Rehman") else "CE"
        teacher_rows.append({
            "employee_id": f"AU-T{i:03d}",
            "name": name,
            "email": name.lower().replace(" ", ".").replace(".dr", "dr").replace("-", "") + "@au.edu.pk",
            "department_code": dept,
            "designation": designation,
            "max_teaching_hours": 18,
            "max_lab_hours": 6,
        })
    with open(os.path.join(OUT, "teachers.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["employee_id", "name", "email", "department_code",
                                           "designation", "max_teaching_hours", "max_lab_hours"])
        w.writeheader()
        w.writerows(teacher_rows)

    # ---- time slots ----
    with open(os.path.join(OUT, "time_slots.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["slot_key", "day_of_week", "day_name", "start_time", "end_time", "slot_type"])
        w.writeheader()
        w.writerows(build_time_slots())

    # ---- sections / student groups ----
    section_rows = []
    for sec_code, (prog, year, letter, sem) in SECTIONS.items():
        section_rows.append({
            "section_code": sec_code,
            "program_code": prog,
            "batch_year": year,
            "section_name": letter,
            "semester_number": sem,
            "size": 45,
        })
    with open(os.path.join(OUT, "sections.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["section_code", "program_code", "batch_year",
                                           "section_name", "semester_number", "size"])
        w.writeheader()
        w.writerows(section_rows)

    # ---- courses (deduped by name+program) ----
    course_seen = {}
    for sec_code, day_abbr, start_slot, dur, kind, cname, teacher, room in ENTRIES:
        if cname in ("Advisory Class",):
            continue  # not a real course
        prog = SECTIONS[sec_code][0]
        sem = SECTIONS[sec_code][3]
        key = (cname, prog)
        has_lab = course_seen.get(key, {}).get("has_lab", False) or (kind == "lab")
        course_seen[key] = {"program_code": prog, "semester_number": sem, "has_lab": has_lab}
    course_rows = []
    for (cname, prog), meta in sorted(course_seen.items()):
        code = "".join(w[0] for w in cname.split() if w[0].isalnum()).upper()
        code = f"{prog[2:]}-{meta['semester_number']}{code[:3]}"
        course_rows.append({
            "code": code,
            "name": cname,
            "program_code": prog,
            "semester_number": meta["semester_number"],
            "credit_hours": 3,
            "course_type": "theory_lab" if meta["has_lab"] else "theory",
            "weekly_hours": 4 if meta["has_lab"] else 3,
        })
    with open(os.path.join(OUT, "courses.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["code", "name", "program_code", "semester_number",
                                           "credit_hours", "course_type", "weekly_hours"])
        w.writeheader()
        w.writerows(course_rows)

    course_code_lookup = {(r["name"], r["program_code"]): r["code"] for r in course_rows}

    # ---- course offerings (course x section x teacher) ----
    offering_seen = {}
    for sec_code, day_abbr, start_slot, dur, kind, cname, teacher, room in ENTRIES:
        if cname == "Advisory Class":
            continue
        prog = SECTIONS[sec_code][0]
        course_code = course_code_lookup[(cname, prog)]
        key = (course_code, sec_code)
        off = offering_seen.setdefault(key, {
            "course_code": course_code, "section_code": sec_code,
            "primary_teacher": None, "lab_teacher": None, "requires_lab": False,
        })
        if kind == "class" and off["primary_teacher"] is None:
            off["primary_teacher"] = teacher
        if kind == "lab":
            off["requires_lab"] = True
            off["lab_teacher"] = teacher
            if off["primary_teacher"] is None:
                off["primary_teacher"] = teacher
    with open(os.path.join(OUT, "course_offerings.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["course_code", "section_code", "primary_teacher",
                                           "lab_teacher", "requires_lab"])
        w.writeheader()
        w.writerows(offering_seen.values())

    # ---- schedule (ground-truth timetable entries, for seeding + GA comparison) ----
    schedule_rows = []
    for sec_code, day_abbr, start_slot, dur, kind, cname, teacher, room in ENTRIES:
        keys = slot_key_range(day_abbr, start_slot, dur)
        prog = SECTIONS[sec_code][0]
        course_code = course_code_lookup.get((cname, prog), "ADVISORY")
        for k in keys:
            schedule_rows.append({
                "section_code": sec_code,
                "slot_key": k,
                "course_code": course_code,
                "course_name": cname,
                "schedule_type": kind,
                "teacher": teacher,
                "room_code": room,
            })
    with open(os.path.join(OUT, "schedule.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["section_code", "slot_key", "course_code", "course_name",
                                           "schedule_type", "teacher", "room_code"])
        w.writeheader()
        w.writerows(schedule_rows)

    print(f"Rooms: {len(room_rows)}, Teachers: {len(teacher_rows)}, Sections: {len(section_rows)}, "
          f"Courses: {len(course_rows)}, Offerings: {len(offering_seen)}, Schedule rows: {len(schedule_rows)}")


if __name__ == "__main__":
    main()
