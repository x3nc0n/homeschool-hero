from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.models.portfolio import PortfolioEntryType
from backend.schemas.students import StudentRead
from backend.schemas.subjects import SubjectRead
from backend.schemas.submissions import SubmissionVersionRead
from backend.validation import normalize_text


def _normalize_tags(value: list[str]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for item in value:
        candidate = normalize_text(item, field_name='Portfolio tag').lower()
        if candidate in seen:
            continue
        seen.add(candidate)
        normalized.append(candidate)
    return normalized


def _normalize_entry_ids(value: list[int]) -> list[int]:
    normalized: list[int] = []
    seen: set[int] = set()
    for item in value:
        if item <= 0 or item in seen:
            continue
        seen.add(item)
        normalized.append(item)
    return normalized


def _normalize_rich_text(value: str | None, *, field_name: str, max_length: int) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    if not normalized:
        return None
    if len(normalized) > max_length:
        raise ValueError(f'{field_name} must be {max_length} characters or fewer')
    if '\x00' in normalized:
        raise ValueError(f'{field_name} contains invalid characters')
    return normalized


class PortfolioAssignmentSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    due_date: datetime | None = None


class PortfolioEntryBase(BaseModel):
    student_id: int = Field(gt=0)
    entry_type: PortfolioEntryType
    title: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=20000)
    date: date
    subject_id: int | None = Field(default=None, gt=0)
    assignment_id: int | None = Field(default=None, gt=0)
    submission_id: int | None = Field(default=None, gt=0)
    tags: list[str] = Field(default_factory=list)

    @field_validator('title')
    @classmethod
    def validate_title(cls, value: str) -> str:
        return normalize_text(value, field_name='Portfolio title')

    @field_validator('description')
    @classmethod
    def validate_description(cls, value: str | None) -> str | None:
        return _normalize_rich_text(value, field_name='Portfolio description', max_length=20000)

    @field_validator('tags')
    @classmethod
    def validate_tags(cls, value: list[str]) -> list[str]:
        return _normalize_tags(value)


class PortfolioEntryCreate(PortfolioEntryBase):
    pass


class PortfolioEntryUpdate(PortfolioEntryBase):
    pass


class PortfolioEntryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    family_id: int
    student_id: int
    entry_type: PortfolioEntryType
    title: str
    description: str | None = None
    date: date
    subject_id: int | None = None
    assignment_id: int | None = None
    submission_id: int | None = None
    attachments: list[str] = Field(default_factory=list)
    attachment_urls: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    created_by_user_id: int
    created_at: datetime
    updated_at: datetime
    student: StudentRead | None = None
    subject: SubjectRead | None = None
    assignment: PortfolioAssignmentSummary | None = None
    submission: SubmissionVersionRead | None = None


class PublicPortfolioEntryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    student_id: int
    entry_type: PortfolioEntryType
    title: str
    description: str | None = None
    date: date
    subject_id: int | None = None
    assignment_id: int | None = None
    submission_id: int | None = None
    attachments: list[str] = Field(default_factory=list)
    attachment_urls: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    subject: SubjectRead | None = None
    assignment: PortfolioAssignmentSummary | None = None
    submission: SubmissionVersionRead | None = None


class PortfolioCollectionBase(BaseModel):
    student_id: int = Field(gt=0)
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=4000)
    entry_ids: list[int] = Field(default_factory=list)
    is_public: bool = False

    @field_validator('name')
    @classmethod
    def validate_name(cls, value: str) -> str:
        return normalize_text(value, field_name='Portfolio collection name')

    @field_validator('description')
    @classmethod
    def validate_description(cls, value: str | None) -> str | None:
        return _normalize_rich_text(value, field_name='Portfolio collection description', max_length=4000)

    @field_validator('entry_ids')
    @classmethod
    def validate_entry_ids(cls, value: list[int]) -> list[int]:
        return _normalize_entry_ids(value)


class PortfolioCollectionCreate(PortfolioCollectionBase):
    pass


class PortfolioCollectionUpdate(PortfolioCollectionBase):
    pass


class PortfolioCollectionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    family_id: int
    student_id: int
    name: str
    description: str | None = None
    entry_ids: list[int] = Field(default_factory=list)
    is_public: bool
    share_token: str | None = None
    created_at: datetime
    entries: list[PortfolioEntryRead] = Field(default_factory=list)


class PublicPortfolioCollectionRead(BaseModel):
    id: int
    student_id: int
    name: str
    description: str | None = None
    is_public: bool
    share_token: str
    created_at: datetime
    entries: list[PublicPortfolioEntryRead] = Field(default_factory=list)


class PortfolioShareLinkRead(BaseModel):
    collection_id: int
    share_token: str
    url: str
