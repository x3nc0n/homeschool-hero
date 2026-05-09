from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models import AuditAction, BackupJob
from backend.schemas.backups import BackupConfigRead, BackupJobRead, BackupStatusRead, BackupTriggerRequest
from backend.security import AuthSession, get_family_record
from backend.services.audit import log_event
from backend.services.authorization import Capability, require_capabilities
from backend.services.backup_service import (
    create_backup_job,
    get_backup_configuration,
    get_backup_status,
    list_backup_jobs,
    schedule_backup_execution,
)

router = APIRouter(prefix='/backups', tags=['backups'])


async def _get_job_or_404(db: AsyncSession, job_id: int, family_id: int) -> BackupJob:
    job = await get_family_record(db, BackupJob, job_id, family_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Backup job not found')
    return job


@router.post('/trigger', response_model=BackupJobRead, status_code=status.HTTP_201_CREATED)
async def trigger_backup(
    payload: BackupTriggerRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.manage_family, action='manage backups')),
) -> BackupJob:
    job = await create_backup_job(
        db,
        family_id=auth.family_id,
        user_id=auth.user_id,
        backup_type=payload.backup_type,
    )
    await log_event(
        db,
        action=AuditAction.export,
        actor=auth,
        family_id=auth.family_id,
        target_type='backup_job',
        target_id=job.id,
        before=None,
        after={
            'id': job.id,
            'backup_type': job.backup_type.value,
            'destination': job.destination.value,
            'status': job.status.value,
        },
        request=request,
    )
    await db.commit()
    schedule_backup_execution(job.id)
    return job


@router.get('/config', response_model=BackupConfigRead)
async def backup_config(
    auth: AuthSession = Depends(require_capabilities(Capability.manage_family, action='manage backups')),
) -> BackupConfigRead:
    _ = auth
    return BackupConfigRead.model_validate(get_backup_configuration())


@router.get('/status', response_model=BackupStatusRead)
async def backup_status(
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.manage_family, action='manage backups')),
) -> BackupStatusRead:
    payload = await get_backup_status(db, family_id=auth.family_id)
    return BackupStatusRead(
        configured=payload['configured'],
        scheduler_enabled=payload['scheduler_enabled'],
        destination=payload['destination'],
        next_scheduled=payload['next_scheduled'],
        restic_enabled=payload['restic_enabled'],
        validation=payload['validation'],
        last_backup=BackupJobRead.model_validate(payload['last_backup']) if payload['last_backup'] is not None else None,
        last_success=BackupJobRead.model_validate(payload['last_success']) if payload['last_success'] is not None else None,
    )


@router.get('', response_model=list[BackupJobRead])
async def list_backups(
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.manage_family, action='manage backups')),
) -> list[BackupJob]:
    return await list_backup_jobs(db, family_id=auth.family_id)


@router.get('/{job_id}', response_model=BackupJobRead)
async def get_backup(
    job_id: int,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.manage_family, action='manage backups')),
) -> BackupJob:
    return await _get_job_or_404(db, job_id, auth.family_id)
