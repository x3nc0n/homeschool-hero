from __future__ import annotations

import enum
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, JSON, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base, TimestampMixin
from backend.services.storage import build_authenticated_file_url

json_type = JSON().with_variant(JSONB, 'postgresql')


class ResourceType(str, enum.Enum):
    file = 'file'
    link = 'link'
    note = 'note'


class LessonResource(Base):
    __tablename__ = 'lesson_resources'

    lesson_id: Mapped[int] = mapped_column(
        ForeignKey('curriculum_lessons.id', ondelete='CASCADE'), primary_key=True
    )
    resource_id: Mapped[int] = mapped_column(ForeignKey('resources.id', ondelete='CASCADE'), primary_key=True)


class CurriculumPackage(TimestampMixin, Base):
    __tablename__ = 'curriculum_packages'
    __table_args__ = (
        UniqueConstraint('family_id', 'school_year_id', 'name', name='uq_curriculum_packages_family_school_year_name'),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    family_id: Mapped[int] = mapped_column(ForeignKey('families.id', ondelete='CASCADE'), nullable=False, index=True)
    school_year_id: Mapped[int] = mapped_column(
        ForeignKey('school_years.id', ondelete='CASCADE'), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    subject_id: Mapped[int] = mapped_column(ForeignKey('subjects.id', ondelete='CASCADE'), nullable=False, index=True)
    created_by_user_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)

    school_year = relationship('SchoolYear')
    subject = relationship('Subject')
    created_by_user = relationship('User')
    units = relationship(
        'CurriculumUnit',
        back_populates='package',
        cascade='all, delete-orphan',
        order_by='(CurriculumUnit.sequence_order, CurriculumUnit.id)',
    )


class CurriculumUnit(TimestampMixin, Base):
    __tablename__ = 'curriculum_units'
    __table_args__ = (UniqueConstraint('package_id', 'name', name='uq_curriculum_units_package_name'),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    package_id: Mapped[int] = mapped_column(
        ForeignKey('curriculum_packages.id', ondelete='CASCADE'), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    sequence_order: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default=text('1'))
    standards_tags: Mapped[list[str]] = mapped_column(json_type, nullable=False, default=list)

    package = relationship('CurriculumPackage', back_populates='units')
    lessons = relationship(
        'CurriculumLesson',
        back_populates='unit',
        cascade='all, delete-orphan',
        order_by='(CurriculumLesson.sequence_order, CurriculumLesson.id)',
    )
    pacing_targets = relationship(
        'PacingTarget',
        back_populates='curriculum_unit',
        cascade='all, delete-orphan',
        order_by='PacingTarget.target_start_date',
    )


class CurriculumLesson(TimestampMixin, Base):
    __tablename__ = 'curriculum_lessons'
    __table_args__ = (UniqueConstraint('unit_id', 'name', name='uq_curriculum_lessons_unit_name'),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    unit_id: Mapped[int] = mapped_column(ForeignKey('curriculum_units.id', ondelete='CASCADE'), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    sequence_order: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default=text('1'))
    estimated_duration_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    standards_tags: Mapped[list[str]] = mapped_column(json_type, nullable=False, default=list)

    unit = relationship('CurriculumUnit', back_populates='lessons')
    resources = relationship('Resource', secondary='lesson_resources', back_populates='lessons')
    lesson_plans = relationship(
        'LessonPlan',
        back_populates='curriculum_lesson',
        cascade='all, delete-orphan',
        order_by='LessonPlan.target_date',
    )


class Resource(TimestampMixin, Base):
    __tablename__ = 'resources'
    __table_args__ = (UniqueConstraint('family_id', 'name', name='uq_resources_family_id_name'),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    family_id: Mapped[int] = mapped_column(ForeignKey('families.id', ondelete='CASCADE'), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    resource_type: Mapped[ResourceType] = mapped_column(
        Enum(ResourceType, name='resource_type'), nullable=False, default=ResourceType.note
    )
    file_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    tags: Mapped[list[str]] = mapped_column(json_type, nullable=False, default=list)
    resource_metadata: Mapped[dict[str, Any]] = mapped_column('metadata', json_type, nullable=False, default=dict)
    created_by_user_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)

    created_by_user = relationship('User')
    lessons = relationship('CurriculumLesson', secondary='lesson_resources', back_populates='resources')

    @property
    def file_url(self) -> str | None:
        if not self.file_path:
            return None
        return build_authenticated_file_url(self.file_path)

    @property
    def lesson_ids(self) -> list[int]:
        return [lesson.id for lesson in self.lessons]


class ImportedCurriculum(TimestampMixin, Base):
    __tablename__ = 'imported_curricula'
    __table_args__ = (UniqueConstraint('family_id', 'name', name='uq_imported_curricula_family_name'),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    family_id: Mapped[int] = mapped_column(ForeignKey('families.id', ondelete='CASCADE'), nullable=False, index=True)
    created_by_user_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String(120), nullable=False, default='manual', server_default='manual')
    schema_version: Mapped[str] = mapped_column(String(32), nullable=False, default='1.0', server_default='1.0')
    grade_levels: Mapped[list[str]] = mapped_column(json_type, nullable=False, default=list)
    standards_alignment: Mapped[list[str]] = mapped_column(json_type, nullable=False, default=list)
    estimated_hours: Mapped[int | None] = mapped_column(Integer, nullable=True)
    prerequisites: Mapped[list[str]] = mapped_column(json_type, nullable=False, default=list)
    curriculum_metadata: Mapped[dict[str, Any]] = mapped_column('metadata', json_type, nullable=False, default=dict)
    payload: Mapped[dict[str, Any]] = mapped_column(json_type, nullable=False, default=dict)
    last_activation_summary: Mapped[dict[str, Any]] = mapped_column(json_type, nullable=False, default=dict)
    last_activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_by_user = relationship('User')
    subjects = relationship(
        'ImportedCurriculumSubject',
        back_populates='curriculum',
        cascade='all, delete-orphan',
        order_by='(ImportedCurriculumSubject.sequence_order, ImportedCurriculumSubject.id)',
    )

    @property
    def subject_count(self) -> int:
        return len(self.subjects)

    @property
    def unit_count(self) -> int:
        return sum(len(subject.units) for subject in self.subjects)

    @property
    def lesson_count(self) -> int:
        return sum(len(unit.lessons) for subject in self.subjects for unit in subject.units)

    @property
    def is_activated(self) -> bool:
        return self.last_activated_at is not None


class ImportedCurriculumSubject(TimestampMixin, Base):
    __tablename__ = 'imported_curriculum_subjects'
    __table_args__ = (UniqueConstraint('curriculum_id', 'name', name='uq_imported_curriculum_subjects_curriculum_name'),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    curriculum_id: Mapped[int] = mapped_column(
        ForeignKey('imported_curricula.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    sequence_order: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default=text('1'))
    grade_levels: Mapped[list[str]] = mapped_column(json_type, nullable=False, default=list)
    standards_alignment: Mapped[list[str]] = mapped_column(json_type, nullable=False, default=list)
    estimated_hours: Mapped[int | None] = mapped_column(Integer, nullable=True)
    prerequisites: Mapped[list[str]] = mapped_column(json_type, nullable=False, default=list)
    subject_metadata: Mapped[dict[str, Any]] = mapped_column('metadata', json_type, nullable=False, default=dict)
    activated_subject_id: Mapped[int | None] = mapped_column(
        ForeignKey('subjects.id', ondelete='SET NULL'),
        nullable=True,
        index=True,
    )
    activated_package_id: Mapped[int | None] = mapped_column(
        ForeignKey('curriculum_packages.id', ondelete='SET NULL'),
        nullable=True,
        index=True,
    )

    curriculum = relationship('ImportedCurriculum', back_populates='subjects')
    activated_subject = relationship('Subject')
    activated_package = relationship('CurriculumPackage')
    units = relationship(
        'ImportedCurriculumUnit',
        back_populates='subject',
        cascade='all, delete-orphan',
        order_by='(ImportedCurriculumUnit.sequence_order, ImportedCurriculumUnit.id)',
    )


class ImportedCurriculumUnit(TimestampMixin, Base):
    __tablename__ = 'imported_curriculum_units'
    __table_args__ = (UniqueConstraint('subject_id', 'name', name='uq_imported_curriculum_units_subject_name'),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    subject_id: Mapped[int] = mapped_column(
        ForeignKey('imported_curriculum_subjects.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    sequence_order: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default=text('1'))
    standards_alignment: Mapped[list[str]] = mapped_column(json_type, nullable=False, default=list)
    estimated_hours: Mapped[int | None] = mapped_column(Integer, nullable=True)
    prerequisites: Mapped[list[str]] = mapped_column(json_type, nullable=False, default=list)
    unit_metadata: Mapped[dict[str, Any]] = mapped_column('metadata', json_type, nullable=False, default=dict)
    activated_curriculum_unit_id: Mapped[int | None] = mapped_column(
        ForeignKey('curriculum_units.id', ondelete='SET NULL'),
        nullable=True,
        index=True,
    )

    subject = relationship('ImportedCurriculumSubject', back_populates='units')
    activated_curriculum_unit = relationship('CurriculumUnit')
    lessons = relationship(
        'ImportedCurriculumLesson',
        back_populates='unit',
        cascade='all, delete-orphan',
        order_by='(ImportedCurriculumLesson.sequence_order, ImportedCurriculumLesson.id)',
    )


class ImportedCurriculumLesson(TimestampMixin, Base):
    __tablename__ = 'imported_curriculum_lessons'
    __table_args__ = (UniqueConstraint('unit_id', 'name', name='uq_imported_curriculum_lessons_unit_name'),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    unit_id: Mapped[int] = mapped_column(
        ForeignKey('imported_curriculum_units.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    sequence_order: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default=text('1'))
    estimated_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    objectives: Mapped[list[str]] = mapped_column(json_type, nullable=False, default=list)
    resources: Mapped[list[dict[str, Any]]] = mapped_column(json_type, nullable=False, default=list)
    standards_alignment: Mapped[list[str]] = mapped_column(json_type, nullable=False, default=list)
    prerequisites: Mapped[list[str]] = mapped_column(json_type, nullable=False, default=list)
    lesson_metadata: Mapped[dict[str, Any]] = mapped_column('metadata', json_type, nullable=False, default=dict)
    activated_curriculum_lesson_id: Mapped[int | None] = mapped_column(
        ForeignKey('curriculum_lessons.id', ondelete='SET NULL'),
        nullable=True,
        index=True,
    )

    unit = relationship('ImportedCurriculumUnit', back_populates='lessons')
    activated_curriculum_lesson = relationship('CurriculumLesson')
