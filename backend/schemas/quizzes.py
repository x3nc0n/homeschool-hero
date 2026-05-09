from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from backend.validation import normalize_text


class QuizQuestion(BaseModel):
    type: Literal["multiple_choice", "short_answer", "true_false"]
    prompt: str = Field(min_length=1, max_length=1000)
    options: list[str] | None = Field(default=None, max_length=10)
    correct_answer: Any
    points: float = Field(default=1.0, gt=0)

    @field_validator('prompt')
    @classmethod
    def validate_prompt(cls, value: str) -> str:
        return normalize_text(value, field_name='Question prompt')

    @field_validator('options')
    @classmethod
    def validate_options(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        normalized = [normalize_text(item, field_name='Question option') for item in value]
        if not normalized:
            raise ValueError('Question options are required')
        return normalized

    @model_validator(mode='after')
    def validate_question_shape(self) -> 'QuizQuestion':
        if self.type == 'multiple_choice' and not self.options:
            raise ValueError('Multiple choice questions require options')
        if self.type != 'multiple_choice':
            self.options = None
        return self


class QuizCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    subject_id: int = Field(gt=0)
    questions: list[QuizQuestion] = Field(min_length=1)

    @field_validator('title')
    @classmethod
    def validate_title(cls, value: str) -> str:
        return normalize_text(value, field_name='Quiz title')


class QuizUpdate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    subject_id: int = Field(gt=0)
    questions: list[QuizQuestion] = Field(min_length=1)

    @field_validator('title')
    @classmethod
    def validate_title(cls, value: str) -> str:
        return normalize_text(value, field_name='Quiz title')


class QuizRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    subject_id: int
    questions: list[dict[str, Any]]
    created_at: datetime


class QuizAttemptCreate(BaseModel):
    student_id: int = Field(gt=0)
    answers: list[Any] = Field(max_length=100)


class QuizAttemptRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    quiz_id: int
    student_id: int
    answers: list[Any]
    score: float
    max_score: float
    completed_at: datetime
