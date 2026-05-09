from __future__ import annotations

from datetime import date, datetime, time
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from backend.models.schedule import ScheduleOverrideType
from backend.validation import normalize_optional_text, normalize_text


class ScheduleTimeRangeModel(BaseModel):
    @model_validator(mode='after')
    def validate_time_range(self):
        if self.start_time >= self.end_time:
            raise ValueError('start_time must be earlier than end_time')
        return self


class ScheduleCreate(BaseModel):
    student_id: int = Field(gt=0)
    school_year_id: int = Field(gt=0)
    name: str = Field(min_length=1, max_length=120)

    @field_validator('name')
    @classmethod
    def validate_name(cls, value: str) -> str:
        return normalize_text(value, field_name='Schedule name')


class ScheduleUpdate(ScheduleCreate):
    pass


class ScheduleBlockCreate(ScheduleTimeRangeModel):
    subject_id: int = Field(gt=0)
    day_of_week: int = Field(ge=0, le=6)
    start_time: time
    end_time: time
    location: str | None = Field(default=None, max_length=160)
    notes: str | None = Field(default=None, max_length=1000)

    @field_validator('location')
    @classmethod
    def validate_location(cls, value: str | None) -> str | None:
        return normalize_optional_text(value, field_name='Schedule location', max_length=160)

    @field_validator('notes')
    @classmethod
    def validate_notes(cls, value: str | None) -> str | None:
        return normalize_optional_text(value, field_name='Schedule notes', max_length=1000)


class ScheduleBlockUpdate(ScheduleBlockCreate):
    pass


class ScheduleOverrideCreate(BaseModel):
    schedule_id: int = Field(gt=0)
    date: date
    original_block_id: int | None = Field(default=None, gt=0)
    override_type: ScheduleOverrideType
    subject_id: int | None = Field(default=None, gt=0)
    start_time: time | None = None
    end_time: time | None = None
    reason: str = Field(min_length=1, max_length=1000)

    @field_validator('reason')
    @classmethod
    def validate_reason(cls, value: str) -> str:
        return normalize_text(value, field_name='Override reason')

    @model_validator(mode='after')
    def validate_override(self):
        if self.override_type in {ScheduleOverrideType.cancel, ScheduleOverrideType.reschedule} and self.original_block_id is None:
            raise ValueError('original_block_id is required for cancel and reschedule overrides')
        if self.override_type == ScheduleOverrideType.add and self.subject_id is None:
            raise ValueError('subject_id is required for add overrides')
        if self.override_type in {ScheduleOverrideType.add, ScheduleOverrideType.reschedule}:
            if self.start_time is None or self.end_time is None:
                raise ValueError('start_time and end_time are required for add and reschedule overrides')
            if self.start_time >= self.end_time:
                raise ValueError('start_time must be earlier than end_time')
        if self.override_type == ScheduleOverrideType.cancel:
            self.subject_id = None
            self.start_time = None
            self.end_time = None
        return self


class ScheduleSubjectRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    color: str


class ScheduleStudentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class ScheduleSchoolYearRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    start_date: date
    end_date: date
    is_active: bool


class ScheduleBlockRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    schedule_id: int
    subject_id: int
    day_of_week: int
    start_time: time
    end_time: time
    location: str | None
    notes: str | None
    subject: ScheduleSubjectRead
    created_at: datetime
    updated_at: datetime


class ScheduleOverrideRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    schedule_id: int
    date: date
    original_block_id: int | None
    override_type: ScheduleOverrideType
    subject_id: int | None
    start_time: time | None
    end_time: time | None
    reason: str
    subject: ScheduleSubjectRead | None = None
    created_at: datetime
    updated_at: datetime


class ScheduleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    family_id: int
    student_id: int
    school_year_id: int
    name: str
    student: ScheduleStudentRead
    school_year: ScheduleSchoolYearRead
    created_at: datetime
    updated_at: datetime


class ScheduleDetail(ScheduleRead):
    blocks: list[ScheduleBlockRead] = []
    overrides: list[ScheduleOverrideRead] = []


class AgendaItemRead(BaseModel):
    schedule_id: int
    schedule_name: str
    block_id: int | None = None
    override_id: int | None = None
    date: date
    day_of_week: int
    source: Literal['recurring', 'override']
    override_type: ScheduleOverrideType | None = None
    subject_id: int
    subject_name: str
    subject_color: str
    start_time: time
    end_time: time
    location: str | None = None
    notes: str | None = None
    reason: str | None = None


class DailyAgendaRead(BaseModel):
    student_id: int
    date: date
    items: list[AgendaItemRead]


class WeeklyAgendaRead(BaseModel):
    student_id: int
    week_start: date
    week_end: date
    days: list[DailyAgendaRead]
