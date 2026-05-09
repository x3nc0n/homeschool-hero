from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models import AuditAction
from backend.models.export_job import ExportJob, ExportJobStatus
from backend.schemas.exports import ExportJobCreateRequest, ExportJobRead
from backend.security import AuthSession, get_family_record
from backend.services.audit import log_event
from backend.services.authorization import Capability, require_capabilities
from backend.services.export_service import (
    create_export_job,
    delete_export_job,
    get_export_media_type,
    list_export_jobs,
    schedule_export_execution,
)

router = APIRouter(prefix='/exports', tags=['exports'])


async def _get_job_or_404(db: AsyncSession, job_id: int, family_id: int) -> ExportJob:
    job = await get_family_record(db, ExportJob, job_id, family_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Export job not found')
    return job


@router.post('', response_model=ExportJobRead, status_code=status.HTTP_201_CREATED)
async def create_export(
    payload: ExportJobCreateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.manage_family, action='manage exports')),
) -> ExportJob:
    job = await create_export_job(
        db,
        family_id=auth.family_id,
        user_id=auth.user_id,
        export_type=payload.export_type,
        format=payload.format,
        entity_types=payload.entity_types,
        date_from=payload.date_from,
    )
    await log_event(
        db,
        action=AuditAction.export,
        actor=auth,
        family_id=auth.family_id,
        target_type='export_job',
        target_id=job.id,
        before=None,
        after={
            'id': job.id,
            'status': job.status.value,
            'export_type': job.export_type.value,
            'format': job.format.value,
            'entity_types': list(job.entity_types or []),
            'date_from': job.date_from.isoformat() if job.date_from else None,
        },
        request=request,
    )
    await db.commit()
    schedule_export_execution(job.id)
    return job


@router.get('', response_model=list[ExportJobRead])
async def list_exports(
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.manage_family, action='manage exports')),
) -> list[ExportJob]:
    return await list_export_jobs(db, family_id=auth.family_id)


@router.get('/{job_id}/status', response_model=ExportJobRead)
async def get_export_status(
    job_id: int,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.manage_family, action='manage exports')),
) -> ExportJob:
    return await _get_job_or_404(db, job_id, auth.family_id)


@router.get('/{job_id}/download')
async def download_export(
    job_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.manage_family, action='manage exports')),
) -> FileResponse:
    job = await _get_job_or_404(db, job_id, auth.family_id)
    if job.status != ExportJobStatus.complete:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='Export job is not complete')
    if not job.file_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Export file not found')
    response = FileResponse(
        job.file_path,
        media_type=get_export_media_type(job.file_path),
        filename=job.file_path.split('\\')[-1].split('/')[-1],
    )
    await log_event(
        db,
        action=AuditAction.export,
        actor=auth,
        family_id=auth.family_id,
        target_type='export_download',
        target_id=job.id,
        before=None,
        after={'id': job.id, 'status': job.status.value, 'file_size': job.file_size},
        request=request,
    )
    await db.commit()
    return response


@router.delete('/{job_id}', status_code=status.HTTP_204_NO_CONTENT)
async def remove_export(
    job_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.manage_family, action='manage exports')),
) -> Response:
    job = await _get_job_or_404(db, job_id, auth.family_id)
    before = {
        'id': job.id,
        'status': job.status.value,
        'file_path': job.file_path,
        'file_size': job.file_size,
    }
    await delete_export_job(db, job)
    await log_event(
        db,
        action=AuditAction.export,
        actor=auth,
        family_id=auth.family_id,
        target_type='export_job',
        target_id=job_id,
        before=before,
        after={'deleted': True},
        request=request,
    )
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
