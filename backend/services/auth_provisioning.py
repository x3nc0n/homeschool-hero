from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.models import Family, FamilyMembership, FamilyRole, FamilySettings, Invitation, User
from backend.security import hash_password, normalize_email


@dataclass(slots=True)
class ExternalIdentity:
    provider: str
    external_id: str
    email: str
    display_name: str


@dataclass(slots=True)
class ProvisionedIdentity:
    user: User
    membership: FamilyMembership
    family: Family
    auto_accepted_invitation: bool = False
    created_default_family_membership: bool = False


def _normalized_provider(provider: str) -> str:
    return provider.strip().lower()


def _default_display_name(email: str, display_name: str | None) -> str:
    candidate = (display_name or '').strip()
    if candidate:
        return candidate
    return email.split('@', 1)[0].replace('.', ' ').title()


def _sso_password_hash() -> str:
    return hash_password(secrets.token_urlsafe(32))


async def _get_user_by_external_id(db: AsyncSession, *, provider: str, external_id: str) -> User | None:
    result = await db.execute(
        select(User).where(
            User.auth_provider == provider,
            User.external_id == external_id,
        )
    )
    return result.scalar_one_or_none()


async def _get_user_by_email(db: AsyncSession, *, email: str) -> User | None:
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def _get_primary_membership(db: AsyncSession, *, user_id: int) -> tuple[FamilyMembership, Family] | None:
    result = await db.execute(
        select(FamilyMembership, Family)
        .join(Family, Family.id == FamilyMembership.family_id)
        .where(FamilyMembership.user_id == user_id, FamilyMembership.accepted_at.is_not(None))
        .order_by(desc(FamilyMembership.is_owner), Family.name, Family.id)
    )
    return result.first()


async def _get_pending_invitation(db: AsyncSession, *, email: str) -> Invitation | None:
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(Invitation)
        .where(
            Invitation.email == email,
            Invitation.accepted_at.is_(None),
            Invitation.expires_at > now,
        )
        .order_by(Invitation.created_at.desc(), Invitation.id.desc())
    )
    return result.scalars().first()


async def _ensure_default_family(db: AsyncSession) -> Family:
    family_name = settings.auth_default_family_name.strip()
    result = await db.execute(select(Family).where(Family.name == family_name).order_by(Family.id))
    family = result.scalars().first()
    if family is not None:
        return family

    family = Family(
        name=family_name,
        settings={'timezone': settings.bootstrap_timezone, 'grading_scale': settings.bootstrap_grading_scale},
    )
    db.add(family)
    await db.flush()
    db.add(
        FamilySettings(
            family_id=family.id,
            timezone=settings.bootstrap_timezone,
            grading_scale=settings.bootstrap_grading_scale,
        )
    )
    return family


async def _create_membership_from_invitation(
    db: AsyncSession,
    *,
    user: User,
    invitation: Invitation,
) -> tuple[FamilyMembership, Family]:
    family = await db.get(Family, invitation.family_id)
    if family is None:
        raise HTTPException(status_code=status.HTTP_410_GONE, detail='The invitation family no longer exists')

    existing_membership = (
        await db.execute(
            select(FamilyMembership).where(
                FamilyMembership.user_id == user.id,
                FamilyMembership.family_id == invitation.family_id,
            )
        )
    ).scalar_one_or_none()
    if existing_membership is not None:
        invitation.accepted_at = datetime.now(timezone.utc)
        return existing_membership, family

    membership = FamilyMembership(
        user_id=user.id,
        family_id=invitation.family_id,
        role=invitation.role,
        is_owner=False,
        student_id=invitation.student_id,
        invited_at=invitation.created_at,
        accepted_at=datetime.now(timezone.utc),
    )
    db.add(membership)
    invitation.accepted_at = membership.accepted_at
    await db.flush()
    return membership, family


async def provision_external_identity(db: AsyncSession, identity: ExternalIdentity) -> ProvisionedIdentity:
    provider = _normalized_provider(identity.provider)
    email = normalize_email(identity.email)
    display_name = _default_display_name(email, identity.display_name)

    external_user = await _get_user_by_external_id(db, provider=provider, external_id=identity.external_id)
    email_user = await _get_user_by_email(db, email=email)
    if external_user is not None and email_user is not None and external_user.id != email_user.id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail='This external identity is already linked to a different local user.',
        )

    user = external_user or email_user
    if user is None:
        user = User(
            email=email,
            display_name=display_name,
            password_hash=_sso_password_hash(),
            is_active=True,
            auth_provider=provider,
            external_id=identity.external_id,
        )
        db.add(user)
        await db.flush()
    elif not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='User account is inactive')

    user.email = email
    user.display_name = display_name
    user.auth_provider = provider
    user.external_id = identity.external_id

    membership_row = await _get_primary_membership(db, user_id=user.id)
    if membership_row is not None:
        membership, family = membership_row
        await db.commit()
        return ProvisionedIdentity(user=user, membership=membership, family=family)

    invitation = await _get_pending_invitation(db, email=email)
    if invitation is not None:
        membership, family = await _create_membership_from_invitation(db, user=user, invitation=invitation)
        await db.commit()
        return ProvisionedIdentity(
            user=user,
            membership=membership,
            family=family,
            auto_accepted_invitation=True,
        )

    auto_provision_mode = settings.auth_auto_provision_mode.strip().lower()
    if auto_provision_mode == 'reject':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail='No matching account or invitation exists for this identity provider user.',
        )

    family = await _ensure_default_family(db)
    now = datetime.now(timezone.utc)
    membership = FamilyMembership(
        user_id=user.id,
        family_id=family.id,
        role=FamilyRole.parent,
        is_owner=False,
        invited_at=now,
        accepted_at=now,
    )
    db.add(membership)
    await db.commit()
    return ProvisionedIdentity(
        user=user,
        membership=membership,
        family=family,
        created_default_family_membership=True,
    )
