from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from backend.models.assignment import (
    AssignmentCategory,
    AssignmentRecurrence,
    AssignmentStatus,
    AssignmentTargetStatus,
)
from backend.schemas.calendar import GradingPeriodRead
from backend.schemas.students import StudentRead
from backend.schemas.subjects import SubjectRead
from backend.validation import normalize_optional_text, normalize_text


def _normalize_attachments(value: list[str] | None) -> list[str]:
    if not value:
        return []
    normalized: list[str] = []
    for item in value:
        candidate = normalize_text(item, field_name='Assignment attachment path')
        normalized.append(candidate)
    return normalized


class AssignmentTargetWrite(BaseModel):
    student_id: int = Field(gt=0)
    due_date: datetime | None = None
    status: AssignmentTargetStatus = AssignmentTargetStatus.assigned


class AnswerKeyQuestion(BaseModel):
    question_number: str = Field(min_length=1, max_length=64)
    correct_answer: str = Field(min_length=1, max_length=2000)
    points: float = Field(default=1.0, ge=0)
    partial_credit_rules: str | None = Field(default=None, max_length=2000)

    @field_validator('question_number', 'correct_answer')
    @classmethod
    def validate_answer_key_text(cls, value: str) -> str:
        return normalize_text(value, field_name='Answer key value')

    @field_validator('partial_credit_rules')
    @classmethod
    def validate_partial_credit_rules(cls, value: str | None) -> str | None:
        return normalize_optional_text(value, field_name='Answer key partial credit rules', max_length=2000)


class AnswerKeyUpsert(BaseModel):
    questions: list[AnswerKeyQuestion] = Field(default_factory=list)


class AnswerKeyRead(AnswerKeyUpsert):
    model_config = ConfigDict(from_attributes=True)

    id: int
    assignment_id: int
    family_id: int
    created_at: datetime
    updated_at: datetime


class AssignmentBase(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    subject_id: int = Field(gt=0)
    description: str | None = Field(default=None, max_length=4000)
    due_date: datetime | None = None
    status: AssignmentStatus = AssignmentStatus.pending
    category: AssignmentCategory = AssignmentCategory.homework
    grading_period_id: int | None = Field(default=None, gt=0)
    weight: float = Field(default=1.0, ge=0)
    max_score: float = Field(default=100.0, gt=0)
    recurrence: AssignmentRecurrence = AssignmentRecurrence.none
    recurrence_end_date: date | None = None
    rubric_description: str | None = Field(default=None, max_length=4000)
    attachments: list[str] = Field(default_factory=list)
    lesson_plan_id: int | None = Field(default=None, gt=0)
    targets: list[AssignmentTargetWrite] | None = None

    @field_validator('title')
    @classmethod
    def validate_title(cls, value: str) -> str:
        return normalize_text(value, field_name='Assignment title')

    @field_validator('description')
    @classmethod
    def validate_description(cls, value: str | None) -> str | None:
        return normalize_optional_text(value, field_name='Assignment description', max_length=4000)

    @field_validator('rubric_description')
    @classmethod
    def validate_rubric_description(cls, value: str | None) -> str | None:
        return normalize_optional_text(value, field_name='Assignment rubric description', max_length=4000)

    @field_validator('attachments')
    @classmethod
    def validate_attachments(cls, value: list[str]) -> list[str]:
        return _normalize_attachments(value)

    @model_validator(mode='after')
    def validate_recurrence(self):
        if self.recurrence == AssignmentRecurrence.none:
            return self
        if self.due_date is None:
            raise ValueError('due_date is required when recurrence is enabled')
        if self.recurrence_end_date is None:
            raise ValueError('recurrence_end_date is required when recurrence is enabled')
        if self.recurrence_end_date < self.due_date.date():
            raise ValueError('recurrence_end_date must be on or after due_date')
        return self


class AssignmentCreate(AssignmentBase):
    pass


class AssignmentUpdate(AssignmentBase):
    pass


class AssignmentStatusUpdate(BaseModel):
    status: AssignmentStatus


class AssignmentTargetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    assignment_id: int
    student_id: int
    due_date: datetime | None
    status: AssignmentTargetStatus
    completed_at: datetime | None
    student: StudentRead | None = None
    created_at: datetime
    updated_at: datetime


class AssignmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    subject_id: int
    description: str | None
    due_date: datetime | None
    status: AssignmentStatus
    category: AssignmentCategory
    grading_period_id: int | None
    weight: float
    max_score: float
    recurrence: AssignmentRecurrence
    recurrence_end_date: date | None
    rubric_description: str | None
    attachments: list[str] = Field(default_factory=list)
    lesson_plan_id: int | None
    status_history: list[dict[str, Any]] = Field(default_factory=list)
    answer_key: AnswerKeyRead | None = None
    subject: SubjectRead | None = None
    grading_period: GradingPeriodRead | None = None
    targets: list[AssignmentTargetRead] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class AssignmentListResponse(BaseModel):
    items: list[AssignmentRead]
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1)
    total_pages: int = Field(ge=0)
