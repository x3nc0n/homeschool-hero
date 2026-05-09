from __future__ import annotations

from typing import Any

from fastapi import Request
from fastapi.encoders import jsonable_encoder
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import AuditAction, AuditEvent
from backend.security import AuthSession


def _actor_user_id(actor: AuthSession | Any) -> int:
    if isinstance(actor, AuthSession):
        return actor.user_id
    actor_id = getattr(actor, 'id', None)
    if isinstance(actor_id, int):
        return actor_id
    raise ValueError('actor must expose a user id')


def _snapshot(payload: Any) -> dict[str, Any] | None:
    if payload is None:
        return None
    encoded = jsonable_encoder(payload)
    return encoded if isinstance(encoded, dict) else {'value': encoded}


async def log_event(
    db: AsyncSession,
    *,
    action: AuditAction,
    actor: AuthSession | Any,
    family_id: int,
    target_type: str,
    target_id: int | str | None,
    before: Any,
    after: Any,
    request: Request | None,
) -> AuditEvent:
    audit_event = AuditEvent(
        family_id=family_id,
        actor_user_id=_actor_user_id(actor),
        action=action,
        target_entity_type=target_type,
        target_entity_id=str(target_id) if target_id is not None else None,
        before_snapshot=_snapshot(before),
        after_snapshot=_snapshot(after),
        ip_address=request.client.host if request and request.client else None,
        user_agent=request.headers.get('user-agent') if request else None,
    )
    db.add(audit_event)
    await db.flush()
    return audit_event
