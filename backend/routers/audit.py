from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models import AuditAction, AuditEvent, User
from backend.schemas.audit import AuditEventListResponse, AuditEventRead
from backend.security import AuthSession
from backend.services.authorization import Capability, require_capabilities

router = APIRouter(prefix='/audit', tags=['audit'])


def _normalize_end_of_day(value: datetime) -> datetime:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    if value.hour == 0 and value.minute == 0 and value.second == 0 and value.microsecond == 0:
        return value + timedelta(days=1)
    return value


@router.get('', response_model=AuditEventListResponse)
async def list_audit_events(
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    actor: str | None = Query(default=None, min_length=1, max_length=255),
    entity_type: str | None = Query(default=None, min_length=1, max_length=120),
    entity_id: str | None = Query(default=None, min_length=1, max_length=255),
    action: AuditAction | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.manage_platform, action='view audit logs')),
) -> AuditEventListResponse:
    stmt = (
        select(AuditEvent, User.display_name, User.email)
        .join(User, User.id == AuditEvent.actor_user_id)
        .where(AuditEvent.family_id == auth.family_id)
    )

    if date_from is not None:
        stmt = stmt.where(AuditEvent.timestamp >= date_from)
    if date_to is not None:
        stmt = stmt.where(AuditEvent.timestamp < _normalize_end_of_day(date_to))
    if actor:
        actor_filter = actor.strip()
        lowered = f'%{actor_filter.lower()}%'
        actor_conditions = [
            func.lower(User.display_name).like(lowered),
            func.lower(User.email).like(lowered),
        ]
        if actor_filter.isdigit():
            actor_conditions.append(AuditEvent.actor_user_id == int(actor_filter))
        stmt = stmt.where(or_(*actor_conditions))
    if entity_type:
        stmt = stmt.where(AuditEvent.target_entity_type == entity_type.strip().lower())
    if entity_id:
        stmt = stmt.where(AuditEvent.target_entity_id == entity_id.strip())
    if action is not None:
        stmt = stmt.where(AuditEvent.action == action)

    total = (await db.execute(select(func.count()).select_from(stmt.order_by(None).subquery()))).scalar_one()
    total_pages = (total + page_size - 1) // page_size if total else 0
    rows = (
        await db.execute(
            stmt.order_by(AuditEvent.timestamp.desc(), AuditEvent.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).all()

    return AuditEventListResponse(
        items=[
            AuditEventRead(
                id=event.id,
                family_id=event.family_id,
                actor_user_id=event.actor_user_id,
                actor_display_name=display_name,
                actor_email=email,
                action=event.action,
                target_entity_type=event.target_entity_type,
                target_entity_id=event.target_entity_id,
                before_snapshot=event.before_snapshot,
                after_snapshot=event.after_snapshot,
                ip_address=event.ip_address,
                user_agent=event.user_agent,
                timestamp=event.timestamp,
            )
            for event, display_name, email in rows
        ],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )
