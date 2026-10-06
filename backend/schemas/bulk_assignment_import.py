from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.models.assignment import AssignmentCategory, AssignmentRecurrence, AssignmentTargetStatus
from backend.models.bulk_assignment_import import BulkAssignmentImportStatus
from backend.schemas.assignments import AnswerKeyQuestion
from backend.validation import normalize_optional_text, normalize_text


class BulkAssignmentAnswerKey(BaseModel):
    questions: list[AnswerKeyQuestion] = Field(default_factory=list)


class ParsedAssignmentCandidate(BaseModel):
    client_item_id: str | None = Field(default=None, max_length=80)
    title: str | None = Field(default=None, max_length=255)
    description: str | None = Field(default=None, max_length=4000)
    subject_ref: str | None = Field(default=None, max_length=255)
    student_refs: list[str] = Field(default_factory=list, max_length=50)
    due_date: date | None = None
    category: AssignmentCategory | None = None
    grading_period_ref: str | None = Field(default=None, max_length=255)
    weight: float | None = Field(default=None, ge=0)
    max_score: float | None = Field(default=None, gt=0)
    recurrence: AssignmentRecurrence | None = None
    recurrence_end_date: date | None = None
    rubric_description: str | None = Field(default=None, max_length=4000)
    lesson_plan_ref: str | None = Field(default=None, max_length=255)
    answer_key: BulkAssignmentAnswerKey | None = None
    source_excerpt: str | None = Field(default=None, max_length=1000)
    confidence: float | None = Field(default=None, ge=0, le=1)
    missing_fields: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class ParsedAssignmentDocument(BaseModel):
    schema_version: str = '1.0'
    assignments: list[ParsedAssignmentCandidate] = Field(default_factory=list)


class BulkImportDefaults(BaseModel):
    subject_id: int | None = Field(default=None, gt=0)
    student_ids: list[int] = Field(default_factory=list)
    grading_period_id: int | None = Field(default=None, gt=0)
    category: AssignmentCategory | None = None
    max_score: float | None = Field(default=None, gt=0)
    weight: float | None = Field(default=None, ge=0)
    due_date: datetime | None = None


class BulkAssignmentImportTarget(BaseModel):
    student_id: int = Field(gt=0)
    due_date: datetime | None = None
    status: AssignmentTargetStatus = AssignmentTargetStatus.assigned


class BulkAssignmentImportItem(BaseModel):
    client_item_id: str = Field(min_length=1, max_length=80)
    title: str | None = Field(default=None, max_length=255)
    subject_id: int | None = Field(default=None, gt=0)
    description: str | None = Field(default=None, max_length=4000)
    due_date: datetime | None = None
    category: AssignmentCategory = AssignmentCategory.homework
    grading_period_id: int | None = Field(default=None, gt=0)
    weight: float = Field(default=1.0, ge=0)
    max_score: float = Field(default=100.0, gt=0)
    recurrence: AssignmentRecurrence = AssignmentRecurrence.none
    recurrence_end_date: date | None = None
    rubric_description: str | None = Field(default=None, max_length=4000)
    lesson_plan_id: int | None = Field(default=None, gt=0)
    targets: list[BulkAssignmentImportTarget] = Field(default_factory=list)
    answer_key: BulkAssignmentAnswerKey | None = None
    source_excerpt: str | None = Field(default=None, max_length=1000)
    confidence: float | None = Field(default=None, ge=0, le=1)
    status: Literal['ready', 'needs_clarification', 'invalid'] = 'needs_clarification'
    missing_fields: list[str] = Field(default_factory=list)
    ambiguous_fields: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    refs: dict[str, Any] = Field(default_factory=dict)

    @field_validator('title')
    @classmethod
    def validate_title(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return normalize_text(value, field_name='Assignment title')

    @field_validator('description')
    @classmethod
    def validate_description(cls, value: str | None) -> str | None:
        return normalize_optional_text(value, field_name='Assignment description', max_length=4000)

    @field_validator('rubric_description')
    @classmethod
    def validate_rubric_description(cls, value: str | None) -> str | None:
        return normalize_optional_text(value, field_name='Assignment rubric description', max_length=4000)


class BulkAssignmentImportChoice(BaseModel):
    id: int
    label: str


class BulkAssignmentImportQuestion(BaseModel):
    id: str
    field: str
    assignment_indexes: list[int]
    message: str
    choices: list[BulkAssignmentImportChoice] = Field(default_factory=list)
    allow_apply_to_all: bool = False


class BulkAssignmentImportSummary(BaseModel):
    total: int = Field(ge=0)
    ready: int = Field(ge=0)
    needs_clarification: int = Field(ge=0)
    invalid: int = Field(ge=0)


class BulkAssignmentImportRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: BulkAssignmentImportStatus
    source_filename: str
    source_content_type: str
    source_size_bytes: int
    warnings: list[str] = Field(default_factory=list)
    summary: BulkAssignmentImportSummary
    questions: list[BulkAssignmentImportQuestion] = Field(default_factory=list)
    items: list[BulkAssignmentImportItem] = Field(default_factory=list)
    revision: int
    expires_at: datetime
    created_at: datetime
    updated_at: datetime


class BulkAssignmentClarificationAnswer(BaseModel):
    question_id: str
    value: int | list[int] | str | None
    apply_to_assignment_indexes: list[int] | None = None


class BulkAssignmentImportPatch(BaseModel):
    answers: list[BulkAssignmentClarificationAnswer] = Field(default_factory=list)
    items: list[BulkAssignmentImportItem] = Field(default_factory=list)


class BulkAssignmentImportConfirmRequest(BaseModel):
    client_revision: int | None = Field(default=None, ge=1)
    item_ids: list[str] | None = None


class BulkAssignmentImportConfirmResponse(BaseModel):
    created_assignment_ids: list[int]
    skipped_item_ids: list[str] = Field(default_factory=list)
    assignment_count: int
