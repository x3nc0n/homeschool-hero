from __future__ import annotations

from datetime import datetime
import json
from typing import Any
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

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


MAX_IMPORT_SUBJECTS = 25
MAX_IMPORT_TOTAL_UNITS = 250
MAX_IMPORT_TOTAL_LESSONS = 2500
MAX_IMPORT_TOTAL_OBJECTIVES = 10000
MAX_IMPORT_TOTAL_RESOURCES = 10000
MAX_IMPORT_PAYLOAD_BYTES = 2_000_000


def _normalize_extensions(value: dict[str, Any]) -> dict[str, Any]:
    return dict(value or {})


def _normalize_prerequisites(values: list[str], *, field_name: str) -> list[str]:
    return _normalize_tag_list(values, field_name=field_name)


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


class CurriculumImportMetadata(BaseModel):
    model_config = ConfigDict(extra='forbid')

    grade_levels: list[str] = Field(default_factory=list, max_length=12)
    standards_alignment: list[str] = Field(default_factory=list, max_length=50)
    estimated_hours: int | None = Field(default=None, ge=1, le=5000)
    prerequisites: list[str] = Field(default_factory=list, max_length=25)
    external_source: dict[str, Any] = Field(default_factory=dict)
    extensions: dict[str, Any] = Field(default_factory=dict)

    @field_validator('grade_levels')
    @classmethod
    def validate_grade_levels(cls, value: list[str]) -> list[str]:
        return _normalize_tag_list(value, field_name='Grade level')

    @field_validator('standards_alignment')
    @classmethod
    def validate_standards_alignment(cls, value: list[str]) -> list[str]:
        return _normalize_tag_list(value, field_name='Standards alignment')

    @field_validator('prerequisites')
    @classmethod
    def validate_prerequisites(cls, value: list[str]) -> list[str]:
        return _normalize_prerequisites(value, field_name='Prerequisite')

    @field_validator('extensions')
    @classmethod
    def validate_extensions(cls, value: dict[str, Any]) -> dict[str, Any]:
        return _normalize_extensions(value)


class CurriculumImportResource(BaseModel):
    model_config = ConfigDict(extra='forbid')

    name: str = Field(min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=4000)
    resource_type: str = Field(default='reference', min_length=1, max_length=32)
    url: str | None = Field(default=None, max_length=1000)
    tags: list[str] = Field(default_factory=list, max_length=20)
    metadata: dict[str, Any] = Field(default_factory=dict)
    extensions: dict[str, Any] = Field(default_factory=dict)

    @field_validator('name')
    @classmethod
    def validate_name(cls, value: str) -> str:
        return normalize_text(value, field_name='Curriculum resource name')

    @field_validator('description')
    @classmethod
    def validate_description(cls, value: str | None) -> str | None:
        return normalize_optional_text(value, field_name='Curriculum resource description', max_length=4000)

    @field_validator('resource_type')
    @classmethod
    def validate_resource_type(cls, value: str) -> str:
        return normalize_text(value, field_name='Curriculum resource type')

    @field_validator('url')
    @classmethod
    def validate_url(cls, value: str | None) -> str | None:
        return _validate_optional_url(value)

    @field_validator('tags')
    @classmethod
    def validate_tags(cls, value: list[str]) -> list[str]:
        return _normalize_tag_list(value, field_name='Curriculum resource tag')

    @field_validator('extensions')
    @classmethod
    def validate_extensions(cls, value: dict[str, Any]) -> dict[str, Any]:
        return _normalize_extensions(value)


class CurriculumImportLessonPayload(BaseModel):
    model_config = ConfigDict(extra='forbid')

    name: str = Field(min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=4000)
    estimated_minutes: int | None = Field(default=None, ge=1, le=1440)
    objectives: list[str] = Field(default_factory=list, max_length=20)
    resources: list[CurriculumImportResource] = Field(default_factory=list, max_length=20)
    metadata: CurriculumImportMetadata = Field(default_factory=CurriculumImportMetadata)
    extensions: dict[str, Any] = Field(default_factory=dict)

    @field_validator('name')
    @classmethod
    def validate_name(cls, value: str) -> str:
        return normalize_text(value, field_name='Curriculum lesson name')

    @field_validator('description')
    @classmethod
    def validate_description(cls, value: str | None) -> str | None:
        return normalize_optional_text(value, field_name='Curriculum lesson description', max_length=4000)

    @field_validator('objectives')
    @classmethod
    def validate_objectives(cls, value: list[str]) -> list[str]:
        return [normalize_text(item, field_name='Lesson objective') for item in value]

    @field_validator('extensions')
    @classmethod
    def validate_extensions(cls, value: dict[str, Any]) -> dict[str, Any]:
        return _normalize_extensions(value)


