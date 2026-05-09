from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.models.report_card import ReportCardStatus
from backend.schemas.students import StudentRead
from backend.schemas.subjects import SubjectRead
from backend.validation import normalize_optional_text


class ReportCardGenerateRequest(BaseModel):
    student_id: int = Field(gt=0)
    grading_period_id: int = Field(gt=0)
    notes: str | None = Field(default=None, max_length=2000)

    @field_validator('notes')
    @classmethod
    def validate_notes(cls, value: str | None) -> str | None:
        return normalize_optional_text(value, field_name='Report card notes', max_length=2000)


class ReportCardEntryUpdate(BaseModel):
    entry_id: int = Field(gt=0)
    teacher_comments: str | None = Field(default=None, max_length=2000)

    @field_validator('teacher_comments')
    @classmethod
    def validate_teacher_comments(cls, value: str | None) -> str | None:
        return normalize_optional_text(value, field_name='Teacher comments', max_length=2000)


class ReportCardUpdateRequest(BaseModel):
    notes: str | None = Field(default=None, max_length=2000)
    status: ReportCardStatus | None = None
    entries: list[ReportCardEntryUpdate] = Field(default_factory=list)

    @field_validator('notes')
    @classmethod
    def validate_notes(cls, value: str | None) -> str | None:
        return normalize_optional_text(value, field_name='Report card notes', max_length=2000)


class ReportCardEntryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    report_card_id: int
    subject_id: int
    letter_grade: str | None
    percentage: float | None
    gpa_points: float | None
    attendance_summary: dict[str, Any]
    teacher_comments: str | None
    category_breakdown: dict[str, float]
    subject: SubjectRead | None = None


class ReportCardSummaryRead(BaseModel):
    id: int
    family_id: int
    student_id: int
    school_year_id: int
    grading_period_id: int
    generated_at: datetime
    generated_by_user_id: int | None
    generated_by_name: str | None = None
    status: ReportCardStatus
    notes: str | None
    student_name: str
    school_year_name: str
    grading_period_name: str
    entry_count: int
    gpa: float | None
    overall_percentage: float | None


class ReportCardRead(ReportCardSummaryRead):
    student: StudentRead | None = None
    entries: list[ReportCardEntryRead]
