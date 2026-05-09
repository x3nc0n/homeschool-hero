from __future__ import annotations

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base, TimestampMixin


class UserPreference(TimestampMixin, Base):
    __tablename__ = 'user_preferences'

    user_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), primary_key=True)
    theme: Mapped[str] = mapped_column(String(32), nullable=False, default='system', server_default='system')
    accent_color: Mapped[str] = mapped_column(String(16), nullable=False, default='#2563eb', server_default='#2563eb')
    font_size: Mapped[str] = mapped_column(String(16), nullable=False, default='medium', server_default='medium')
    density: Mapped[str] = mapped_column(String(16), nullable=False, default='comfortable', server_default='comfortable')
    sidebar_position: Mapped[str] = mapped_column(String(16), nullable=False, default='left', server_default='left')

    user = relationship('User', back_populates='ui_preferences')
