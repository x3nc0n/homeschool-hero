from __future__ import annotations

import enum
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Enum, Float, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base


class ReportCardStatus(str, enum.Enum):
    draft = 'draft'
    final = 'final'
    archived = 'archived'


class ReportCard(Base):
    __tablename__ = 'report_cards'

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    family_id: Mapped[int] = mapped_column(ForeignKey('families.id', ondelete='CASCADE'), nullable=False, index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey('students.id', ondelete='CASCADE'), nullable=False, index=True)
    school_year_id: Mapped[int] = mapped_column(ForeignKey('school_years.id', ondelete='CASCADE'), nullable=False, index=True)
    grading_period_id: Mapped[int] = mapped_column(
        ForeignKey('grading_periods.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)
    generated_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey('users.id', ondelete='SET NULL'),
        nullable=True,
        index=True,
    )
    status: Mapped[ReportCardStatus] = mapped_column(
        Enum(ReportCardStatus, name='report_card_status'),
        nullable=False,
        default=ReportCardStatus.draft,
        server_default=ReportCardStatus.draft.value,
        index=True,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    family = relationship('Family', back_populates='report_cards')
    student = relationship('Student', back_populates='report_cards', lazy='selectin')
    school_year = relationship('SchoolYear', back_populates='report_cards', lazy='selectin')
    grading_period = relationship('GradingPeriod', back_populates='report_cards', lazy='selectin')
    generated_by = relationship('User', back_populates='generated_report_cards', lazy='selectin')
    entries = relationship(
        'ReportCardEntry',
        back_populates='report_card',
        cascade='all, delete-orphan',
        order_by='ReportCardEntry.id',
        lazy='selectin',
    )


class ReportCardEntry(Base):
    __tablename__ = 'report_card_entries'
    __table_args__ = (UniqueConstraint('report_card_id', 'subject_id', name='uq_report_card_entries_report_subject'),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    report_card_id: Mapped[int] = mapped_column(
        ForeignKey('report_cards.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    subject_id: Mapped[int] = mapped_column(ForeignKey('subjects.id', ondelete='CASCADE'), nullable=False, index=True)
    letter_grade: Mapped[str | None] = mapped_column(String(4), nullable=True)
    percentage: Mapped[float | None] = mapped_column(Float, nullable=True)
    gpa_points: Mapped[float | None] = mapped_column(Float, nullable=True)
    attendance_summary: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    teacher_comments: Mapped[str | None] = mapped_column(Text, nullable=True)
    category_breakdown: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)

    report_card = relationship('ReportCard', back_populates='entries')
    subject = relationship('Subject', back_populates='report_card_entries', lazy='selectin')
