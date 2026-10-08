from __future__ import annotations

import enum
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, Index, Integer, String
from sqlalchemy.ext.mutable import MutableList
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base, TimestampMixin


class CurriculumAIImportSessionStatus(str, enum.Enum):
    processing = 'processing'
    ready = 'ready'
    failed = 'failed'
    expired = 'expired'
    confirmed = 'confirmed'


class CurriculumAIImportSession(TimestampMixin, Base):
    """Durable, family-scoped AI curriculum draft. Source text is never stored."""

    __tablename__ = 'curriculum_ai_import_sessions'
    __table_args__ = (
        Index('ix_curriculum_ai_import_sessions_family_status', 'family_id', 'status'),
        Index('ix_curriculum_ai_import_sessions_expires_at', 'expires_at'),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    family_id: Mapped[int] = mapped_column(ForeignKey('families.id', ondelete='CASCADE'), nullable=False, index=True)
    created_by_user_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    status: Mapped[CurriculumAIImportSessionStatus] = mapped_column(
        Enum(CurriculumAIImportSessionStatus, name='curriculum_ai_import_session_status'),
        nullable=False,
        default=CurriculumAIImportSessionStatus.processing,
        server_default=CurriculumAIImportSessionStatus.processing.value,
        index=True,
    )
    source_kind: Mapped[str] = mapped_column(String(16), nullable=False)
    source_name: Mapped[str] = mapped_column(String(255), nullable=False)
    warnings: Mapped[list[str]] = mapped_column(MutableList.as_mutable(JSON), nullable=False, default=list)
    draft_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default='1')
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    confirmed_curriculum_id: Mapped[int | None] = mapped_column(
        ForeignKey('imported_curricula.id', ondelete='SET NULL'),
        nullable=True,
        index=True,
    )