class CurriculumImportUnitPayload(BaseModel):
    model_config = ConfigDict(extra='forbid')

    name: str = Field(min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=4000)
    lessons: list[CurriculumImportLessonPayload] = Field(min_length=1, max_length=250)
    metadata: CurriculumImportMetadata = Field(default_factory=CurriculumImportMetadata)
    extensions: dict[str, Any] = Field(default_factory=dict)

    @field_validator('name')
    @classmethod
    def validate_name(cls, value: str) -> str:
        return normalize_text(value, field_name='Curriculum unit name')

    @field_validator('description')
    @classmethod
    def validate_description(cls, value: str | None) -> str | None:
        return normalize_optional_text(value, field_name='Curriculum unit description', max_length=4000)

    @field_validator('extensions')
    @classmethod
    def validate_extensions(cls, value: dict[str, Any]) -> dict[str, Any]:
        return _normalize_extensions(value)


class CurriculumImportSubjectPayload(BaseModel):
    model_config = ConfigDict(extra='forbid')

    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=4000)
    units: list[CurriculumImportUnitPayload] = Field(min_length=1, max_length=100)
    metadata: CurriculumImportMetadata = Field(default_factory=CurriculumImportMetadata)
    extensions: dict[str, Any] = Field(default_factory=dict)

    @field_validator('name')
    @classmethod
    def validate_name(cls, value: str) -> str:
        return normalize_text(value, field_name='Curriculum subject name')

    @field_validator('description')
    @classmethod
    def validate_description(cls, value: str | None) -> str | None:
        return normalize_optional_text(value, field_name='Curriculum subject description', max_length=4000)

    @field_validator('extensions')
    @classmethod
    def validate_extensions(cls, value: dict[str, Any]) -> dict[str, Any]:
        return _normalize_extensions(value)


class CurriculumImportDocument(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
        json_schema_extra={
            'example': {
                'schema_version': '1.0',
                'name': 'Core Homeschool 6th Grade',
                'description': 'Integrated core curriculum for the 2026 school year.',
                'source': 'manual',
                'metadata': {
                    'grade_levels': ['6'],
                    'standards_alignment': ['CCSS.MATH.CONTENT.6.RP.A.1'],
                    'estimated_hours': 720,
                    'prerequisites': ['5th grade arithmetic'],
                },
                'subjects': [
                    {
                        'name': 'Math',
                        'metadata': {'grade_levels': ['6']},
                        'units': [
                            {
                                'name': 'Ratios and Proportions',
                                'lessons': [
                                    {
                                        'name': 'Understanding Ratios',
                                        'estimated_minutes': 45,
                                        'objectives': ['Define a ratio', 'Model ratios with tables'],
                                        'resources': [
                                            {
                                                'name': 'Ratio Warmup Video',
                                                'resource_type': 'video',
                                                'url': 'https://example.com/ratio-warmup',
                                            }
                                        ],
                                    }
                                ],
                            }
                        ],
                    }
                ],
            }
        },
    )

    schema_version: str = Field(default='1.0', min_length=1, max_length=32)
    name: str = Field(min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=4000)
    source: str = Field(default='manual', min_length=1, max_length=120)
    metadata: CurriculumImportMetadata = Field(default_factory=CurriculumImportMetadata)
    subjects: list[CurriculumImportSubjectPayload] = Field(min_length=1, max_length=MAX_IMPORT_SUBJECTS)
    extensions: dict[str, Any] = Field(default_factory=dict)

    @field_validator('schema_version')
    @classmethod
    def validate_schema_version(cls, value: str) -> str:
        return normalize_text(value, field_name='Curriculum schema version')

    @field_validator('name')
    @classmethod
    def validate_name(cls, value: str) -> str:
        return normalize_text(value, field_name='Curriculum name')

    @field_validator('description')
    @classmethod
    def validate_description(cls, value: str | None) -> str | None:
        return normalize_optional_text(value, field_name='Curriculum description', max_length=4000)

    @field_validator('source')
    @classmethod
    def validate_source(cls, value: str) -> str:
        return normalize_text(value, field_name='Curriculum source')

    @field_validator('extensions')
    @classmethod
    def validate_extensions(cls, value: dict[str, Any]) -> dict[str, Any]:
        return _normalize_extensions(value)

    @model_validator(mode='after')
    def validate_size_limits(self):
        total_units = 0
        total_lessons = 0
        total_objectives = 0
        total_resources = 0
        for subject in self.subjects:
            total_units += len(subject.units)
            for unit in subject.units:
                total_lessons += len(unit.lessons)
                for lesson in unit.lessons:
                    total_objectives += len(lesson.objectives)
                    total_resources += len(lesson.resources)
        if total_units > MAX_IMPORT_TOTAL_UNITS:
            raise ValueError(f'Curriculum import exceeds the {MAX_IMPORT_TOTAL_UNITS} unit limit')
        if total_lessons > MAX_IMPORT_TOTAL_LESSONS:
            raise ValueError(f'Curriculum import exceeds the {MAX_IMPORT_TOTAL_LESSONS} lesson limit')
        if total_objectives > MAX_IMPORT_TOTAL_OBJECTIVES:
            raise ValueError(f'Curriculum import exceeds the {MAX_IMPORT_TOTAL_OBJECTIVES} objective limit')
        if total_resources > MAX_IMPORT_TOTAL_RESOURCES:
            raise ValueError(f'Curriculum import exceeds the {MAX_IMPORT_TOTAL_RESOURCES} resource limit')
        payload_bytes = len(json.dumps(self.model_dump(mode='json'), separators=(',', ':')).encode('utf-8'))
        if payload_bytes > MAX_IMPORT_PAYLOAD_BYTES:
            raise ValueError(f'Curriculum import exceeds the {MAX_IMPORT_PAYLOAD_BYTES} byte limit')
        return self


class CurriculumImportSummaryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: int
    name: str
    description: str | None
    source: str
    schema_version: str
    metadata: CurriculumImportMetadata = Field(validation_alias='curriculum_metadata', serialization_alias='metadata')
    subject_count: int
    unit_count: int
    lesson_count: int
    is_activated: bool
    last_activation_summary: dict[str, Any] = Field(default_factory=dict)
    last_activated_at: datetime | None
    created_at: datetime
    updated_at: datetime


class CurriculumImportResourceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    description: str | None
    resource_type: str
    url: str | None
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    extensions: dict[str, Any] = Field(default_factory=dict)


class CurriculumImportLessonRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: int
    name: str
    description: str | None
    sequence_order: int
    estimated_minutes: int | None
    objectives: list[str] = Field(default_factory=list)
    resources: list[CurriculumImportResourceRead] = Field(default_factory=list)
    metadata: CurriculumImportMetadata = Field(validation_alias='lesson_metadata', serialization_alias='metadata')
    activated_curriculum_lesson_id: int | None
    created_at: datetime
    updated_at: datetime


class CurriculumImportUnitRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: int
    name: str
    description: str | None
    sequence_order: int
    metadata: CurriculumImportMetadata = Field(validation_alias='unit_metadata', serialization_alias='metadata')
    activated_curriculum_unit_id: int | None
    lessons: list[CurriculumImportLessonRead] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class CurriculumImportSubjectRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: int
    name: str
    description: str | None
    sequence_order: int
    metadata: CurriculumImportMetadata = Field(validation_alias='subject_metadata', serialization_alias='metadata')
    activated_subject_id: int | None
    activated_package_id: int | None
    units: list[CurriculumImportUnitRead] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class CurriculumImportRead(CurriculumImportSummaryRead):
    grade_levels: list[str] = Field(default_factory=list)
    standards_alignment: list[str] = Field(default_factory=list)
    estimated_hours: int | None
    prerequisites: list[str] = Field(default_factory=list)
    payload: dict[str, Any] = Field(default_factory=dict)
    subjects: list[CurriculumImportSubjectRead] = Field(default_factory=list)


class CurriculumImportActivationRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')

    school_year_id: int = Field(gt=0)
    subject_mappings: dict[int, int] = Field(default_factory=dict)
    create_missing_subjects: bool = True
    generate_assignments: bool = False


class CurriculumImportActivationRead(BaseModel):
    curriculum_id: int
    package_ids: list[int] = Field(default_factory=list)
    subject_ids: list[int] = Field(default_factory=list)
    unit_ids: list[int] = Field(default_factory=list)
    lesson_ids: list[int] = Field(default_factory=list)
    resource_ids: list[int] = Field(default_factory=list)
    assignment_ids: list[int] = Field(default_factory=list)
    generated_assignments: bool
    activated_at: datetime
