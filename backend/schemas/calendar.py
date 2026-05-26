from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, RootModel, field_validator, model_validator

from backend.models.calendar import CalendarEventType, TermType
from backend.validation import normalize_optional_text, normalize_text

DateValue = date


class CalendarDateRangeModel(BaseModel):
    @model_validator(mode='after')
    def validate_date_range(self):
        if self.start_date > self.end_date:
            raise ValueError('start_date must be on or before end_date')
        return self


class SchoolYearCreate(CalendarDateRangeModel):
    name: str = Field(min_length=1, max_length=64)
    start_date: date
    end_date: date
    is_active: bool = False

    @field_validator('name')
    @classmethod
    def validate_name(cls, value: str) -> str:
        return normalize_text(value, field_name='School year name')


class SchoolYearUpdate(CalendarDateRangeModel):
    name: str = Field(min_length=1, max_length=64)
    start_date: date
    end_date: date
    is_active: bool = False

    @field_validator('name')
    @classmethod
    def validate_name(cls, value: str) -> str:
        return normalize_text(value, field_name='School year name')


class GradingPeriodCreate(CalendarDateRangeModel):
    term_id: int = Field(gt=0)
    name: str = Field(min_length=1, max_length=120)
    start_date: date
    end_date: date

    @field_validator('name')
    @classmethod
    def validate_name(cls, value: str) -> str:
        return normalize_text(value, field_name='Grading period name')


class GradingPeriodUpdate(CalendarDateRangeModel):
    name: str = Field(min_length=1, max_length=120)
    start_date: date
    end_date: date

    @field_validator('name')
    @classmethod
    def validate_name(cls, value: str) -> str:
        return normalize_text(value, field_name='Grading period name')


class TermCreate(CalendarDateRangeModel):
    school_year_id: int = Field(gt=0)
    name: str = Field(min_length=1, max_length=120)
    start_date: date
    end_date: date
    term_type: TermType = TermType.semester

    @field_validator('name')
    @classmethod
    def validate_name(cls, value: str) -> str:
        return normalize_text(value, field_name='Term name')


class TermUpdate(CalendarDateRangeModel):
    name: str = Field(min_length=1, max_length=120)
    start_date: date
    end_date: date
    term_type: TermType = TermType.semester

    @field_validator('name')
    @classmethod
    def validate_name(cls, value: str) -> str:
        return normalize_text(value, field_name='Term name')


class CalendarEventCreate(BaseModel):
    school_year_id: int = Field(gt=0)
    date: date
    event_type: CalendarEventType = CalendarEventType.holiday
    name: str = Field(min_length=1, max_length=160)
    is_instructional_day: bool = False
    notes: str | None = Field(default=None, max_length=1000)

    @field_validator('name')
    @classmethod
    def validate_name(cls, value: str) -> str:
        return normalize_text(value, field_name='Calendar event name')

    @field_validator('notes')
    @classmethod
    def validate_notes(cls, value: str | None) -> str | None:
        return normalize_optional_text(value, field_name='Calendar event notes', max_length=1000)


class CalendarEventUpdate(BaseModel):
    date: date
    event_type: CalendarEventType = CalendarEventType.holiday
    name: str = Field(min_length=1, max_length=160)
    is_instructional_day: bool = False
    notes: str | None = Field(default=None, max_length=1000)

    @field_validator('name')
    @classmethod
    def validate_name(cls, value: str) -> str:
        return normalize_text(value, field_name='Calendar event name')

    @field_validator('notes')
    @classmethod
    def validate_notes(cls, value: str | None) -> str | None:
        return normalize_optional_text(value, field_name='Calendar event notes', max_length=1000)


class TermBulkCreate(RootModel[list[TermCreate]]):
    pass


class CalendarEventBulkCreate(RootModel[list[CalendarEventCreate]]):
    pass


class SchoolYearWizardCustomBreak(CalendarDateRangeModel):
    name: str = Field(min_length=1, max_length=160)
    start_date: date
    end_date: date

    @field_validator('name')
    @classmethod
    def validate_name(cls, value: str) -> str:
        return normalize_text(value, field_name='Custom break name')


class SchoolYearWizardCreate(CalendarDateRangeModel):
    name: str = Field(min_length=1, max_length=64)
    start_date: date
    end_date: date
    term_structure: Literal['semesters', 'quarters', 'trimesters', 'custom']
    holidays: list[str] = Field(default_factory=list)
    custom_breaks: list[SchoolYearWizardCustomBreak] = Field(default_factory=list)
    is_active: bool = True

    @field_validator('name')
    @classmethod
    def validate_name(cls, value: str) -> str:
        return normalize_text(value, field_name='School year name')

    @field_validator('holidays')
    @classmethod
    def validate_holidays(cls, value: list[str]) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()
        for item in value:
            holiday = normalize_text(item, field_name='Holiday preset').lower().replace(' ', '_')
            if holiday in seen:
                continue
            seen.add(holiday)
            normalized.append(holiday)
        return normalized


class GradingPeriodRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    term_id: int
    family_id: int
    name: str
    start_date: date
    end_date: date
    created_at: datetime
    updated_at: datetime


class TermRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    school_year_id: int
    family_id: int
    name: str
    start_date: date
    end_date: date
    term_type: TermType
    grading_periods: list[GradingPeriodRead] = []
    created_at: datetime
    updated_at: datetime


class CalendarEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    family_id: int
    school_year_id: int
    date: date
    event_type: CalendarEventType
    name: str
    is_instructional_day: bool
    notes: str | None
    created_at: datetime
    updated_at: datetime


class SchoolYearRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    family_id: int
    name: str
    start_date: date
    end_date: date
    is_active: bool
    created_at: datetime
    updated_at: datetime


class SchoolYearDetail(SchoolYearRead):
    terms: list[TermRead] = []
    calendar_events: list[CalendarEventRead] = []


class InstructionalDayCount(BaseModel):
    school_year_id: int
    instructional_days: int
    weekday_days: int
    non_instructional_overrides: int
    instructional_overrides: int


class HolidayPresetEventPreview(BaseModel):
    date: DateValue
    name: str


class HolidayPresetDateRange(BaseModel):
    start_date: date
    end_date: date


class HolidayPresetRead(BaseModel):
    key: str
    name: str
    type: Literal['federal', 'religious', 'school_break']
    recurring: bool
    calculation_rule: dict[str, Any] | None = None
    date: DateValue | None = None
    date_range: HolidayPresetDateRange | None = None
    events: list[HolidayPresetEventPreview] = Field(default_factory=list)


class SchoolYearTemplateRead(BaseModel):
    key: str
    name: str
    description: str
    suggested_start_date: str
    suggested_end_date: str
    default_term_structure: Literal['semesters', 'quarters', 'trimesters', 'custom']
