from __future__ import annotations

import enum

from sqlalchemy import Boolean, Enum, ForeignKey, Index, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base, TimestampMixin


class NotificationType(str, enum.Enum):
    due_date = 'due_date'
    grading_complete = 'grading_complete'
    backup_status = 'backup_status'
    security_alert = 'security_alert'
    invitation = 'invitation'
    compliance_reminder = 'compliance_reminder'


class Notification(TimestampMixin, Base):
    __tablename__ = 'notifications'
    __table_args__ = (
        Index('ix_notifications_user_read_created_at', 'user_id', 'read', 'created_at'),
        Index('ix_notifications_family_user_read', 'family_id', 'user_id', 'read'),
        Index(
            'ix_notifications_unread_created_at',
            'user_id',
            'created_at',
            postgresql_where=text('read = false'),
            sqlite_where=text('read = 0'),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    family_id: Mapped[int] = mapped_column(ForeignKey('families.id', ondelete='CASCADE'), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    type: Mapped[NotificationType] = mapped_column(
        Enum(NotificationType, name='notification_type'), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text('false'), index=True)
    link: Mapped[str | None] = mapped_column(String(2048), nullable=True)

    family = relationship('Family', back_populates='notifications')
    user = relationship('User', back_populates='notifications')


class NotificationPreference(TimestampMixin, Base):
    __tablename__ = 'notification_preferences'
    __table_args__ = (
        UniqueConstraint('user_id', 'notification_type', name='uq_notification_preferences_user_id_notification_type'),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    notification_type: Mapped[NotificationType] = mapped_column(
        Enum(NotificationType, name='notification_type'), nullable=False
    )
    in_app_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text('true'))
    email_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text('false'))

    user = relationship('User', back_populates='notification_preferences')
