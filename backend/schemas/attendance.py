from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator, field_validator

from backend.models import AttendanceStatus
from backend.schemas.students import StudentRead
from backend.validation import normalize_optional_text, normalize_text


class AttendanceRecordEntry(BaseModel):
    student_id: int = Field(gt=0)
    status: AttendanceStatus = AttendanceStatus.present
    check_in_time: time | None = None
    check_out_time: time | None = None
    instructional_hours: Decimal | None = Field(default=None, ge=0, le=24, max_digits=5, decimal_places=2)
    notes: str | None = Field(default=None, max_length=1000)

    @field_validator('notes')
    @classmethod
    def validate_notes(cls, value: str | None) -> str | None:
        return normalize_optional_text(value, field_name='Attendance notes', max_length=1000)

    @model_validator(mode='after')
    def validate_times(self):
        if self.check_in_time and self.check_out_time and self.check_out_time < self.check_in_time:
            raise ValueError('check_out_time must be on or after check_in_time')
        return self


class AttendanceDailyUpsert(BaseModel):
    date: date
    records: list[AttendanceRecordEntry] = Field(min_length=1)

    @model_validator(mode='after')
    def validate_unique_students(self):
        student_ids = [record.student_id for record in self.records]
        if len(student_ids) != len(set(student_ids)):
            raise ValueError('Each student may only appear once per daily attendance request')
        return self


class AttendanceHoursLog(BaseModel):
    student_id: int = Field(gt=0)
    date: date
    instructional_hours: Decimal = Field(ge=0, le=24, max_digits=5, decimal_places=2)
    check_in_time: time | None = None
    check_out_time: time | None = None
    notes: str | None = Field(default=None, max_length=1000)

    @field_validator('notes')
    @classmethod
    def validate_notes(cls, value: str | None) -> str | None:
        return normalize_optional_text(value, field_name='Attendance notes', max_length=1000)

    @model_validator(mode='after')
    def validate_times(self):
        if self.check_in_time and self.check_out_time and self.check_out_time < self.check_in_time:
            raise ValueError('check_out_time must be on or after check_in_time')
        return self


class AttendanceExcuseCreate(BaseModel):
    attendance_record_id: int = Field(gt=0)
    reason: str = Field(min_length=1, max_length=255)

    @field_validator('reason')
    @classmethod
    def validate_reason(cls, value: str) -> str:
        return normalize_text(value, field_name='Excuse reason')


class AttendanceExcuseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    family_id: int
    attendance_record_id: int
    reason: str
    document_path: str | None
    document_url: str | None = None
    approved_by_user_id: int | None
    approved_at: datetime | None
    created_at: datetime
    updated_at: datetime


class AttendanceRecordRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    family_id: int
    student_id: int
    date: date
    status: AttendanceStatus
    check_in_time: time | None
    check_out_time: time | None
    instructional_hours: Decimal
    notes: str | None
    student: StudentRead | None = None
    excuse: AttendanceExcuseRead | None = None
    created_at: datetime
    updated_at: datetime


class AttendanceSummaryBucket(BaseModel):
    label: str
    start_date: date
    end_date: date
    total_records: int
    present: int
    absent: int
    tardy: int
    excused: int
    attendance_rate: float
    total_hours: Decimal


class AttendanceSummaryResponse(BaseModel):
    student_id: int
    school_year_id: int | None = None
    period: Literal['day', 'week', 'term', 'year']
    total_records: int
    present: int
    absent: int
    tardy: int
    excused: int
    attendance_rate: float
    total_hours: Decimal
    buckets: list[AttendanceSummaryBucket]


class AttendanceHoursResponse(BaseModel):
    student_id: int
    school_year_id: int
    total_hours: Decimal
    recorded_days: int
    average_hours_per_day: float
