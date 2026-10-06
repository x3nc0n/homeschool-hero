from __future__ import annotations

import enum
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, Index, Integer, String
from sqlalchemy.ext.mutable import MutableDict, MutableList
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base, TimestampMixin


class BulkAssignmentImportStatus(str, enum.Enum):
    draft = 'draft'
    needs_clarification = 'needs_clarification'
    ready = 'ready'
    confirmed = 'confirmed'
    expired = 'expired'
    failed = 'failed'


class BulkAssignmentImportSession(TimestampMixin, Base):
    __tablename__ = 'bulk_assignment_import_sessions'
    __table_args__ = (
        Index('ix_bulk_assignment_import_sessions_family_status', 'family_id', 'status'),
        Index('ix_bulk_assignment_import_sessions_expires_at', 'expires_at'),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    family_id: Mapped[int] = mapped_column(ForeignKey('families.id', ondelete='CASCADE'), nullable=False, index=True)
    created_by_user_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    status: Mapped[BulkAssignmentImportStatus] = mapped_column(
        Enum(BulkAssignmentImportStatus, name='bulk_assignment_import_status'),
        nullable=False,
        default=BulkAssignmentImportStatus.draft,
        server_default=BulkAssignmentImportStatus.draft.value,
        index=True,
    )
    source_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    source_content_type: Mapped[str] = mapped_column(String(160), nullable=False)
    source_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    extracted_text_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    warnings: Mapped[list[str]] = mapped_column(MutableList.as_mutable(JSON), nullable=False, default=list)
    draft_payload: Mapped[dict[str, Any]] = mapped_column(MutableDict.as_mutable(JSON), nullable=False, default=dict)
    questions: Mapped[list[dict[str, Any]]] = mapped_column(MutableList.as_mutable(JSON), nullable=False, default=list)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default='1')
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
