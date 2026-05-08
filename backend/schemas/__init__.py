from backend.schemas.assignments import AssignmentCreate, AssignmentRead, AssignmentStatusUpdate, AssignmentUpdate
from backend.schemas.auth import LoginRequest, LoginResponse, SessionResponse
from backend.schemas.grades import (
    GradeAverageByStudent,
    GradeAverageBySubject,
    GradeCreate,
    GradeHistoryItem,
    GradeRead,
    GradeUpdate,
)
from backend.schemas.quizzes import QuizAttemptCreate, QuizAttemptRead, QuizCreate, QuizRead, QuizUpdate
from backend.schemas.students import StudentCreate, StudentRead, StudentUpdate
from backend.schemas.subjects import SubjectCreate, SubjectRead, SubjectUpdate
from backend.schemas.submissions import SubmissionRead

__all__ = [
    "AssignmentCreate",
    "AssignmentRead",
    "AssignmentStatusUpdate",
    "AssignmentUpdate",
    "GradeAverageByStudent",
    "GradeAverageBySubject",
    "GradeCreate",
    "GradeHistoryItem",
    "GradeRead",
    "GradeUpdate",
    "LoginRequest",
    "LoginResponse",
    "QuizAttemptCreate",
    "QuizAttemptRead",
    "QuizCreate",
    "QuizRead",
    "QuizUpdate",
    "SessionResponse",
    "StudentCreate",
    "StudentRead",
    "StudentUpdate",
    "SubjectCreate",
    "SubjectRead",
    "SubjectUpdate",
    "SubmissionRead",
]
