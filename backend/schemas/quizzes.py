from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class QuizQuestion(BaseModel):
    type: Literal["multiple_choice", "short_answer", "true_false"]
    prompt: str = Field(min_length=1)
    options: list[str] | None = None
    correct_answer: Any
    points: float = Field(default=1.0, gt=0)


class QuizCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    subject_id: int
    questions: list[QuizQuestion] = Field(min_length=1)


class QuizUpdate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    subject_id: int
    questions: list[QuizQuestion] = Field(min_length=1)


class QuizRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    subject_id: int
    questions: list[dict[str, Any]]
    created_at: datetime


class QuizAttemptCreate(BaseModel):
    student_id: int
    answers: list[Any]


class QuizAttemptRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    quiz_id: int
    student_id: int
    answers: list[Any]
    score: float
    max_score: float
    completed_at: datetime
