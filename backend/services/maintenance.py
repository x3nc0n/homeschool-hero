from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.models import FamilyMembership, FamilyRole, MaintenanceMode
from backend.security import AuthSession, SessionClaims
from backend.services.rbac import AppRole

ADMIN_BYPASS_ROLES = {FamilyRole.parent, FamilyRole.co_parent}


@dataclass(slots=True)
class MaintenanceStatus:
    enabled: bool
    env_enabled: bool
    active: bool
    scheduled: bool
    schedule_active: bool
    message: str
    source: str
    start_at: datetime | None
    end_at: datetime | None
    updated_at: datetime | None
    updated_by_user_id: int | None


def default_maintenance_message() -> str:
    return settings.maintenance_message.strip()


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _role_can_bypass(role: FamilyRole | str, *, is_owner: bool = False) -> bool:
    if is_owner:
        return True
    normalized = role if isinstance(role, FamilyRole) else FamilyRole(role)
    return normalized in ADMIN_BYPASS_ROLES


def _app_roles_can_bypass(app_roles: list[str] | tuple[str, ...] | None) -> bool:
    return bool(app_roles and AppRole.admin.value in app_roles)


def auth_can_bypass_maintenance(auth: AuthSession) -> bool:
    return _app_roles_can_bypass(auth.app_roles) or _role_can_bypass(auth.role, is_owner=auth.is_owner)


def membership_can_bypass_maintenance(membership: FamilyMembership) -> bool:
    return _role_can_bypass(membership.role, is_owner=membership.is_owner)


async def get_maintenance_record(db: AsyncSession) -> MaintenanceMode | None:
    result = await db.execute(select(MaintenanceMode).where(MaintenanceMode.id == 1))
    return result.scalar_one_or_none()


async def get_maintenance_status(db: AsyncSession) -> MaintenanceStatus:
    record = await get_maintenance_record(db)
    now = _utcnow()
    message = record.message if record is not None else default_maintenance_message()
    start_at = _normalize_datetime(record.scheduled_start_at if record is not None else None)
    end_at = _normalize_datetime(record.scheduled_end_at if record is not None else None)
    env_enabled = settings.maintenance_mode
    manual_enabled = bool(record.enabled) if record is not None else False
    scheduled = start_at is not None and end_at is not None
    schedule_active = bool(scheduled and start_at <= now < end_at)
    active = env_enabled or manual_enabled or schedule_active
    if env_enabled:
        source = 'env'
    elif manual_enabled:
        source = 'manual'
    elif schedule_active:
        source = 'scheduled'
    else:
        source = 'off'
    return MaintenanceStatus(
        enabled=manual_enabled,
        env_enabled=env_enabled,
        active=active,
        scheduled=scheduled,
        schedule_active=schedule_active,
        message=message,
        source=source,
        start_at=start_at,
        end_at=end_at,
        updated_at=_normalize_datetime(record.updated_at if record is not None else None),
        updated_by_user_id=record.updated_by_user_id if record is not None else None,
    )


async def ensure_maintenance_record(db: AsyncSession) -> MaintenanceMode:
    record = await get_maintenance_record(db)
    if record is not None:
        return record
    record = MaintenanceMode(id=1, enabled=False, message=default_maintenance_message())
    db.add(record)
    await db.flush()
    return record


async def set_maintenance_mode(
    db: AsyncSession,
    *,
    enabled: bool,
    message: str | None,
    user_id: int | None,
) -> MaintenanceStatus:
    record = await ensure_maintenance_record(db)
    record.enabled = enabled
    if message is not None:
        record.message = message
    elif not record.message:
        record.message = default_maintenance_message()
    record.updated_by_user_id = user_id
    await db.flush()
    return await get_maintenance_status(db)


async def set_maintenance_schedule(
    db: AsyncSession,
    *,
    start_at: datetime | None,
    end_at: datetime | None,
    message: str | None,
    user_id: int | None,
) -> MaintenanceStatus:
    record = await ensure_maintenance_record(db)
    record.scheduled_start_at = _normalize_datetime(start_at)
    record.scheduled_end_at = _normalize_datetime(end_at)
    if message is not None:
        record.message = message
    elif not record.message:
        record.message = default_maintenance_message()
    record.updated_by_user_id = user_id
    await db.flush()
    return await get_maintenance_status(db)


async def session_can_bypass_maintenance(db: AsyncSession, claims: SessionClaims | None) -> bool:
    if claims is None:
        return False
    if _app_roles_can_bypass(claims.get('app_roles')):
        return True
    if claims.get('auth_type') == 'bearer' and claims.get('family_role'):
        return _role_can_bypass(claims['family_role'], is_owner=bool(claims.get('is_owner', False)))
    result = await db.execute(
        select(FamilyMembership.role, FamilyMembership.is_owner)
        .where(
            FamilyMembership.user_id == claims['user_id'],
            FamilyMembership.family_id == claims['family_id'],
            FamilyMembership.accepted_at.is_not(None),
        )
    )
    row = result.one_or_none()
    if row is None:
        return False
    role, is_owner = row
    return _role_can_bypass(role, is_owner=is_owner)
