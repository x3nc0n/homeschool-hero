from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from backend.models.lesson_plan import LessonPlanStatus
from backend.schemas.calendar import SchoolYearRead
from backend.schemas.curriculum import ResourceSummaryRead
from backend.schemas.students import StudentRead
from backend.validation import normalize_optional_text


class LessonPlanLessonPackageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    subject_id: int


class LessonPlanLessonUnitRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    sequence_order: int
    package: LessonPlanLessonPackageRead


class LessonPlanLessonRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    unit_id: int
    name: str
    description: str | None
    sequence_order: int
    estimated_duration_minutes: int | None
    standards_tags: list[str] = Field(default_factory=list)
    resources: list[ResourceSummaryRead] = Field(default_factory=list)
    unit: LessonPlanLessonUnitRead


class PacingTargetUnitRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    package_id: int
    name: str
    sequence_order: int
    package: LessonPlanLessonPackageRead


class LessonPlanBase(BaseModel):
    curriculum_lesson_id: int = Field(gt=0)
    student_id: int = Field(gt=0)
    school_year_id: int = Field(gt=0)
    target_date: date
    estimated_duration_minutes: int | None = Field(default=None, ge=1, le=1440)
    status: LessonPlanStatus = LessonPlanStatus.planned
    notes: str | None = Field(default=None, max_length=4000)

    @field_validator('notes')
    @classmethod
    def validate_notes(cls, value: str | None) -> str | None:
        return normalize_optional_text(value, field_name='Lesson plan notes', max_length=4000)


class LessonPlanCreate(LessonPlanBase):
    pass


class LessonPlanUpdate(LessonPlanBase):
    pass


class LessonPlanRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    family_id: int
    curriculum_lesson_id: int
    student_id: int
    school_year_id: int
    target_date: date
    estimated_duration_minutes: int | None
    status: LessonPlanStatus
    completed_at: datetime | None
    notes: str | None
    assignment_ids: list[int] = Field(default_factory=list)
    curriculum_lesson: LessonPlanLessonRead
    student: StudentRead
    school_year: SchoolYearRead
    created_at: datetime
    updated_at: datetime


class LessonPlanBulkUpdateRequest(BaseModel):
    lesson_plan_ids: list[int] = Field(min_length=1)
    status: LessonPlanStatus
    target_date: date | None = None
    notes: str | None = Field(default=None, max_length=4000)

    @field_validator('notes')
    @classmethod
    def validate_notes(cls, value: str | None) -> str | None:
        return normalize_optional_text(value, field_name='Lesson plan bulk notes', max_length=4000)

    @model_validator(mode='after')
    def validate_payload(self):
        if self.status == LessonPlanStatus.rescheduled and self.target_date is None:
            raise ValueError('target_date is required when rescheduling lesson plans')
        return self


class LessonPlanGenerationRequest(BaseModel):
    package_id: int = Field(gt=0)
    student_id: int = Field(gt=0)
    school_year_id: int | None = Field(default=None, gt=0)
    start_date: date | None = None
    default_duration_minutes: int | None = Field(default=None, ge=1, le=1440)
    overwrite_existing: bool = False


class LessonPlanAssignmentGenerationRequest(BaseModel):
    lesson_plan_ids: list[int] = Field(min_length=1)
    include_existing: bool = True


class PacingTargetBase(BaseModel):
    curriculum_unit_id: int = Field(gt=0)
    student_id: int = Field(gt=0)
    target_start_date: date
    target_end_date: date

    @model_validator(mode='after')
    def validate_dates(self):
        if self.target_start_date > self.target_end_date:
            raise ValueError('target_start_date must be on or before target_end_date')
        return self


class PacingTargetCreate(PacingTargetBase):
    pass


class PacingTargetUpdate(PacingTargetBase):
    pass


class PacingTargetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    family_id: int
    curriculum_unit_id: int
    student_id: int
    target_start_date: date
    target_end_date: date
    actual_completion_date: date | None
    curriculum_unit: PacingTargetUnitRead
    student: StudentRead
    created_at: datetime
    updated_at: datetime


class PacingStatusRead(BaseModel):
    pacing_target_id: int
    curriculum_unit_id: int
    unit_name: str
    package_id: int
    package_name: str
    subject_id: int
    target_start_date: date
    target_end_date: date
    actual_completion_date: date | None
    status: str
    total_lessons: int
    planned_lessons: int
    completed_lessons: int
    remaining_lessons: int


class PacingStatusSummaryRead(BaseModel):
    student_id: int
    subject_id: int | None = None
    items: list[PacingStatusRead] = Field(default_factory=list)
