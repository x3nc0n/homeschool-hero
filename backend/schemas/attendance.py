from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.schemas.students import StudentRead
from backend.validation import normalize_optional_text


class AttendanceRecordEntry(BaseModel):
    model_config = ConfigDict(extra='forbid')

    student_id: int = Field(gt=0)
    is_instructional_day: bool = True
    instructional_hours: Decimal | None = Field(default=None, ge=0, le=24, max_digits=5, decimal_places=2)
    notes: str | None = Field(default=None, max_length=1000)

    @field_validator('notes')
    @classmethod
    def validate_notes(cls, value: str | None) -> str | None:
        return normalize_optional_text(value, field_name='Attendance notes', max_length=1000)


class AttendanceDailyUpsert(BaseModel):
    date: date
    records: list[AttendanceRecordEntry] = Field(min_length=1)

    @field_validator('records')
    @classmethod
    def validate_unique_students(cls, records: list[AttendanceRecordEntry]) -> list[AttendanceRecordEntry]:
        student_ids = [record.student_id for record in records]
        if len(student_ids) != len(set(student_ids)):
            raise ValueError('Each student may only appear once per daily attendance request')
        return records


class AttendanceHoursLog(BaseModel):
    model_config = ConfigDict(extra='forbid')

    student_id: int = Field(gt=0)
    date: date
    instructional_hours: Decimal = Field(ge=0, le=24, max_digits=5, decimal_places=2)
    notes: str | None = Field(default=None, max_length=1000)

    @field_validator('notes')
    @classmethod
    def validate_notes(cls, value: str | None) -> str | None:
        return normalize_optional_text(value, field_name='Attendance notes', max_length=1000)


class AttendanceRecordRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    family_id: int
    student_id: int
    date: date
    is_instructional_day: bool
    instructional_hours: Decimal | None
    notes: str | None
    student: StudentRead | None = None
    created_at: datetime
    updated_at: datetime


class AttendanceSummaryBucket(BaseModel):
    label: str
    start_date: date
    end_date: date
    total_records: int
    instructional_days: int
    non_instructional_days: int
    attendance_rate: float
    total_hours: Decimal | None


class AttendanceStateProfileRead(BaseModel):
    state_code: str
    state_name: str
    required_days: int | None
    required_hours: int | None
    show_hours_ui: bool


class AttendanceStateProfileProgress(BaseModel):
    required_days: int | None
    days_remaining: int | None
    required_hours: int | None
    hours_remaining: Decimal | None


class AttendanceSummaryResponse(BaseModel):
    student_id: int
    school_year_id: int | None = None
    period: Literal['day', 'week', 'term', 'year']
    total_records: int
    instructional_days: int
    non_instructional_days: int
    attendance_rate: float
    total_hours: Decimal | None
    buckets: list[AttendanceSummaryBucket]
    state_profile_progress: AttendanceStateProfileProgress | None = None


class AttendanceHoursResponse(BaseModel):
    student_id: int
    school_year_id: int
    total_hours: Decimal
    recorded_days: int
    average_hours_per_day: float
