from backend.routers.assignments import router as assignments_router
from backend.routers.audit import router as audit_router
from backend.routers.auth import router as auth_router
from backend.routers.calendar import router as calendar_router
from backend.routers.curriculum import router as curriculum_router
from backend.routers.dashboard import router as dashboard_router
from backend.routers.grades import router as grades_router
from backend.routers.grading import router as grading_router
from backend.routers.invitations import router as invitations_router
from backend.routers.quizzes import router as quizzes_router
from backend.routers.schedule import router as schedule_router
from backend.routers.students import router as students_router
from backend.routers.subjects import router as subjects_router
from backend.routers.submissions import router as submissions_router

__all__ = [
    'assignments_router',
    'audit_router',
    'auth_router',
    'calendar_router',
    'curriculum_router',
    'dashboard_router',
    'grades_router',
    'grading_router',
    'invitations_router',
    'quizzes_router',
    'schedule_router',
    'students_router',
    'subjects_router',
    'submissions_router',
]
