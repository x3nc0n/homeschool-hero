from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base, TimestampMixin


class MaintenanceMode(TimestampMixin, Base):
    __tablename__ = 'maintenance_modes'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1, server_default=text('1'))
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text('false'))
    message: Mapped[str] = mapped_column(String(500), nullable=False)
    scheduled_start_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    scheduled_end_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_by_user_id: Mapped[int | None] = mapped_column(ForeignKey('users.id', ondelete='SET NULL'), nullable=True)

    updated_by_user = relationship('User', foreign_keys=[updated_by_user_id])
