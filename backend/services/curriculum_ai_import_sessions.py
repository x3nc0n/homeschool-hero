"""Background AI curriculum import sessions.

A session row is the durable, family-scoped draft. Source bytes/text live only in the
worker's memory. Worker completion uses compare-and-swap on (id, family, status,
revision) so a cancelled, expired, or stale session is never overwritten by a late worker.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import logging
from typing import Any

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.database import AsyncSessionLocal
from backend.models import CurriculumAIImportSession, CurriculumAIImportSessionStatus, ImportedCurriculum
from backend.schemas.curriculum import CurriculumImportDocument
from backend.services.curriculum_ai_import import (
    AIImportError,
    AIImportUnavailable,
    get_ai_curriculum_import_service,
)
from backend.services.curriculum_duplicates import find_internal_duplicate_paths
from backend.services.curriculum_imports import CurriculumImportConflict, create_imported_curriculum
from backend.services.logging_config import log_action

logger = logging.getLogger(__name__)

SESSION_TTL = timedelta(hours=24)
PURGE_AFTER_EXPIRY = timedelta(days=7)
POLL_RETRY_AFTER_SECONDS = 2
MAX_SESSION_UPLOAD_BYTES = 10 * 1024 * 1024
MIN_PROCESSING_STALE = timedelta(minutes=30)
INTERNAL_DUPLICATE_WARNING = (
    'The draft contains duplicate subject, unit, or lesson names. Rename them before confirming the import.'
)
UNAVAILABLE_MESSAGE = 'AI curriculum import is unavailable'
PROCESSING_FAILED_MESSAGE = 'AI curriculum import processing failed. Please retry the import.'
PROCESSING_STALE_MESSAGE = 'AI curriculum import processing did not finish. Please retry the import.'

Status = CurriculumAIImportSessionStatus
_TASKS: dict[int, asyncio.Task[None]] = {}


@dataclass(slots=True)
class SessionSource:
    """In-memory source handed to the worker; never persisted."""

    kind: str
    name: str
    payload: bytes | None = None
    content_type: str = ''
    url: str | None = None


class SessionConflict(CurriculumImportConflict):
    code = 'curriculum_ai_import_session_conflict'
    message_key = 'errors.curriculum.ai_import_session_conflict'

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        if code:
            self.code = code


def utcnow() -> datetime:
    return datetime.now(UTC)


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def session_max_upload_bytes() -> int:
    configured = int(getattr(settings, 'upload_max_bytes', MAX_SESSION_UPLOAD_BYTES) or MAX_SESSION_UPLOAD_BYTES)
    return max(1, min(configured, MAX_SESSION_UPLOAD_BYTES))


def processing_stale_after() -> timedelta:
    """Upper bound for a healthy worker: fetch + every provider attempt + backoff, plus margin."""
    timeout = max(float(settings.ai_import_request_timeout_seconds or 0), 0.0)
    attempts = max(int(settings.ai_import_retry_attempts or 1), 1)
    backoff = max(float(settings.ai_import_retry_backoff_seconds or 0), 0.0)
    backoff_total = sum(backoff * (2 ** index) for index in range(attempts - 1))
    budget = timedelta(seconds=timeout * (attempts + 1) + backoff_total) + timedelta(minutes=5)
    return max(MIN_PROCESSING_STALE, budget)


async def create_processing_session(
    db: AsyncSession,
    *,
    family_id: int,
    user_id: int,
    source: SessionSource,
) -> CurriculumAIImportSession:
    now = utcnow()
    await db.execute(
        delete(CurriculumAIImportSession).where(
            CurriculumAIImportSession.family_id == family_id,
            CurriculumAIImportSession.expires_at < now - PURGE_AFTER_EXPIRY,
        )
    )
    session = CurriculumAIImportSession(
        family_id=family_id,
        created_by_user_id=user_id,
        status=Status.processing,
        source_kind=source.kind,
        source_name=source.name[:255],
        warnings=[],
        draft_payload=None,
        revision=1,
        expires_at=now + SESSION_TTL,
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


def schedule_processing(session_id: int, family_id: int, revision: int, source: SessionSource) -> None:
    task = asyncio.create_task(run_processing(session_id, family_id, revision, source))
    _TASKS[session_id] = task

    def _discard(done: asyncio.Task[None]) -> None:
        # Only drop the registry entry if it still points at this task.
        if _TASKS.get(session_id) is done:
            _TASKS.pop(session_id, None)

    task.add_done_callback(_discard)


def cancel_processing(session_id: int) -> None:
    task = _TASKS.pop(session_id, None)
    if task is not None and not task.done():
        task.cancel()


async def cancel_all_processing() -> None:
    tasks = list(_TASKS.values())
    _TASKS.clear()
    for task in tasks:
        task.cancel()
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)


async def run_processing(session_id: int, family_id: int, revision: int, source: SessionSource) -> None:
    service = get_ai_curriculum_import_service()
    started = utcnow()
    try:
        if source.url is not None:
            draft, extracted = await service.build_draft_from_url(source.url)
        else:
            draft, extracted = await service.build_draft_from_bytes(
                source.payload or b'',
                filename=source.name,
                content_type=source.content_type,
            )
    except asyncio.CancelledError:
        raise
    except AIImportUnavailable:
        await _complete_failed(session_id, family_id, revision, 'ai_import_unavailable', UNAVAILABLE_MESSAGE, started)
        return
    except AIImportError as exc:
        await _complete_failed(session_id, family_id, revision, exc.code, exc.message, started)
        return
    except Exception:  # noqa: BLE001
        log_action(
            logger,
            logging.ERROR,
            'AI curriculum import worker raised an unexpected error.',
            action='curriculum_ai_import_session.worker_error',
            family_id=family_id,
            details={'session_id': session_id},
            exc_info=True,
        )
        await _complete_failed(session_id, family_id, revision, 'processing_failed', PROCESSING_FAILED_MESSAGE, started)
        return
    finally:
        source.payload = None

    warnings = list(extracted.warnings or [])
    if find_internal_duplicate_paths(draft):
        warnings.append(INTERNAL_DUPLICATE_WARNING)
    await _complete(
        session_id,
        family_id,
        revision,
        values={
            'status': Status.ready,
            'draft_payload': draft.model_dump(mode='json'),
            'warnings': warnings,
            'source_name': (extracted.source_name or source.name)[:255],
        },
        outcome='ready',
        started=started,
    )


async def _complete_failed(
    session_id: int,
    family_id: int,
    revision: int,
    code: str,
    message: str,
    started: datetime,
) -> None:
    await _complete(
        session_id,
        family_id,
        revision,
        values={'status': Status.failed, 'error_code': code[:64], 'error_message': message[:500], 'draft_payload': None},
        outcome=code,
        started=started,
    )


async def _complete(
    session_id: int,
    family_id: int,
    revision: int,
    *,
    values: dict[str, Any],
    outcome: str,
    started: datetime,
) -> None:
    """CAS completion: only a still-processing session at the captured revision is updated."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            update(CurriculumAIImportSession)
            .where(
                CurriculumAIImportSession.id == session_id,
                CurriculumAIImportSession.family_id == family_id,
                CurriculumAIImportSession.status == Status.processing,
                CurriculumAIImportSession.revision == revision,
            )
            .values(**values, revision=revision + 1)
            .execution_options(synchronize_session=False)
        )
        await db.commit()
    applied = result.rowcount == 1
    log_action(
        logger,
        logging.INFO if applied else logging.WARNING,
        'AI curriculum import worker finished.' if applied else 'AI curriculum import worker result discarded.',
        action='curriculum_ai_import_session.worker_complete',
        family_id=family_id,
        details={
            'session_id': session_id,
            'outcome': outcome,
            'applied': applied,
            'duration_ms': int((utcnow() - started).total_seconds() * 1000),
        },
    )


