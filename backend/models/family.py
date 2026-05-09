from __future__ import annotations

import enum
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, Enum, ForeignKey, String, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base, TimestampMixin

json_type = JSON().with_variant(JSONB, 'postgresql')


class FamilyRole(str, enum.Enum):
    parent = 'parent'
    co_parent = 'co-parent'
    tutor = 'tutor'
    student_viewer = 'student_viewer'


class Family(TimestampMixin, Base):
    __tablename__ = 'families'

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    settings: Mapped[dict[str, Any]] = mapped_column(json_type, nullable=False, default=dict)

    family_settings = relationship('FamilySettings', back_populates='family', cascade='all, delete-orphan', uselist=False)
    memberships = relationship('FamilyMembership', back_populates='family', cascade='all, delete-orphan')
    invitations = relationship('Invitation', back_populates='family', cascade='all, delete-orphan')


class FamilySettings(TimestampMixin, Base):
    __tablename__ = 'family_settings'

    family_id: Mapped[int] = mapped_column(ForeignKey('families.id', ondelete='CASCADE'), primary_key=True)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default='UTC', server_default='UTC')
    grading_scale: Mapped[str] = mapped_column(String(64), nullable=False, default='letter', server_default='letter')

    family = relationship('Family', back_populates='family_settings')


class FamilyMembership(Base):
    __tablename__ = 'family_memberships'

    user_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), primary_key=True)
    family_id: Mapped[int] = mapped_column(ForeignKey('families.id', ondelete='CASCADE'), primary_key=True)
    role: Mapped[FamilyRole] = mapped_column(Enum(FamilyRole, name='family_role'), nullable=False, default=FamilyRole.parent)
    is_owner: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text('false'))
    invited_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user = relationship('User', back_populates='memberships')
    family = relationship('Family', back_populates='memberships')


class Invitation(TimestampMixin, Base):
    __tablename__ = 'invitations'

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    family_id: Mapped[int] = mapped_column(ForeignKey('families.id', ondelete='CASCADE'), nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    role: Mapped[FamilyRole] = mapped_column(Enum(FamilyRole, name='family_role'), nullable=False)
    token: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    family = relationship('Family', back_populates='invitations')
