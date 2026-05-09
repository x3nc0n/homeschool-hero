from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base, TimestampMixin


class ReviewItemStatus(str, enum.Enum):
    pending_review = 'pending_review'
    in_review = 'in_review'
    approved = 'approved'
    rejected = 'rejected'
    needs_regrade = 'needs_regrade'


class ReviewPriority(str, enum.Enum):
    low = 'low'
    medium = 'medium'
    high = 'high'
    urgent = 'urgent'


class ReviewItem(TimestampMixin, Base):
    __tablename__ = 'review_items'

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    family_id: Mapped[int] = mapped_column(ForeignKey('families.id', ondelete='CASCADE'), nullable=False, index=True)
    submission_id: Mapped[int] = mapped_column(
        ForeignKey('submissions.id', ondelete='CASCADE'),
        nullable=False,
        unique=True,
        index=True,
    )
    grading_job_id: Mapped[int] = mapped_column(
        ForeignKey('grading_jobs.id', ondelete='CASCADE'),
        nullable=False,
        unique=True,
        index=True,
    )
    assigned_to_user_id: Mapped[int | None] = mapped_column(ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    reviewed_by_user_id: Mapped[int | None] = mapped_column(ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    status: Mapped[ReviewItemStatus] = mapped_column(
        Enum(ReviewItemStatus, name='review_item_status'),
        nullable=False,
        default=ReviewItemStatus.pending_review,
        server_default=ReviewItemStatus.pending_review.value,
        index=True,
    )
    priority: Mapped[ReviewPriority] = mapped_column(
        Enum(ReviewPriority, name='review_priority'),
        nullable=False,
        default=ReviewPriority.medium,
        server_default=ReviewPriority.medium.value,
        index=True,
    )
    ai_suggested_grade: Mapped[float | None] = mapped_column(Float, nullable=True)
    ai_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    reviewer_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)

    submission = relationship('Submission', back_populates='review_item', lazy='selectin')
    grading_job = relationship('GradingJob', back_populates='review_item', lazy='selectin')
    assignee = relationship('User', foreign_keys=[assigned_to_user_id], back_populates='assigned_review_items', lazy='selectin')
    reviewer = relationship('User', foreign_keys=[reviewed_by_user_id], back_populates='reviewed_review_items', lazy='selectin')
    comments = relationship(
        'ReviewComment',
        back_populates='review_item',
        cascade='all, delete-orphan',
        order_by='ReviewComment.created_at.asc()',
        lazy='selectin',
    )


class ReviewComment(TimestampMixin, Base):
    __tablename__ = 'review_comments'

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    family_id: Mapped[int] = mapped_column(ForeignKey('families.id', ondelete='CASCADE'), nullable=False, index=True)
    review_item_id: Mapped[int] = mapped_column(
        ForeignKey('review_items.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    author_user_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)

    review_item = relationship('ReviewItem', back_populates='comments', lazy='selectin')
    author = relationship('User', back_populates='review_comments', lazy='selectin')
