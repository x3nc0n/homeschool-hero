from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models import AuditAction
from backend.schemas.maintenance import MaintenanceScheduleRequest, MaintenanceStatusRead, MaintenanceToggleRequest
from backend.security import AuthSession
from backend.services.audit import log_event
from backend.services.authorization import require_admin
from backend.services.maintenance import get_maintenance_status, set_maintenance_mode, set_maintenance_schedule

router = APIRouter(prefix='/admin/maintenance', tags=['admin'])


def _status_response(payload) -> MaintenanceStatusRead:
    return MaintenanceStatusRead(
        enabled=payload.enabled,
        env_enabled=payload.env_enabled,
        active=payload.active,
        scheduled=payload.scheduled,
        schedule_active=payload.schedule_active,
        message=payload.message,
        source=payload.source,
        start_at=payload.start_at,
        end_at=payload.end_at,
        updated_at=payload.updated_at,
        updated_by_user_id=payload.updated_by_user_id,
    )


@router.get('', response_model=MaintenanceStatusRead)
async def maintenance_status(
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_admin(action='view maintenance status')),
) -> MaintenanceStatusRead:
    _ = auth
    return _status_response(await get_maintenance_status(db))


@router.post('', response_model=MaintenanceStatusRead)
async def toggle_maintenance(
    payload: MaintenanceToggleRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_admin(action='update maintenance mode')),
) -> MaintenanceStatusRead:
    before = _status_response(await get_maintenance_status(db)).model_dump(mode='json')
    status_payload = await set_maintenance_mode(
        db,
        enabled=payload.enabled,
        message=payload.message,
        user_id=auth.user_id,
    )
    after = _status_response(status_payload).model_dump(mode='json')
    await log_event(
        db,
        action=AuditAction.config_change,
        actor=auth,
        family_id=auth.family_id,
        target_type='maintenance_mode',
        target_id='global',
        before=before,
        after=after,
        request=request,
    )
    await db.commit()
    return _status_response(status_payload)


@router.put('/schedule', response_model=MaintenanceStatusRead)
async def schedule_maintenance(
    payload: MaintenanceScheduleRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_admin(action='schedule maintenance mode')),
) -> MaintenanceStatusRead:
    before = _status_response(await get_maintenance_status(db)).model_dump(mode='json')
    status_payload = await set_maintenance_schedule(
        db,
        start_at=payload.start_at,
        end_at=payload.end_at,
        message=payload.message,
        user_id=auth.user_id,
    )
    after = _status_response(status_payload).model_dump(mode='json')
    await log_event(
        db,
        action=AuditAction.config_change,
        actor=auth,
        family_id=auth.family_id,
        target_type='maintenance_schedule',
        target_id='global',
        before=before,
        after=after,
        request=request,
    )
    await db.commit()
    return _status_response(status_payload)
