from __future__ import annotations

import logging
from pathlib import Path
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.database import get_db
from backend.i18n import error_detail
from backend.models import CurriculumAIImportSession, ImportedCurriculum
from backend.routers.curriculum import (
    AI_IMPORT_UNAVAILABLE_MESSAGE,
    _get_imported_curriculum_or_404,
    _parse_ai_import_request,
    _service_unavailable_response,
    curriculum_import_conflict_http_exception,
)
from backend.schemas.curriculum import (
    CurriculumAIImportSessionConfirmRequest,
    CurriculumAIImportSessionRead,
    CurriculumImportRead,
)
from backend.security import AuthSession
from backend.services.authorization import Capability, require_capabilities
from backend.services.curriculum_ai_import import (
    SUPPORTED_FILE_TYPES,
    AIImportError,
    AIImportUnavailable,
    get_ai_curriculum_import_service,
)
from backend.services.curriculum_ai_import_sessions import (
    POLL_RETRY_AFTER_SECONDS,
    SessionSource,
    confirm_session,
    create_processing_session,
    expire_session,
    get_family_session,
    refresh_session_state,
    schedule_processing,
    session_max_upload_bytes,
    session_payload,
)
from backend.services.curriculum_imports import CurriculumImportConflict
from backend.validation import sanitize_filename

router = APIRouter(prefix='/curriculum/ai-import-sessions', tags=['curriculum'])
logger = logging.getLogger(__name__)
SESSION_NOT_FOUND = 'AI curriculum import session not found'


def _bad_request(code: str, message: str, status_code: int = status.HTTP_400_BAD_REQUEST) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail=error_detail(code=code, message_key=f'errors.curriculum.{code}', default_message=message),
    )


async def _get_session_or_404(db: AsyncSession, auth: AuthSession, session_id: int) -> CurriculumAIImportSession:
    session = await get_family_session(db, family_id=auth.family_id, session_id=session_id)
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=SESSION_NOT_FOUND)
    return session


async def _read_bounded_upload(upload: object) -> tuple[bytes, str, str]:
    service = get_ai_curriculum_import_service()
    raw_name = getattr(upload, 'filename', None) or 'uploaded-document'
    filename = (sanitize_filename(raw_name) or 'uploaded-document')[:255]
    content_type = getattr(upload, 'content_type', None) or ''
    if service._detect_content_type(filename=filename, content_type=content_type) not in SUPPORTED_FILE_TYPES:
        supported = ', '.join(sorted(SUPPORTED_FILE_TYPES))
        raise _bad_request('unsupported_document_type', f'Unsupported document type for AI import. Supported types: {supported}')
    max_bytes = session_max_upload_bytes()
    payload = await upload.read(max_bytes + 1)
    if not payload:
        raise _bad_request('empty_document', 'The provided document is empty')
    if len(payload) > max_bytes:
        raise _bad_request(
            'document_too_large',
            f'The provided document exceeds the {max_bytes} byte limit',
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
        )
    return payload, filename, content_type


def _url_source_name(url: str) -> str:
    parsed = urlparse(url)
    return (Path(parsed.path).name or parsed.hostname or 'url-import')[:255]


@router.post(
    '',
    response_model=CurriculumAIImportSessionRead,
    status_code=status.HTTP_202_ACCEPTED,
    summary='Start a background AI curriculum import draft',
    description=(
        'Accepts exactly one source: a multipart `file` (.txt, .pdf, .docx) or JSON `{"url": "..."}`. '
        'Persists a `processing` session and returns 202 immediately with `Location` and `Retry-After` headers. '
        'Poll `GET /curriculum/ai-import-sessions/{id}` until the status is `ready` or `failed`. '
        'No curriculum is created until the draft is confirmed.'
    ),
)
async def create_curriculum_ai_import_session(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.manage_curriculum, action='draft AI curriculum import')),
):
    upload, url = await _parse_ai_import_request(request)
    if url and not settings.online_curriculum_enabled:
        return _service_unavailable_response(
            request,
            detail='Online curriculum URL imports are disabled by deployment policy',
            code='online_curriculum_disabled',
        )
    service = get_ai_curriculum_import_service()
    try:
        service._ensure_configured()
    except AIImportUnavailable:
        logger.warning('AI curriculum import is unavailable.')
        return _service_unavailable_response(request, detail=AI_IMPORT_UNAVAILABLE_MESSAGE, code='ai_import_unavailable')
    if upload is not None:
        payload, filename, content_type = await _read_bounded_upload(upload)
        source = SessionSource(kind='file', name=filename, payload=payload, content_type=content_type)
    else:
        try:
            normalized_url, _ = service._parse_http_url(url or '', error_message='AI import URL must be a valid http or https URL')
        except AIImportError as exc:
            raise _bad_request(exc.code if exc.code != 'ai_import_failed' else 'invalid_source_url', exc.message) from None
        source = SessionSource(kind='url', name=_url_source_name(normalized_url), url=normalized_url)

    session = await create_processing_session(db, family_id=auth.family_id, user_id=auth.user_id, source=source)
    schedule_processing(session.id, session.family_id, session.revision, source)
    response.headers['Location'] = f'{request.url.path.rstrip("/")}/{session.id}'
    response.headers['Retry-After'] = str(POLL_RETRY_AFTER_SECONDS)
    return session_payload(session)


@router.get('/{session_id:int}', response_model=CurriculumAIImportSessionRead)
async def read_curriculum_ai_import_session(
    session_id: int,
    response: Response,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.manage_curriculum, action='view AI curriculum import draft')),
):
    session = await refresh_session_state(db, await _get_session_or_404(db, auth, session_id))
    if session.status.value == 'processing':
        response.headers['Retry-After'] = str(POLL_RETRY_AFTER_SECONDS)
    return session_payload(session)


@router.delete('/{session_id:int}', status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_curriculum_ai_import_session(
    session_id: int,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.manage_curriculum, action='discard AI curriculum import draft')),
) -> Response:
    session = await _get_session_or_404(db, auth, session_id)
    try:
        await expire_session(db, session)
    except CurriculumImportConflict as exc:
        raise curriculum_import_conflict_http_exception(exc) from None
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post('/{session_id:int}/confirm', response_model=CurriculumImportRead, status_code=status.HTTP_201_CREATED)
async def confirm_curriculum_ai_import_session(
    session_id: int,
    payload: CurriculumAIImportSessionConfirmRequest,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.manage_curriculum, action='confirm AI curriculum import')),
) -> ImportedCurriculum:
    session = await refresh_session_state(db, await _get_session_or_404(db, auth, session_id))
    try:
        created = await confirm_session(
            db,
            session,
            user_id=auth.user_id,
            draft=payload.draft,
            client_revision=payload.client_revision,
            acknowledged_duplicate_ids=payload.acknowledged_duplicate_ids,
        )
    except CurriculumImportConflict as exc:
        raise curriculum_import_conflict_http_exception(exc) from None
    return await _get_imported_curriculum_or_404(db, created.id, auth.family_id)