async def get_family_session(db: AsyncSession, *, family_id: int, session_id: int) -> CurriculumAIImportSession | None:
    return (
        await db.execute(
            select(CurriculumAIImportSession).where(
                CurriculumAIImportSession.id == session_id,
                CurriculumAIImportSession.family_id == family_id,
            )
        )
    ).scalar_one_or_none()


async def _cas_transition(
    db: AsyncSession,
    session: CurriculumAIImportSession,
    *,
    values: dict[str, Any],
) -> bool:
    result = await db.execute(
        update(CurriculumAIImportSession)
        .where(
            CurriculumAIImportSession.id == session.id,
            CurriculumAIImportSession.family_id == session.family_id,
            CurriculumAIImportSession.status == session.status,
            CurriculumAIImportSession.revision == session.revision,
        )
        .values(**values, revision=session.revision + 1)
        .execution_options(synchronize_session=False)
    )
    await db.commit()
    return result.rowcount == 1


async def refresh_session_state(db: AsyncSession, session: CurriculumAIImportSession) -> CurriculumAIImportSession:
    """Apply expiry and processing-staleness guards on read."""
    now = utcnow()
    values: dict[str, Any] | None = None
    if session.status in (Status.processing, Status.ready, Status.failed) and _aware(session.expires_at) <= now:
        values = {'status': Status.expired, 'draft_payload': None}
    elif session.status == Status.processing and _aware(session.updated_at) <= now - processing_stale_after():
        values = {
            'status': Status.failed,
            'error_code': 'processing_stale',
            'error_message': PROCESSING_STALE_MESSAGE,
            'draft_payload': None,
        }
    if values is not None:
        if await _cas_transition(db, session, values=values):
            cancel_processing(session.id)
        await db.refresh(session)
    return session


