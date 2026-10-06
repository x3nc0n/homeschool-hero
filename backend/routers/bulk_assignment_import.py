from __future__ import annotations

import json
import logging
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models import AuditAction
from backend.models.bulk_assignment_import import BulkAssignmentImportSession, BulkAssignmentImportStatus
from backend.schemas.bulk_assignment_import import (
    BulkAssignmentImportConfirmRequest,
    BulkAssignmentImportConfirmResponse,
    BulkAssignmentImportItem,
    BulkAssignmentImportPatch,
    BulkAssignmentImportRead,
    BulkAssignmentImportTarget,
    BulkImportDefaults,
)
from backend.security import AuthSession
from backend.services.audit import log_event
from backend.services.authorization import Capability, require_capabilities
from backend.services.bulk_assignment_import import (
    BulkAssignmentImportError,
    bulk_assignment_processing_stale_minutes,
    get_bulk_assignment_import_service,
    schedule_assignment_import_processing,
)
from backend.services.curriculum_ai_import import AIImportError, AIImportUnavailable

logger = logging.getLogger(__name__)
router = APIRouter(prefix='/assignment-import-sessions', tags=['assignment-import-sessions'])
AI_IMPORT_UNAVAILABLE_DETAIL = 'AI assignment import is unavailable'


async def _get_session_or_404(db: AsyncSession, auth: AuthSession, session_id: int) -> BulkAssignmentImportSession:
    session = (
        await db.execute(
            select(BulkAssignmentImportSession).where(
                BulkAssignmentImportSession.id == session_id,
                BulkAssignmentImportSession.family_id == auth.family_id,
            )
        )
    ).scalar_one_or_none()
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Assignment import session not found')
    expires_at = session.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    if expires_at <= datetime.now(UTC) and session.status not in {
        BulkAssignmentImportStatus.confirmed,
        BulkAssignmentImportStatus.expired,
    }:
        session.status = BulkAssignmentImportStatus.expired
        await db.commit()
        raise HTTPException(status_code=status.HTTP_410_GONE, detail='Assignment import session expired')
    updated_at = session.updated_at
    if updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=UTC)
    if (
        session.status == BulkAssignmentImportStatus.processing
        and updated_at <= datetime.now(UTC) - timedelta(minutes=bulk_assignment_processing_stale_minutes())
    ):
        payload = dict(session.draft_payload or {})
        payload['error_message'] = 'Assignment import processing did not finish. Please retry the upload.'
        payload.setdefault('parse_method', 'ai')
        payload.setdefault('items', [])
        payload.setdefault('summary', {'total': 0, 'ready': 0, 'needs_clarification': 0, 'invalid': 0})
        session.draft_payload = payload
        session.status = BulkAssignmentImportStatus.failed
        session.revision += 1
        await db.commit()
        await db.refresh(session)
    return session


def _parse_defaults(raw_defaults: str | None) -> BulkImportDefaults | None:
    if not raw_defaults:
        return None
    try:
        parsed = json.loads(raw_defaults)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='defaults must be valid JSON') from exc
    return BulkImportDefaults.model_validate(parsed)


@router.post(
    '',
    response_model=BulkAssignmentImportRead,
    status_code=status.HTTP_201_CREATED,
    summary='Create an AI assignment draft from TXT, Markdown, JSON, CSV, TSV, DOCX, PDF, or XLSX',
    description=(
        'Upload a planning document (default 10 MiB maximum). XLSX extraction preserves all worksheet names, '
        'row/cell coordinates, dates, and merged headers. Formulas are not executed; missing saved results '
        'are explicitly marked and reported in warnings. Legacy XLS and encrypted workbooks are unsupported. '
        'Malformed, empty, mismatched-type, or resource-limit-exceeding workbooks return 400. '
        'JSON/CSV/TSV require UTF-8 (BOM accepted); schema keys, headers, delimiters and rows are preserved. '
        'Malformed JSON/quoted tables and oversized structured text return 400 without AI invocation. '
        'JSON matching the assignment import document shape is parsed deterministically without AI; other JSON falls back to AI. '
        'No assignments are created until the draft is confirmed.'
    ),
)
async def create_assignment_import_session(
    file: UploadFile = File(..., description='Planning file: .txt, .md, .json, .csv, .tsv, .docx, .pdf, or unencrypted .xlsx (not .xls).'),
    defaults: str | None = Form(default=None),
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.manage_curriculum, action='create assignment import draft')),
) -> dict:
    service = get_bulk_assignment_import_service()
    try:
        parsed_defaults = _parse_defaults(defaults)
        extracted = await service.extract_upload(file)
        await service.validate_defaults(db, family_id=auth.family_id, defaults=parsed_defaults)
        parsed = service.parse_structured_json(extracted.extracted)
        if parsed is not None:
            session = await service.create_draft_session(
                db,
                family_id=auth.family_id,
                user_id=auth.user_id,
                source=extracted,
                parsed=parsed,
                defaults=parsed_defaults,
                parse_method='structured_json',
            )
            return service.read_session_payload(session, include_items=False)
        service.ensure_ai_configured()
        session = await service.create_processing_session(
            db,
            family_id=auth.family_id,
            user_id=auth.user_id,
            source=extracted,
        )
        schedule_assignment_import_processing(session.id, extracted, parsed_defaults)
    except AIImportUnavailable:
        logger.exception('AI assignment import is unavailable.')
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={'detail': AI_IMPORT_UNAVAILABLE_DETAIL, 'code': 'ai_import_unavailable'},
        )
    except (AIImportError, BulkAssignmentImportError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return service.read_session_payload(session, include_items=False)


@router.get('/{session_id:int}', response_model=BulkAssignmentImportRead)
async def read_assignment_import_session(
    session_id: int,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.manage_curriculum, action='read assignment import draft')),
) -> dict:
    session = await _get_session_or_404(db, auth, session_id)
    return get_bulk_assignment_import_service().read_session_payload(session, include_items=True)


