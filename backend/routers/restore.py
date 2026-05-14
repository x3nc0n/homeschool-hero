from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import AsyncSessionLocal, get_db
from backend.models import AuditAction
from backend.schemas.restore import (
    AvailableBackupRead,
    RestoreExecuteRequest,
    RestoreExecutionRead,
    RestoreValidationRead,
    RetentionCleanupRead,
    RetentionPolicyRead,
    SelectiveRestoreRequest,
)
from backend.security import AuthSession
from backend.services.audit import log_event
from backend.services.authorization import require_admin
from backend.services.restore_service import (
    cleanup_retained_backups,
    execute_restore,
    get_retention_policy,
    list_available_backups,
    notify_restore_result,
    selective_restore,
    update_retention_policy,
    validate_backup,
)

router = APIRouter(prefix='/restore', tags=['restore'])


def _backup_to_schema(item) -> AvailableBackupRead:
    return AvailableBackupRead(
        backup_id=item.backup_id,
        label=item.label,
        file_path=str(item.path),
        destination=item.destination,
        backup_type=item.backup_type,
        storage_mode=item.storage_mode,
        created_at=item.created_at,
        completed_at=item.completed_at,
        size_bytes=item.size_bytes,
        manifest_present=item.manifest is not None,
        manifest_version=item.manifest.get('version') if item.manifest else None,
        available_entities=item.available_entities,
        metadata=item.metadata,
    )


async def _record_restore_audit(
    *,
    auth: AuthSession,
    request: Request,
    action: str,
    target_id: str,
    before: object | None,
    after: object | None,
) -> None:
    async with AsyncSessionLocal() as db:
        await log_event(
            db,
            action=AuditAction.restore if action != 'retention' else AuditAction.config_change,
            actor=auth,
            family_id=auth.family_id,
            target_type='restore' if action != 'retention' else 'backup_retention',
            target_id=target_id,
            before=before,
            after=after,
            request=request,
        )
        await db.commit()


@router.get('/backups', response_model=list[AvailableBackupRead])
async def available_backups(
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_admin(action='manage restores')),
) -> list[AvailableBackupRead]:
    return [_backup_to_schema(item) for item in await list_available_backups(db, family_id=auth.family_id)]


@router.post('/validate/{backup_id}', response_model=RestoreValidationRead)
async def validate_restore_backup(
    backup_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_admin(action='manage restores')),
) -> RestoreValidationRead:
    result = await validate_backup(db, family_id=auth.family_id, user_id=auth.user_id, backup_id=backup_id)
    await log_event(
        db,
        action=AuditAction.restore,
        actor=auth,
        family_id=auth.family_id,
        target_type='restore_validation',
        target_id=backup_id,
        before=None,
        after=result.model_dump(),
        request=request,
    )
    await db.commit()
    return result


@router.post('/execute/{backup_id}', response_model=RestoreExecutionRead)
async def execute_restore_backup(
    backup_id: str,
    payload: RestoreExecuteRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_admin(action='manage restores')),
) -> RestoreExecutionRead:
    try:
        result = await execute_restore(
            db,
            family_id=auth.family_id,
            user_id=auth.user_id,
            backup_id=backup_id,
            confirmation_token=payload.confirmation_token,
            include_database=payload.include_database,
            include_files=payload.include_files,
            auto_backup=payload.auto_backup,
        )
    except Exception as exc:
        await db.rollback()
        await notify_restore_result(family_id=auth.family_id, success=False, message=str(exc))
        await _record_restore_audit(
            auth=auth,
            request=request,
            action='restore-failed',
            target_id=backup_id,
            before=None,
            after={'backup_id': backup_id, 'status': 'failed', 'message': str(exc)},
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    await notify_restore_result(family_id=auth.family_id, success=True, message=result.message)
    await _record_restore_audit(
        auth=auth,
        request=request,
        action='restore-executed',
        target_id=backup_id,
        before=None,
        after=result.model_dump(),
    )
    return result


@router.post('/selective/{backup_id}', response_model=RestoreExecutionRead)
async def execute_selective_restore(
    backup_id: str,
    payload: SelectiveRestoreRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_admin(action='manage restores')),
) -> RestoreExecutionRead:
    try:
        result = await selective_restore(
            db,
            family_id=auth.family_id,
            user_id=auth.user_id,
            backup_id=backup_id,
            confirmation_token=payload.confirmation_token,
            entity_types=payload.entity_types,
            overwrite_existing=payload.overwrite_existing,
            auto_backup=payload.auto_backup,
        )
    except Exception as exc:
        await db.rollback()
        await notify_restore_result(family_id=auth.family_id, success=False, message=str(exc))
        await _record_restore_audit(
            auth=auth,
            request=request,
            action='selective-failed',
            target_id=backup_id,
            before=None,
            after={'backup_id': backup_id, 'status': 'failed', 'message': str(exc)},
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    await notify_restore_result(family_id=auth.family_id, success=True, message=result.message)
    await _record_restore_audit(
        auth=auth,
        request=request,
        action='selective-executed',
        target_id=backup_id,
        before=None,
        after=result.model_dump(),
    )
    return result


@router.get('/retention', response_model=RetentionPolicyRead)
async def current_retention_policy(
    auth: AuthSession = Depends(require_admin(action='manage restores')),
) -> RetentionPolicyRead:
    _ = auth
    return RetentionPolicyRead(**get_retention_policy())


@router.put('/retention', response_model=RetentionPolicyRead)
async def save_retention_policy(
    payload: RetentionPolicyRead,
    request: Request,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_admin(action='manage restores')),
) -> RetentionPolicyRead:
    before = get_retention_policy()
    updated = update_retention_policy(retention_days=payload.retention_days, retention_count=payload.retention_count)
    await log_event(
        db,
        action=AuditAction.config_change,
        actor=auth,
        family_id=auth.family_id,
        target_type='backup_retention',
        target_id='runtime',
        before=before,
        after=updated,
        request=request,
    )
    await db.commit()
    return RetentionPolicyRead(**updated)


@router.post('/cleanup', response_model=RetentionCleanupRead)
async def cleanup_restore_backups(
    request: Request,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_admin(action='manage restores')),
) -> RetentionCleanupRead:
    result = await cleanup_retained_backups()
    await log_event(
        db,
        action=AuditAction.config_change,
        actor=auth,
        family_id=auth.family_id,
        target_type='backup_cleanup',
        target_id='runtime',
        before=None,
        after=result,
        request=request,
    )
    await db.commit()
    return RetentionCleanupRead(**result)
