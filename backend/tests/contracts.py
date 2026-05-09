from __future__ import annotations

from pathlib import Path
from typing import Any

API_PREFIX = "/api"

AUTH = {
    "login": f"{API_PREFIX}/auth/login",
    "logout": f"{API_PREFIX}/auth/logout",
    "me": f"{API_PREFIX}/auth/me",
}

STUDENTS = {
    "collection": f"{API_PREFIX}/students",
    "detail": f"{API_PREFIX}/students/{{student_id}}",
}

SUBJECTS = {
    "collection": f"{API_PREFIX}/subjects",
    "detail": f"{API_PREFIX}/subjects/{{subject_id}}",
}

ASSIGNMENTS = {
    "collection": f"{API_PREFIX}/assignments",
    "detail": f"{API_PREFIX}/assignments/{{assignment_id}}",
    "status": f"{API_PREFIX}/assignments/{{assignment_id}}/status",
}

SUBMISSIONS = {
    "collection": f"{API_PREFIX}/submissions",
    "upload": f"{API_PREFIX}/submissions",
    "detail": f"{API_PREFIX}/submissions/{{submission_id}}",
}

GRADES = {
    "collection": f"{API_PREFIX}/grades",
    "detail": f"{API_PREFIX}/grades/{{grade_id}}",
    "history": f"{API_PREFIX}/grades/history",
    "student_averages": f"{API_PREFIX}/grades/averages/student/{{student_id}}",
    "subject_averages": f"{API_PREFIX}/grades/averages/subject/{{subject_id}}",
}

QUIZZES = {
    "collection": f"{API_PREFIX}/quizzes",
    "detail": f"{API_PREFIX}/quizzes/{{quiz_id}}",
    "attempts": f"{API_PREFIX}/quizzes/{{quiz_id}}/attempts",
    "attempts_list": f"{API_PREFIX}/quizzes/{{quiz_id}}/attempts",
}

GRADING = {
    "review_queue": f"{API_PREFIX}/grading/review-queue",
    "approve": f"{API_PREFIX}/grading/review-queue/{{job_id}}/approve",
    "reject": f"{API_PREFIX}/grading/review-queue/{{job_id}}/reject",
}

SERVICE_CANDIDATES = {
    "ocr": ("extract_text_from_image", "extract_text", "perform_ocr"),
    "ai_grade": ("grade_submission_text", "grade_text", "grade_submission", "grade_ocr_text"),
    "worker": ("process_grading_job", "process_job", "handle_job"),
}

VALIDATION_STATUS_CODES = {400, 422}

UPLOADS_DIR = Path(__file__).resolve().parents[1] / ".pytest-state" / "uploads-test"


def student_payload(name: str = "Ada Lovelace") -> dict[str, Any]:
    return {"name": name}


def subject_payload(name: str = "Math", color: str = "#2563eb") -> dict[str, Any]:
    return {"name": name, "color": color}


def assignment_payload(subject_id: int | str) -> dict[str, Any]:
    return {
        "title": "Fractions Worksheet",
        "subject_id": subject_id,
        "description": "Complete problems 1-10 using the answer key.",
        "due_date": "2026-05-15",
        "status": "pending",
    }


def grade_payload(submission_id: int | str, student_id: int | str) -> dict[str, Any]:
    return {
        "submission_id": submission_id,
        "student_id": student_id,
        "score": 88,
        "max_score": 100,
        "letter_grade": "B+",
        "notes": "Strong work with one arithmetic mistake.",
        "graded_by": "human",
    }


def quiz_payload(subject_id: int | str) -> dict[str, Any]:
    return {
        "title": "Fractions Check-In",
        "subject_id": subject_id,
        "questions": [
            {
                "type": "multiple_choice",
                "prompt": "What is 1/2 + 1/4?",
                "options": ["1/4", "1/2", "3/4", "1"],
                "correct_answer": "3/4",
            },
            {
                "type": "short_answer",
                "prompt": "Simplify 6/8.",
                "correct_answer": "3/4",
            },
        ],
    }


def quiz_attempt_payload(student_id: int | str) -> dict[str, Any]:
    return {
        "student_id": student_id,
        "answers": ["3/4", "3/4"],
    }
