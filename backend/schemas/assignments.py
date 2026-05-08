from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from backend.models.assignment import AssignmentStatus


class AssignmentCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    subject_id: int
    description: str | None = None
    due_date: datetime | None = None
    status: AssignmentStatus = AssignmentStatus.pending


class AssignmentUpdate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    subject_id: int
    description: str | None = None
    due_date: datetime | None = None
    status: AssignmentStatus


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
