from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.models.assignment import AssignmentStatus
from backend.validation import normalize_optional_text, normalize_text


class AssignmentCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    subject_id: int = Field(gt=0)
    description: str | None = Field(default=None, max_length=4000)
    due_date: datetime | None = None
    status: AssignmentStatus = AssignmentStatus.pending

    @field_validator('title')
    @classmethod
    def validate_title(cls, value: str) -> str:
        return normalize_text(value, field_name='Assignment title')

    @field_validator('description')
    @classmethod
    def validate_description(cls, value: str | None) -> str | None:
        return normalize_optional_text(value, field_name='Assignment description', max_length=4000)


class AssignmentUpdate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    subject_id: int = Field(gt=0)
    description: str | None = Field(default=None, max_length=4000)
    due_date: datetime | None = None
    status: AssignmentStatus

    @field_validator('title')
    @classmethod
    def validate_title(cls, value: str) -> str:
        return normalize_text(value, field_name='Assignment title')

    @field_validator('description')
    @classmethod
    def validate_description(cls, value: str | None) -> str | None:
        return normalize_optional_text(value, field_name='Assignment description', max_length=4000)


class AssignmentStatusUpdate(BaseModel):
    status: AssignmentStatus


class AssignmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    subject_id: int
    description: str | None
    due_date: datetime | None
    status: AssignmentStatus
    created_at: datetime
    updated_at: datetime