@router.patch('/{session_id:int}', response_model=BulkAssignmentImportRead)
async def patch_assignment_import_session(
    session_id: int,
    payload: BulkAssignmentImportPatch,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.manage_curriculum, action='update assignment import draft')),
) -> dict:
    session = await _get_session_or_404(db, auth, session_id)
    if session.status in {
        BulkAssignmentImportStatus.processing,
        BulkAssignmentImportStatus.failed,
        BulkAssignmentImportStatus.confirmed,
        BulkAssignmentImportStatus.expired,
    }:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f'Cannot update a {session.status.value} import session')
    draft_payload = dict(session.draft_payload or {})
    items = [BulkAssignmentImportItem.model_validate(item) for item in draft_payload.get('items', [])]
    questions_by_id = {question.get('id'): question for question in session.questions or []}

    for answer in payload.answers:
        question = questions_by_id.get(answer.question_id)
        if not question:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Unknown clarification question')
        indexes = answer.apply_to_assignment_indexes
        if indexes is None:
            indexes = list(question.get('assignment_indexes') or [])
        field = question.get('field')
        for index in indexes:
            if index < 0 or index >= len(items):
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Clarification assignment index is out of range')
            item = items[index]
            if field == 'targets':
                values = answer.value if isinstance(answer.value, list) else ([answer.value] if answer.value is not None else [])
                item.targets = [BulkAssignmentImportTarget(student_id=int(value)) for value in values]
            elif field in {'subject_id', 'grading_period_id', 'lesson_plan_id'}:
                setattr(item, field, int(answer.value) if answer.value is not None else None)
            elif field == 'title':
                item.title = str(answer.value or '').strip() or None

    by_id = {item.client_item_id: index for index, item in enumerate(items)}
    for edited in payload.items:
        index = by_id.get(edited.client_item_id)
        if index is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Unknown import item')
        items[index] = edited

    draft_payload['items'] = [item.model_dump(mode='json') for item in items]
    service = get_bulk_assignment_import_service()
    draft_payload, questions, status_value = await service.revalidate_payload(db, family_id=auth.family_id, payload=draft_payload)
    session.draft_payload = draft_payload
    session.questions = questions
    session.status = status_value
    session.revision += 1
    await db.commit()
    await db.refresh(session)
    return service.read_session_payload(session, include_items=True)


@router.post('/{session_id:int}/confirm', response_model=BulkAssignmentImportConfirmResponse, status_code=status.HTTP_201_CREATED)
async def confirm_assignment_import_session(
    session_id: int,
    payload: BulkAssignmentImportConfirmRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.manage_curriculum, action='confirm assignment import draft')),
) -> BulkAssignmentImportConfirmResponse:
    session = await _get_session_or_404(db, auth, session_id)
    if session.status == BulkAssignmentImportStatus.confirmed:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='Assignment import session already confirmed')
    if session.status != BulkAssignmentImportStatus.ready:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f'Cannot confirm a {session.status.value} import session')
    if payload.client_revision is not None and payload.client_revision != session.revision:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='Assignment import session revision is stale')
    service = get_bulk_assignment_import_service()
    try:
        created_ids, skipped_ids = await service.confirm(
            db,
            family_id=auth.family_id,
            payload=session.draft_payload,
            item_ids=payload.item_ids,
        )
        session.status = BulkAssignmentImportStatus.confirmed
        session.confirmed_at = datetime.now(UTC)
        session.revision += 1
        await log_event(
            db,
            action=AuditAction.config_change,
            actor=auth,
            family_id=auth.family_id,
            target_type='bulk_assignment_import_session',
            target_id=session.id,
            before=None,
            after={'assignment_count': len(created_ids), 'session_id': session.id},
            request=request,
        )
        await db.commit()
    except HTTPException:
        await db.rollback()
        raise
    return BulkAssignmentImportConfirmResponse(
        created_assignment_ids=created_ids,
        skipped_item_ids=skipped_ids,
        assignment_count=len(created_ids),
    )


@router.delete('/{session_id:int}', status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_assignment_import_session(
    session_id: int,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.manage_curriculum, action='delete assignment import draft')),
) -> None:
    session = await _get_session_or_404(db, auth, session_id)
    if session.status != BulkAssignmentImportStatus.confirmed:
        session.status = BulkAssignmentImportStatus.expired
        session.revision += 1
        await db.commit()
