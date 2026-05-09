from __future__ import annotations

import enum
from pathlib import Path
from typing import Any

from sqlalchemy import Enum, ForeignKey, Integer, JSON, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base, TimestampMixin

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
        return f'/uploads/{Path(self.file_path).name}'

    @property
    def lesson_ids(self) -> list[int]:
        return [lesson.id for lesson in self.lessons]
