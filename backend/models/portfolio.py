from __future__ import annotations

import enum
from datetime import date, datetime

from sqlalchemy import JSON, Boolean, Date, DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.ext.mutable import MutableList
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base, TimestampMixin
from backend.services.storage import build_authenticated_file_url


class PortfolioEntryType(str, enum.Enum):
    work_sample = 'work_sample'
    journal = 'journal'
    milestone = 'milestone'
    photo = 'photo'
    note = 'note'


class PortfolioEntry(TimestampMixin, Base):
    __tablename__ = 'portfolio_entries'

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    family_id: Mapped[int] = mapped_column(ForeignKey('families.id', ondelete='CASCADE'), nullable=False, index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey('students.id', ondelete='CASCADE'), nullable=False, index=True)
    entry_type: Mapped[PortfolioEntryType] = mapped_column(
        Enum(PortfolioEntryType, name='portfolio_entry_type'),
        nullable=False,
        default=PortfolioEntryType.work_sample,
        server_default=PortfolioEntryType.work_sample.value,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    subject_id: Mapped[int | None] = mapped_column(ForeignKey('subjects.id', ondelete='SET NULL'), nullable=True, index=True)
    assignment_id: Mapped[int | None] = mapped_column(
        ForeignKey('assignments.id', ondelete='SET NULL'), nullable=True, index=True
    )
    submission_id: Mapped[int | None] = mapped_column(
        ForeignKey('submissions.id', ondelete='SET NULL'), nullable=True, index=True
    )
    attachments: Mapped[list[str]] = mapped_column(MutableList.as_mutable(JSON), nullable=False, default=list)
    tags: Mapped[list[str]] = mapped_column(MutableList.as_mutable(JSON), nullable=False, default=list)
    created_by_user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), nullable=False, index=True)

    family = relationship('Family', back_populates='portfolio_entries')
    student = relationship('Student', back_populates='portfolio_entries', lazy='selectin')
    subject = relationship('Subject', back_populates='portfolio_entries', lazy='selectin')
    assignment = relationship('Assignment', back_populates='portfolio_entries', lazy='selectin')
    submission = relationship('Submission', back_populates='portfolio_entries', lazy='selectin')
    creator = relationship('User', back_populates='portfolio_entries', lazy='selectin')

    @property
    def attachment_urls(self) -> list[str]:
        return [build_authenticated_file_url(item) for item in self.attachments or []]


class PortfolioCollection(Base):
    __tablename__ = 'portfolio_collections'

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    family_id: Mapped[int] = mapped_column(ForeignKey('families.id', ondelete='CASCADE'), nullable=False, index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey('students.id', ondelete='CASCADE'), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    entry_ids: Mapped[list[int]] = mapped_column(MutableList.as_mutable(JSON), nullable=False, default=list)
    is_public: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default='false')
    share_token: Mapped[str | None] = mapped_column(String(36), nullable=True, unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    family = relationship('Family', back_populates='portfolio_collections')
    student = relationship('Student', back_populates='portfolio_collections', lazy='selectin')
