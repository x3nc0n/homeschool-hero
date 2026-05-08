from backend.routers.assignments import router as assignments_router
from backend.routers.auth import router as auth_router
from backend.routers.grades import router as grades_router
from backend.routers.grading import router as grading_router
from backend.routers.quizzes import router as quizzes_router
from backend.routers.students import router as students_router
from backend.routers.subjects import router as subjects_router
from backend.routers.submissions import router as submissions_router

__all__ = [
    "assignments_router",
    "auth_router",
    "grades_router",
    "grading_router",
    "quizzes_router",
    "students_router",
    "subjects_router",
    "submissions_router",
]
