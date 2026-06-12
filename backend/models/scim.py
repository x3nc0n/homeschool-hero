from __future__ import annotations

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base, TimestampMixin
from backend.models.family import FamilyRole, family_role_enum


class ScimGroup(TimestampMixin, Base):
    __tablename__ = 'scim_groups'
    __table_args__ = (
        UniqueConstraint('family_id', 'role', name='uq_scim_groups_family_role'),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    family_id: Mapped[int] = mapped_column(ForeignKey('families.id', ondelete='CASCADE'), nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(160), nullable=False)
    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=True)
    role: Mapped[FamilyRole] = mapped_column(family_role_enum, nullable=False)

    family = relationship('Family')