async def expire_session(db: AsyncSession, session: CurriculumAIImportSession) -> None:
    if session.status == Status.confirmed:
        raise SessionConflict('Confirmed AI curriculum import sessions cannot be deleted', code='curriculum_ai_import_session_confirmed')
    cancel_processing(session.id)
    if session.status == Status.expired:
        return
    if not await _cas_transition(db, session, values={'status': Status.expired, 'draft_payload': None}):
        await db.refresh(session)
        if session.status == Status.confirmed:
            raise SessionConflict(
                'Confirmed AI curriculum import sessions cannot be deleted',
                code='curriculum_ai_import_session_confirmed',
            )
        if session.status != Status.expired:
            await expire_session(db, session)


async def confirm_session(
    db: AsyncSession,
    session: CurriculumAIImportSession,
    *,
    user_id: int,
    draft: CurriculumImportDocument,
    client_revision: int,
    acknowledged_duplicate_ids: list[int],
) -> ImportedCurriculum:
    _ensure_confirmable(session, client_revision)
    session_id = session.id
    family_id = session.family_id
    draft_payload = draft.model_dump(mode='json')

    async def claim(claim_db: AsyncSession) -> None:
        result = await claim_db.execute(
            update(CurriculumAIImportSession)
            .where(
                CurriculumAIImportSession.id == session_id,
                CurriculumAIImportSession.family_id == family_id,
                CurriculumAIImportSession.status == Status.ready,
                CurriculumAIImportSession.revision == client_revision,
                CurriculumAIImportSession.expires_at > utcnow(),
            )
            .values(
                status=Status.confirmed,
                draft_payload=draft_payload,
                confirmed_at=utcnow(),
                revision=client_revision + 1,
            )
            .execution_options(synchronize_session=False)
        )
        if result.rowcount != 1:
            raise SessionConflict(
                'AI curriculum import session changed. Reload the draft and try again.',
                code='curriculum_ai_import_session_stale',
            )

    async def on_created(created_db: AsyncSession, curriculum: ImportedCurriculum) -> None:
        await created_db.execute(
            update(CurriculumAIImportSession)
            .where(CurriculumAIImportSession.id == session_id, CurriculumAIImportSession.family_id == family_id)
            .values(confirmed_curriculum_id=curriculum.id)
            .execution_options(synchronize_session=False)
        )

    return await create_imported_curriculum(
        db,
        family_id=family_id,
        user_id=user_id,
        payload=draft,
        acknowledged_duplicate_ids=acknowledged_duplicate_ids,
        claim=claim,
        on_created=on_created,
    )


def _ensure_confirmable(session: CurriculumAIImportSession, client_revision: int) -> None:
    if session.status == Status.confirmed:
        raise SessionConflict('AI curriculum import session was already confirmed', code='curriculum_ai_import_session_confirmed')
    if session.status == Status.expired or _aware(session.expires_at) <= utcnow():
        raise SessionConflict('AI curriculum import session expired', code='curriculum_ai_import_session_expired')
    if session.status != Status.ready:
        raise SessionConflict(
            f'Cannot confirm a {session.status.value} AI curriculum import session',
            code='curriculum_ai_import_session_not_ready',
        )
    if session.revision != client_revision:
        raise SessionConflict(
            'AI curriculum import session changed. Reload the draft and try again.',
            code='curriculum_ai_import_session_stale',
        )


def session_payload(session: CurriculumAIImportSession) -> dict[str, Any]:
    payload: dict[str, Any] = {
        'id': session.id,
        'status': session.status.value,
        'source_kind': session.source_kind,
        'source_name': session.source_name,
        'warnings': list(session.warnings or []),
        'revision': session.revision,
        'expires_at': _aware(session.expires_at),
        'created_at': _aware(session.created_at),
        'updated_at': _aware(session.updated_at),
        'draft': None,
        'error': None,
    }
    if session.status == Status.ready and session.draft_payload is not None:
        payload['draft'] = session.draft_payload
    if session.status == Status.failed:
        payload['error'] = {
            'code': session.error_code or 'processing_failed',
            'message': session.error_message or PROCESSING_FAILED_MESSAGE,
        }
    return payload
