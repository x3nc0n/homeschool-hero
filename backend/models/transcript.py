from __future__ import annotations

import enum
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base


class TranscriptStatus(str, enum.Enum):
    draft = 'draft'
    final = 'final'
    archived = 'archived'


class Transcript(Base):
    __tablename__ = 'transcripts'

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    family_id: Mapped[int] = mapped_column(ForeignKey('families.id', ondelete='CASCADE'), nullable=False, index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey('students.id', ondelete='CASCADE'), nullable=False, index=True)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)
    generated_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey('users.id', ondelete='SET NULL'),
        nullable=True,
        index=True,
    )
    status: Mapped[TranscriptStatus] = mapped_column(
        Enum(TranscriptStatus, name='transcript_status'),
        nullable=False,
        default=TranscriptStatus.draft,
        server_default=TranscriptStatus.draft.value,
        index=True,
    )
    cumulative_gpa: Mapped[float | None] = mapped_column(nullable=True)
    weighted_gpa: Mapped[float | None] = mapped_column(nullable=True)
    total_credits: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False, default=Decimal('0.00'), server_default='0')
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    family = relationship('Family', back_populates='transcripts')
    student = relationship('Student', back_populates='transcripts', lazy='selectin')
    generated_by = relationship('User', back_populates='generated_transcripts', lazy='selectin')
    entries = relationship(
        'TranscriptEntry',
        back_populates='transcript',
        cascade='all, delete-orphan',
        order_by='TranscriptEntry.school_year_id, TranscriptEntry.subject_name, TranscriptEntry.id',
        lazy='selectin',
    )


class TranscriptEntry(Base):
    __tablename__ = 'transcript_entries'
    __table_args__ = (UniqueConstraint('transcript_id', 'school_year_id', 'subject_id', name='uq_transcript_entries_transcript_year_subject'),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    transcript_id: Mapped[int] = mapped_column(ForeignKey('transcripts.id', ondelete='CASCADE'), nullable=False, index=True)
    school_year_id: Mapped[int] = mapped_column(ForeignKey('school_years.id', ondelete='CASCADE'), nullable=False, index=True)
    subject_id: Mapped[int] = mapped_column(ForeignKey('subjects.id', ondelete='CASCADE'), nullable=False, index=True)
    subject_name: Mapped[str] = mapped_column(String(120), nullable=False)
    credits: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False, default=Decimal('1.00'), server_default='1')
    letter_grade: Mapped[str | None] = mapped_column(String(4), nullable=True)
    gpa_points: Mapped[float | None] = mapped_column(nullable=True)
    is_honors: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default='false')
    is_ap: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default='false')
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    transcript = relationship('Transcript', back_populates='entries')
    school_year = relationship('SchoolYear', back_populates='transcript_entries', lazy='selectin')
    subject = relationship('Subject', back_populates='transcript_entries', lazy='selectin')
