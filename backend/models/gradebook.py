from __future__ import annotations

import enum
from typing import Any

from sqlalchemy import JSON, Boolean, Enum, Float, ForeignKey, Integer, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base, TimestampMixin


class SubjectGradingMode(str, enum.Enum):
    points = 'points'
    percentage = 'percentage'


class GradeScale(TimestampMixin, Base):
    __tablename__ = 'grade_scales'
    __table_args__ = (UniqueConstraint('family_id', 'name', name='uq_grade_scales_family_id_name'),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    family_id: Mapped[int] = mapped_column(ForeignKey('families.id', ondelete='CASCADE'), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    ranges: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text('false'))

    family = relationship('Family', back_populates='grade_scales')
    subjects = relationship('Subject', back_populates='grade_scale')


class GradeCategory(TimestampMixin, Base):
    __tablename__ = 'grade_categories'
    __table_args__ = (UniqueConstraint('subject_id', 'name', name='uq_grade_categories_subject_id_name'),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    family_id: Mapped[int] = mapped_column(ForeignKey('families.id', ondelete='CASCADE'), nullable=False, index=True)
    subject_id: Mapped[int] = mapped_column(ForeignKey('subjects.id', ondelete='CASCADE'), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    weight: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, server_default='0')
    drop_lowest: Mapped[int | None] = mapped_column(Integer, nullable=True)

    subject = relationship('Subject', back_populates='grade_categories')
