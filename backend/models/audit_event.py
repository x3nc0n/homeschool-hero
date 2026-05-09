from __future__ import annotations

import enum
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base

json_type = JSON().with_variant(JSONB, 'postgresql')


class AuditAction(str, enum.Enum):
    login = 'login'
    logout = 'logout'
    role_change = 'role_change'
    grade_create = 'grade_create'
    grade_update = 'grade_update'
    attendance_edit = 'attendance_edit'
    report_generate = 'report_generate'
    export = 'export'
    restore = 'restore'
    config_change = 'config_change'
    invitation_create = 'invitation_create'
    invitation_accept = 'invitation_accept'
    portfolio_entry_create = 'portfolio_entry_create'
    portfolio_entry_update = 'portfolio_entry_update'
    portfolio_entry_delete = 'portfolio_entry_delete'
    portfolio_collection_create = 'portfolio_collection_create'
    portfolio_collection_update = 'portfolio_collection_update'
    portfolio_collection_delete = 'portfolio_collection_delete'
    portfolio_share = 'portfolio_share'


class AuditEvent(Base):
    __tablename__ = 'audit_events'

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    family_id: Mapped[int] = mapped_column(ForeignKey('families.id', ondelete='CASCADE'), nullable=False, index=True)
    actor_user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), nullable=False, index=True)
    action: Mapped[AuditAction] = mapped_column(Enum(AuditAction, name='audit_action'), nullable=False, index=True)
    target_entity_type: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    target_entity_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    before_snapshot: Mapped[dict[str, Any] | None] = mapped_column(json_type, nullable=True)
    after_snapshot: Mapped[dict[str, Any] | None] = mapped_column(json_type, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)

    family = relationship('Family', back_populates='audit_events')
    actor = relationship('User', back_populates='audit_events')
