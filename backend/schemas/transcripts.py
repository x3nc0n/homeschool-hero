from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.models.transcript import TranscriptStatus
from backend.schemas.students import StudentRead
from backend.validation import normalize_optional_text, normalize_text


class TranscriptGenerateRequest(BaseModel):
    student_id: int = Field(gt=0)
    notes: str | None = Field(default=None, max_length=4000)

    @field_validator('notes')
    @classmethod
    def validate_notes(cls, value: str | None) -> str | None:
        return normalize_optional_text(value, field_name='Transcript notes', max_length=4000)


class TranscriptEntryUpdate(BaseModel):
    entry_id: int = Field(gt=0)
    credits: float | None = Field(default=None, ge=0, le=99)
    is_honors: bool | None = None
    is_ap: bool | None = None
    notes: str | None = Field(default=None, max_length=2000)
    subject_name: str | None = Field(default=None, min_length=1, max_length=120)

    @field_validator('notes')
    @classmethod
    def validate_notes(cls, value: str | None) -> str | None:
        return normalize_optional_text(value, field_name='Transcript entry notes', max_length=2000)

    @field_validator('subject_name')
    @classmethod
    def validate_subject_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return normalize_text(value, field_name='Transcript subject name')


class TranscriptUpdateRequest(BaseModel):
    notes: str | None = Field(default=None, max_length=4000)
    status: TranscriptStatus | None = None
    entries: list[TranscriptEntryUpdate] = Field(default_factory=list)

    @field_validator('notes')
    @classmethod
    def validate_notes(cls, value: str | None) -> str | None:
        return normalize_optional_text(value, field_name='Transcript notes', max_length=4000)


class TranscriptEntryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    transcript_id: int
    school_year_id: int
    school_year_name: str
    subject_id: int
    subject_name: str
    credits: float
    letter_grade: str | None
    gpa_points: float | None
    weighted_gpa_points: float | None = None
    is_honors: bool
    is_ap: bool
    notes: str | None


class TranscriptSummaryRead(BaseModel):
    id: int
    family_id: int
    student_id: int
    generated_at: datetime
    generated_by_user_id: int | None
    generated_by_name: str | None = None
    status: TranscriptStatus
    cumulative_gpa: float | None
    weighted_gpa: float | None
    total_credits: float
    notes: str | None
    student_name: str
    entry_count: int


class TranscriptRead(TranscriptSummaryRead):
    student: StudentRead | None = None
    class_rank: int | None = None
    class_size: int | None = None
    honors_weight_bonus: float
    ap_weight_bonus: float
    entries: list[TranscriptEntryRead]
