from __future__ import annotations

from datetime import datetime
from typing import Any
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.models.curriculum import ResourceType
from backend.validation import normalize_optional_text, normalize_text


def _normalize_tag_list(values: list[str], *, field_name: str) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        tag = normalize_text(value, field_name=field_name)
        lowered = tag.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        normalized.append(tag)
    return normalized


def _validate_optional_url(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    if not normalized:
        return None
    parsed = urlparse(normalized)
    if parsed.scheme not in {'http', 'https'} or not parsed.netloc:
        raise ValueError('Resource URL must be a valid http or https URL')
    return normalized


class CurriculumPackageCreate(BaseModel):
    school_year_id: int = Field(gt=0)
    name: str = Field(min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=4000)
    subject_id: int = Field(gt=0)

    @field_validator('name')
    @classmethod
    def validate_name(cls, value: str) -> str:
        return normalize_text(value, field_name='Curriculum package name')

    @field_validator('description')
    @classmethod
    def validate_description(cls, value: str | None) -> str | None:
        return normalize_optional_text(value, field_name='Curriculum package description', max_length=4000)


class CurriculumPackageUpdate(CurriculumPackageCreate):
    pass


class CurriculumUnitCreate(BaseModel):
    package_id: int = Field(gt=0)
    name: str = Field(min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=4000)
    sequence_order: int = Field(default=1, ge=1, le=9999)
    standards_tags: list[str] = Field(default_factory=list)

    @field_validator('name')
    @classmethod
    def validate_name(cls, value: str) -> str:
        return normalize_text(value, field_name='Unit name')

    @field_validator('description')
    @classmethod
    def validate_description(cls, value: str | None) -> str | None:
        return normalize_optional_text(value, field_name='Unit description', max_length=4000)

    @field_validator('standards_tags')
    @classmethod
    def validate_standards_tags(cls, value: list[str]) -> list[str]:
        return _normalize_tag_list(value, field_name='Standards tag')


class CurriculumUnitUpdate(CurriculumUnitCreate):
    package_id: int | None = Field(default=None, exclude=True)


class CurriculumLessonCreate(BaseModel):
    unit_id: int = Field(gt=0)
    name: str = Field(min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=4000)
    sequence_order: int = Field(default=1, ge=1, le=9999)
    estimated_duration_minutes: int | None = Field(default=None, ge=1, le=1440)
    standards_tags: list[str] = Field(default_factory=list)

    @field_validator('name')
    @classmethod
    def validate_name(cls, value: str) -> str:
        return normalize_text(value, field_name='Lesson name')

    @field_validator('description')
    @classmethod
    def validate_description(cls, value: str | None) -> str | None:
        return normalize_optional_text(value, field_name='Lesson description', max_length=4000)

    @field_validator('standards_tags')
    @classmethod
    def validate_standards_tags(cls, value: list[str]) -> list[str]:
        return _normalize_tag_list(value, field_name='Standards tag')


class CurriculumLessonUpdate(CurriculumLessonCreate):
    unit_id: int | None = Field(default=None, exclude=True)


class CloneCurriculumPackageRequest(BaseModel):
    target_school_year_id: int = Field(gt=0)
    name: str | None = Field(default=None, max_length=160)

    @field_validator('name')
    @classmethod
    def validate_name(cls, value: str | None) -> str | None:
        return normalize_optional_text(value, field_name='Cloned curriculum package name', max_length=160)


class ResourceUpsert(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=4000)
    resource_type: ResourceType
    url: str | None = Field(default=None, max_length=1000)
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator('name')
    @classmethod
    def validate_name(cls, value: str) -> str:
        return normalize_text(value, field_name='Resource name')

    @field_validator('description')
    @classmethod
    def validate_description(cls, value: str | None) -> str | None:
        return normalize_optional_text(value, field_name='Resource description', max_length=4000)

    @field_validator('url')
    @classmethod
    def validate_url(cls, value: str | None) -> str | None:
        return _validate_optional_url(value)

    @field_validator('tags')
    @classmethod
    def validate_tags(cls, value: list[str]) -> list[str]:
        return _normalize_tag_list(value, field_name='Resource tag')


class ResourceUpdate(ResourceUpsert):
    pass


class ResourceSummaryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    resource_type: ResourceType
    file_url: str | None = None
    url: str | None = None
    tags: list[str] = []


class CurriculumLessonRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    unit_id: int
    name: str
    description: str | None
    sequence_order: int
    estimated_duration_minutes: int | None
    standards_tags: list[str] = []
    resources: list[ResourceSummaryRead] = []
    created_at: datetime
    updated_at: datetime


class CurriculumUnitRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    package_id: int
    name: str
    description: str | None
    sequence_order: int
    standards_tags: list[str] = []
    lessons: list[CurriculumLessonRead] = []
    created_at: datetime
    updated_at: datetime


class CurriculumPackageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    family_id: int
    school_year_id: int
    name: str
    description: str | None
    subject_id: int
    created_by_user_id: int
    created_at: datetime
    updated_at: datetime


class CurriculumPackageDetail(CurriculumPackageRead):
    units: list[CurriculumUnitRead] = []


class ResourceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: int
    family_id: int
    name: str
    description: str | None
    resource_type: ResourceType
    file_path: str | None
    file_url: str | None = None
    url: str | None
    tags: list[str] = []
    metadata: dict[str, Any] = Field(alias='resource_metadata')
    lesson_ids: list[int] = []
    created_by_user_id: int
    created_at: datetime
    updated_at: datetime
