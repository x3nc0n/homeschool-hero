from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models import AuditAction
from backend.models.import_job import ImportEntityType, ImportJob, ImportJobStatus
from backend.schemas.imports import ImportJobRead
from backend.security import AuthSession, get_family_record
from backend.services.audit import log_event
from backend.services.authorization import Capability, require_capabilities
from backend.services.import_service import (
    available_template_entities,
    create_import_job,
    list_import_jobs,
    render_template_csv,
    schedule_import_execution,
    validate_import_job,
)

router = APIRouter(prefix='/imports', tags=['imports'])


async def _get_job_or_404(db: AsyncSession, job_id: int, family_id: int) -> ImportJob:
    job = await get_family_record(db, ImportJob, job_id, family_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Import job not found')
    return job


@router.get('', response_model=list[ImportJobRead])
async def list_import_history(
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.manage_curriculum, action='manage imports')),
) -> list[ImportJob]:
    return await list_import_jobs(db, family_id=auth.family_id)


@router.post('/upload', response_model=ImportJobRead, status_code=status.HTTP_201_CREATED)
async def upload_import_file(
    entity_type: ImportEntityType,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.manage_curriculum, action='manage imports')),
) -> ImportJob:
    contents = await file.read()
    try:
        return await create_import_job(
            db,
            family_id=auth.family_id,
            user_id=auth.user_id,
            entity_type=entity_type,
            upload_filename=file.filename or '',
            contents=contents,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post('/{job_id}/validate', response_model=ImportJobRead)
async def validate_import(
    job_id: int,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.manage_curriculum, action='manage imports')),
) -> ImportJob:
    job = await _get_job_or_404(db, job_id, auth.family_id)
    if job.status == ImportJobStatus.importing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='Import job is already running')
    return await validate_import_job(db, job)


@router.post('/{job_id}/execute', response_model=ImportJobRead, status_code=status.HTTP_202_ACCEPTED)
async def execute_import(
    job_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.manage_curriculum, action='manage imports')),
) -> ImportJob:
    job = await _get_job_or_404(db, job_id, auth.family_id)
    if job.status == ImportJobStatus.importing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='Import job is already running')
    if job.status == ImportJobStatus.complete:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='Import job has already completed')
    before = {
        'status': job.status.value,
        'processed_rows': job.processed_rows,
        'error_count': job.error_count,
    }
    job.status = ImportJobStatus.importing
    job.total_rows = 0
    job.processed_rows = 0
    job.error_count = 0
    job.errors = []
    job.completed_at = None
    await db.commit()
    await db.refresh(job)
    await log_event(
        db,
        action=AuditAction.config_change,
        actor=auth,
        family_id=auth.family_id,
        target_type='import_job',
        target_id=job.id,
        before=before,
        after={'status': job.status.value, 'entity_type': job.entity_type.value},
        request=request,
    )
    await db.commit()
    schedule_import_execution(job.id)
    return job


@router.get('/{job_id}/status', response_model=ImportJobRead)
async def get_import_status(
    job_id: int,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.manage_curriculum, action='manage imports')),
) -> ImportJob:
    return await _get_job_or_404(db, job_id, auth.family_id)


@router.get('/templates/{entity_type}')
async def download_template(
    entity_type: ImportEntityType,
    auth: AuthSession = Depends(require_capabilities(Capability.manage_curriculum, action='manage imports')),
) -> PlainTextResponse:
    del auth
    if entity_type not in available_template_entities():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Template not available for this import type')
    content = render_template_csv(entity_type)
    return PlainTextResponse(
        content,
        media_type='text/csv',
        headers={'Content-Disposition': f'attachment; filename="{entity_type.value}-template.csv"'},
    )
