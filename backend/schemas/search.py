from __future__ import annotations

import enum
from datetime import datetime

from pydantic import BaseModel, Field


class SearchEntityType(str, enum.Enum):
    assignment = 'assignment'
    grade = 'grade'
    student = 'student'
    subject = 'subject'
    attendance_note = 'attendance_note'
    audit_log = 'audit_log'
    curriculum = 'curriculum'
    resource = 'resource'
    note = 'note'
    notification = 'notification'


class SearchResultRead(BaseModel):
    entity_type: SearchEntityType
    entity_id: str
    title: str
    snippet: str
    link: str
    created_at: datetime | None = None
    student_id: int | None = None
    subject_id: int | None = None
    status: str | None = None


class SearchResponse(BaseModel):
    items: list[SearchResultRead]
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1)
    total_pages: int = Field(ge=0)
    facets: dict[str, int] = Field(default_factory=dict)
