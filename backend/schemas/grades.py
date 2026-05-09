from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.models.grade import GradedBy
from backend.validation import normalize_optional_text


class GradeCreate(BaseModel):
    submission_id: int = Field(gt=0)
    student_id: int = Field(gt=0)
    score: float = Field(ge=0)
    max_score: float = Field(gt=0)
    letter_grade: str | None = Field(default=None, max_length=4)
    notes: str | None = Field(default=None, max_length=4000)
    graded_by: GradedBy = GradedBy.human
    ai_confidence: float | None = Field(default=None, ge=0, le=1)

    @field_validator('letter_grade')
    @classmethod
    def validate_letter_grade(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().upper()
        if not normalized:
            return None
        return normalized

    @field_validator('notes')
    @classmethod
    def validate_notes(cls, value: str | None) -> str | None:
        return normalize_optional_text(value, field_name='Grade notes', max_length=4000)


class GradeUpdate(BaseModel):
    score: float = Field(ge=0)
    max_score: float = Field(gt=0)
    letter_grade: str | None = Field(default=None, max_length=4)
    notes: str | None = Field(default=None, max_length=4000)
    graded_by: GradedBy = GradedBy.human
    ai_confidence: float | None = Field(default=None, ge=0, le=1)

    @field_validator('letter_grade')
    @classmethod
    def validate_letter_grade(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().upper()
        if not normalized:
            return None
        return normalized

    @field_validator('notes')
    @classmethod
    def validate_notes(cls, value: str | None) -> str | None:
        return normalize_optional_text(value, field_name='Grade notes', max_length=4000)


class GradeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    submission_id: int
    student_id: int
    score: float
    max_score: float
    letter_grade: str | None
    notes: str | None
    graded_by: GradedBy
    ai_confidence: float | None
    created_at: datetime
    updated_at: datetime


class GradeAverageByStudent(BaseModel):
    student_id: int
    student_name: str
    subject_id: int
    subject_name: str
    average_percent: float


class GradeAverageBySubject(BaseModel):
    subject_id: int
    subject_name: str
    student_id: int
    student_name: str
    average_percent: float


class GradeHistoryItem(BaseModel):
    grade_id: int
    student_id: int
    student_name: str
    subject_id: int
    subject_name: str
    assignment_id: int
    assignment_title: str
    score: float
    max_score: float
    percent: float
    letter_grade: str | None
    graded_by: GradedBy
    created_at: datetime
