from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from backend.models.gradebook import SubjectGradingMode
from backend.validation import normalize_text


class GradeScaleRange(BaseModel):
    letter: str = Field(min_length=1, max_length=4)
    min: float = Field(ge=0, le=100)
    max: float = Field(ge=0, le=100)
    gpa_points: float = Field(ge=0, le=4.5)

    @field_validator('letter')
    @classmethod
    def validate_letter(cls, value: str) -> str:
        return normalize_text(value, field_name='Grade scale letter').upper()

    @model_validator(mode='after')
    def validate_bounds(self):
        if self.max < self.min:
            raise ValueError('max must be greater than or equal to min')
        return self


class GradeScaleWrite(BaseModel):
    id: int | None = Field(default=None, gt=0)
    name: str = Field(min_length=1, max_length=120)
    ranges: list[GradeScaleRange] = Field(min_length=1)
    is_default: bool = False

    @field_validator('name')
    @classmethod
    def validate_name(cls, value: str) -> str:
        return normalize_text(value, field_name='Grade scale name')


class GradeScaleRead(GradeScaleWrite):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime | None = None
    updated_at: datetime | None = None


class GradeCategoryWrite(BaseModel):
    id: int | None = Field(default=None, gt=0)
    name: str = Field(min_length=1, max_length=64)
    weight: float = Field(ge=0, le=1)
    drop_lowest: int = Field(default=0, ge=0, le=25)

    @field_validator('name')
    @classmethod
    def validate_name(cls, value: str) -> str:
        return normalize_text(value, field_name='Grade category name').lower()


class GradeCategoryRead(GradeCategoryWrite):
    pass


class GradebookCategoriesUpsert(BaseModel):
    subject_id: int = Field(gt=0)
    categories: list[GradeCategoryWrite] = Field(min_length=1)

    @model_validator(mode='after')
    def validate_weights(self):
        total = round(sum(category.weight for category in self.categories), 4)
        if total != 1.0:
            raise ValueError('Grade category weights must add up to 1.0')
        return self


class GradebookScalesUpsert(BaseModel):
    scales: list[GradeScaleWrite] = Field(min_length=1)

    @model_validator(mode='after')
    def validate_default(self):
        if sum(1 for scale in self.scales if scale.is_default) != 1:
            raise ValueError('Exactly one grade scale must be marked as default')
        return self


class GradebookAssignmentItem(BaseModel):
    assignment_id: int
    assignment_title: str
    category: str
    grading_period_id: int | None = None
    due_date: datetime | None = None
    status: str
    score: float | None = None
    max_score: float
    percent: float | None = None
    letter_grade: str | None = None
    submission_id: int | None = None
    grade_id: int | None = None
    graded_at: datetime | None = None
    running_overall_percent: float | None = None
    is_dropped: bool = False


class GradebookCategorySummary(BaseModel):
    id: int | None = None
    name: str
    weight: float
    drop_lowest: int
    average_percent: float | None = None
    weighted_percent: float | None = None
    assignment_count: int
    graded_count: int
    items: list[GradebookAssignmentItem]


class GradebookScaleSummary(BaseModel):
    id: int
    name: str
    ranges: list[GradeScaleRange]
    is_default: bool = False


class GradebookSubjectSummary(BaseModel):
    subject_id: int
    subject_name: str
    subject_color: str | None = None
    grading_mode: SubjectGradingMode
    grade_scale_id: int
    overall_percent: float | None = None
    letter_grade: str | None = None
    gpa_points: float | None = None
    assignments: int
    graded_assignments: int
    scale: GradebookScaleSummary
    categories: list[GradebookCategorySummary]


class GradebookView(BaseModel):
    student_id: int
    student_name: str
    subject_id: int | None = None
    grading_period_id: int | None = None
    generated_at: str
    subjects: list[GradebookSubjectSummary]
    gpa: float | None = None


class GradebookSummarySubject(BaseModel):
    subject_id: int
    subject_name: str
    subject_color: str | None = None
    overall_percent: float | None = None
    letter_grade: str | None = None
    gpa_points: float | None = None
    assignments: int
    graded_assignments: int


class GradebookSummary(BaseModel):
    student_id: int
    student_name: str
    gpa: float | None = None
    subjects: list[GradebookSummarySubject]


class GradebookTrendPoint(BaseModel):
    assignment_id: int
    assignment_title: str
    date: str
    overall_percent: float
    letter_grade: str | None = None


class GradebookTrendSeries(BaseModel):
    subject_id: int
    subject_name: str
    subject_color: str | None = None
    points: list[GradebookTrendPoint]


class GradebookTrends(BaseModel):
    student_id: int
    student_name: str
    subject_id: int | None = None
    grading_period_id: int | None = None
    series: list[GradebookTrendSeries]


class GradebookCalculationRequest(BaseModel):
    student_id: int = Field(gt=0)
    subject_id: int | None = Field(default=None, gt=0)
    grading_period_id: int | None = Field(default=None, gt=0)
