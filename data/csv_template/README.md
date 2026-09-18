# CSV Data Template — what to bring back from the university

11 files, all plain CSV with a header row exactly as shown. This folder has
a filled two-department example (CE + SE) you can copy and overwrite.
Column names must match exactly — the import command reads them by name.

Import with:
```bash
python manage.py import_csv_data --dir data/csv_template --session "Fall 2026"
```
(point `--dir` at your own copy once you've filled it in with real data)

---

## 1. university.csv — exactly one row
| column | example | notes |
|---|---|---|
| code | AU | short unique code |
| name | Air University | |
| location | Islamabad | |

## 2. faculties.csv — one row per faculty
| column | example |
|---|---|
| code | ENG |
| name | Faculty of Engineering |
| university_code | AU — must match university.csv |

## 3. departments.csv — one row **per department** (this is where "2 departments" goes — just add more rows for more)
| column | example |
|---|---|
| code | CE |
| name | Computer Engineering |
| faculty_code | ENG — must match faculties.csv |

## 4. programs.csv — one row per degree program
| column | example | notes |
|---|---|---|
| code | BSCE | referenced by sections.csv and courses.csv |
| name | BS Computer Engineering | |
| department_code | CE — must match departments.csv | |
| degree_type | bs | one of: `bs`, `ms`, `phd`, `diploma`, `certificate` |
| duration_semesters | 8 | |

## 5. buildings.csv — one row per building
| column | example |
|---|---|
| code | BLK-B |
| name | Block B |
| floors | 3 |
| university_code | AU |

## 6. rooms.csv — every room that can be scheduled
| column | example | notes |
|---|---|---|
| code | R-101 | unique |
| name | R-101 | |
| room_type | lecture_room | free text, but must be consistent — use the same string for every lecture room and every lab (e.g. `lecture_room` / `computer_lab`) |
| capacity | 60 | **must be ≥ the largest section size that will sit in it** — this is what caused the earlier "no valid room" bug when capacity was smaller than section size |
| building_code | BLK-B | must match buildings.csv |

## 7. time_slots.csv — every bookable period in the week
| column | example |
|---|---|
| slot_key | Mo1 (any unique key) |
| day_of_week | 1 = Monday … 7 = Sunday |
| day_name | Monday |
| start_time | 08:00 |
| end_time | 09:20 |
| slot_type | morning / afternoon / evening |

## 8. teachers.csv — every teacher, both departments together
| column | example | notes |
|---|---|---|
| employee_id | T001 | |
| name | Dr. Sara Ahmed | used as the lookup key elsewhere — keep it unique |
| email | sara.ahmed@uni.edu.pk | |
| department_code | CE | must match departments.csv |
| designation | assistant_professor | free text |
| max_teaching_hours | 18 | weekly cap, used by fairness scoring |
| max_lab_hours | 6 | weekly cap for lab supervision |

## 9. sections.csv — every section/group of students that needs its own timetable
| column | example | notes |
|---|---|---|
| section_code | CE-1A | unique key, used by course_offerings.csv |
| program_code | BSCE | must match programs.csv |
| batch_year | 2026 | intake year |
| section_name | A | |
| semester_number | 1 | which semester this section is currently in |
| size | 40 | **actual headcount** — drives room-capacity matching |

## 10. courses.csv — the course catalog
| column | example | notes |
|---|---|---|
| code | CE101 | unique |
| name | Intro to Programming | |
| program_code | BSCE | must match programs.csv |
| semester_number | 1 | |
| credit_hours | 3 | |
| course_type | theory | one of: `theory`, `lab`, `theory_lab`, `project`, `thesis`, `seminar` — **`theory_lab` is what makes a course eligible for lab scheduling** |
| weekly_hours | 3 | how many 1-slot sessions per week |

## 11. course_offerings.csv — which course, which section, which teacher, this semester
| column | example | notes |
|---|---|---|
| course_code | CE101 | must match courses.csv |
| section_code | CE-1A | must match sections.csv |
| primary_teacher | Dr. Sara Ahmed | must match a name in teachers.csv |
| lab_teacher | Dr. Kamran Aziz | optional — leave blank to default to the primary teacher |
| requires_lab | True | **exactly** `True` or `False` — this is the second (and final) switch that makes a lab session get scheduled, alongside `course_type=theory_lab` on the course itself |

---

## Labs — how to make sure they actually appear

A course offering only gets a **lab session** in the generated timetable when
**both** of these are true at once:
1. `courses.csv`: that course's `course_type` = `theory_lab`
2. `course_offerings.csv`: that offering's `requires_lab` = `True`

If either one is missing, the GA only schedules the theory class — this is
very likely why labs "weren't showing up" so far, if the earlier dataset was
missing one of the two flags on some courses. The dashboard's Course
Timetable page now marks lab sessions with a green **LAB** tag so you can
confirm at a glance once you re-import.

## Tuning for a bigger, two-department dataset

Once the real dataset is loaded, the search space (offerings × time slots ×
rooms) is a lot bigger than the 14-offering test set. A few knobs to raise
together, roughly in this order, when fitness plateaus below where you want
it:

1. **Generations** first — 200 → 400–600. Cheapest lever, watch `converged_at`
   in the GA Runs page; if it's still climbing near the end, generations was
   the bottleneck.
2. **Population** next — 60 → 120–150. Helps more when there are many
   offerings competing for the same few big lecture halls.
3. **Elitism / tournament size** — leave at the defaults (4 / 3) unless
   convergence is premature (fitness flatlines very early); then lower
   tournament size slightly to keep more diversity.
4. Run it **per department** instead of the whole university at once
   (`--department` on `run_course_ga` / the department field on the API
   call) if the combined run's fitness is worse than running each
   department separately — smaller independent problems are easier for a GA
   to solve well, and two departments rarely share rooms/teachers anyway.

All three GA commands accept `--population`, `--generations`, and
`--mutation-rate`; the dashboard's "Run GA" panels expose the same three.
