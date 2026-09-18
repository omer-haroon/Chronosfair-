from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'users', views.UserViewSet)
router.register(r'universities', views.UniversityViewSet)
router.register(r'faculties', views.FacultyViewSet)
router.register(r'departments', views.DepartmentViewSet)
router.register(r'programs', views.ProgramViewSet)
router.register(r'semesters', views.SemesterViewSet)
router.register(r'academic-sessions', views.AcademicSessionViewSet)
router.register(r'batches', views.BatchViewSet)
router.register(r'student-groups', views.StudentGroupViewSet)
router.register(r'buildings', views.BuildingViewSet)
router.register(r'room-types', views.RoomTypeViewSet)
router.register(r'rooms', views.RoomViewSet)
router.register(r'room-availability', views.RoomAvailabilityViewSet)
router.register(r'time-slots', views.TimeSlotViewSet)
router.register(r'holidays', views.HolidayViewSet)
router.register(r'academic-calendar', views.AcademicCalendarViewSet)
router.register(r'teachers', views.TeacherViewSet)
router.register(r'teacher-preferences', views.TeacherPreferenceViewSet)
router.register(r'invigilation-preferences', views.InvigilationPreferenceViewSet)
router.register(r'teacher-leaves', views.TeacherLeaveViewSet)
router.register(r'courses', views.CourseViewSet)
router.register(r'course-offerings', views.CourseOfferingViewSet)
router.register(r'course-offering-groups', views.CourseOfferingGroupViewSet)
router.register(r'schedules', views.ScheduleViewSet)
router.register(r'exams', views.ExamViewSet)
router.register(r'invigilation-duties', views.InvigilationDutyViewSet)
router.register(r'ga-runs', views.GARunViewSet)
router.register(r'fairness-records', views.FairnessRecordViewSet)
router.register(r'fairness-snapshots', views.GlobalFairnessSnapshotViewSet)
router.register(r'teacher-workloads', views.TeacherWorkloadViewSet)
router.register(r'student-conflicts', views.StudentConflictViewSet)
router.register(r'constraint-violations', views.ConstraintViolationViewSet)
router.register(r'repair-history', views.RepairHistoryViewSet)
router.register(r'ledger', views.LedgerViewSet)
router.register(r'constraints-catalog', views.ConstraintCatalogViewSet)

urlpatterns = [
    path('import-csv/', views.ImportCSVView.as_view(), name='import-csv'),
    path('', include(router.urls)),
]
