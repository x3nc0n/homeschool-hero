from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base, TimestampMixin


class User(TimestampMixin, Base):
    __tablename__ = 'users'
    __table_args__ = (UniqueConstraint('auth_provider', 'external_id', name='uq_users_auth_provider_external_id'),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(160), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text('true'))
    auth_provider: Mapped[str] = mapped_column(String(32), nullable=False, default='local', server_default='local')
    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    failed_login_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text('0'))
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    memberships = relationship('FamilyMembership', back_populates='user', cascade='all, delete-orphan')
    audit_events = relationship('AuditEvent', back_populates='actor')
    grading_jobs = relationship('GradingJob')
    assigned_review_items = relationship('ReviewItem', foreign_keys='ReviewItem.assigned_to_user_id', back_populates='assignee')
    reviewed_review_items = relationship('ReviewItem', foreign_keys='ReviewItem.reviewed_by_user_id', back_populates='reviewer')
    review_comments = relationship('ReviewComment', foreign_keys='ReviewComment.author_user_id', back_populates='author')
    notifications = relationship('Notification', back_populates='user', cascade='all, delete-orphan')
    notification_preferences = relationship('NotificationPreference', back_populates='user', cascade='all, delete-orphan')
    portfolio_entries = relationship('PortfolioEntry', back_populates='creator')
