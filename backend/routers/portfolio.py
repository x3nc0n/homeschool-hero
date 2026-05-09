from __future__ import annotations

import mimetypes
from datetime import date
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.config import settings
from backend.database import get_db
from backend.models import (
    Assignment,
    AuditAction,
    PortfolioCollection,
    PortfolioEntry,
    PortfolioEntryType,
    Student,
    Subject,
    Submission,
)
from backend.schemas.portfolio import (
    PortfolioCollectionCreate,
    PortfolioCollectionRead,
    PortfolioCollectionUpdate,
    PortfolioEntryCreate,
    PortfolioEntryRead,
    PortfolioEntryUpdate,
    PortfolioShareLinkRead,
    PublicPortfolioCollectionRead,
    PublicPortfolioEntryRead,
)
from backend.schemas.students import StudentRead
from backend.schemas.subjects import SubjectRead
from backend.schemas.submissions import SubmissionVersionRead
from backend.security import AuthSession, get_auth_session
from backend.services.audit import log_event
from backend.services.authorization import ensure_student_scope
from backend.validation import sanitize_filename

router = APIRouter(prefix='/portfolio', tags=['portfolio'])


def _entry_options():
    return (
        selectinload(PortfolioEntry.student),
        selectinload(PortfolioEntry.subject),
        selectinload(PortfolioEntry.assignment),
        selectinload(PortfolioEntry.submission).selectinload(Submission.grading_job),
    )


async def _get_student_or_404(db: AsyncSession, *, family_id: int, student_id: int) -> Student:
    student = await db.get(Student, student_id)
    if student is None or student.family_id != family_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Student not found')
    return student


async def _get_entry_or_404(db: AsyncSession, *, family_id: int, entry_id: int) -> PortfolioEntry:
    result = await db.execute(
        select(PortfolioEntry)
        .options(*_entry_options())
        .where(PortfolioEntry.id == entry_id, PortfolioEntry.family_id == family_id)
    )
    entry = result.scalar_one_or_none()
    if entry is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Portfolio entry not found')
    return entry


async def _get_collection_or_404(db: AsyncSession, *, family_id: int, collection_id: int) -> PortfolioCollection:
    result = await db.execute(
        select(PortfolioCollection).where(PortfolioCollection.id == collection_id, PortfolioCollection.family_id == family_id)
    )
    collection = result.scalar_one_or_none()
    if collection is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Portfolio collection not found')
    return collection


async def _load_entries_by_ids(
    db: AsyncSession,
    *,
    family_id: int,
    entry_ids: list[int],
    student_id: int | None = None,
) -> list[PortfolioEntry]:
    if not entry_ids:
        return []
    stmt = (
        select(PortfolioEntry)
        .options(*_entry_options())
        .where(PortfolioEntry.family_id == family_id, PortfolioEntry.id.in_(entry_ids))
    )
    if student_id is not None:
        stmt = stmt.where(PortfolioEntry.student_id == student_id)
    rows = list((await db.execute(stmt)).scalars().all())
    order = {entry_id: index for index, entry_id in enumerate(entry_ids)}
    rows.sort(key=lambda item: order.get(item.id, len(order)))
    return rows


def _ensure_portfolio_access(auth: AuthSession, *, student_id: int, action: str) -> None:
    ensure_student_scope(auth, student_id, action=action)


async def _validate_entry_references(
    db: AsyncSession,
    *,
    family_id: int,
    payload: PortfolioEntryCreate | PortfolioEntryUpdate,
) -> None:
    await _get_student_or_404(db, family_id=family_id, student_id=payload.student_id)
    subject = None
    assignment = None
    if payload.subject_id is not None:
        subject = await db.get(Subject, payload.subject_id)
        if subject is None or subject.family_id != family_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Subject not found')
    if payload.assignment_id is not None:
        assignment = await db.get(Assignment, payload.assignment_id)
        if assignment is None or assignment.family_id != family_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Assignment not found')
    if subject is not None and assignment is not None and assignment.subject_id != subject.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Assignment does not match the selected subject')
    if payload.submission_id is not None:
        submission = await db.get(Submission, payload.submission_id)
        if submission is None or submission.family_id != family_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Submission not found')
        if submission.student_id != payload.student_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Submission does not belong to the selected student')
        if payload.assignment_id is not None and submission.assignment_id != payload.assignment_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Submission does not match the selected assignment')


async def _validate_collection_entries(
    db: AsyncSession,
    *,
    family_id: int,
    student_id: int,
    entry_ids: list[int],
) -> None:
    await _get_student_or_404(db, family_id=family_id, student_id=student_id)
    entries = await _load_entries_by_ids(db, family_id=family_id, entry_ids=entry_ids, student_id=student_id)
    if len(entries) != len(entry_ids):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Collections may only include entries for the selected student in the current family',
        )


async def _serialize_collection(db: AsyncSession, collection: PortfolioCollection) -> PortfolioCollectionRead:
    entries = await _load_entries_by_ids(
        db,
        family_id=collection.family_id,
        entry_ids=list(collection.entry_ids or []),
        student_id=collection.student_id,
    )
    payload = PortfolioCollectionRead.model_validate(collection).model_dump()
    payload['entries'] = [_serialize_entry(entry).model_dump() for entry in entries]
    return PortfolioCollectionRead.model_validate(payload)


def _serialize_public_collection(collection: PortfolioCollection, entries: list[PortfolioEntry]) -> PublicPortfolioCollectionRead:
    return PublicPortfolioCollectionRead(
        id=collection.id,
        student_id=collection.student_id,
        name=collection.name,
        description=collection.description,
        is_public=collection.is_public,
        share_token=collection.share_token or '',
        created_at=collection.created_at,
        entries=[_serialize_public_entry(entry) for entry in entries],
    )


def _entry_audit_snapshot(entry: PortfolioEntry) -> dict[str, object]:
    return {
        'id': entry.id,
        'family_id': entry.family_id,
        'student_id': entry.student_id,
        'entry_type': entry.entry_type.value,
        'title': entry.title,
        'description': entry.description,
        'date': entry.date.isoformat(),
        'subject_id': entry.subject_id,
        'assignment_id': entry.assignment_id,
        'submission_id': entry.submission_id,
        'attachments': list(entry.attachments or []),
        'tags': list(entry.tags or []),
        'created_by_user_id': entry.created_by_user_id,
    }


def _collection_audit_snapshot(collection: PortfolioCollection) -> dict[str, object]:
    return {
        'id': collection.id,
        'family_id': collection.family_id,
        'student_id': collection.student_id,
        'name': collection.name,
        'description': collection.description,
        'entry_ids': list(collection.entry_ids or []),
        'is_public': collection.is_public,
        'share_token': collection.share_token,
    }


def _serialize_submission(submission: Submission | None) -> dict[str, object] | None:
    if submission is None:
        return None
    return SubmissionVersionRead.model_validate(
        {
            'id': submission.id,
            'assignment_id': submission.assignment_id,
            'student_id': submission.student_id,
            'file_path': submission.file_path,
            'file_url': submission.file_url,
            'original_filename': submission.original_filename,
            'file_name': submission.file_name,
            'file_type': submission.file_type,
            'file_size_bytes': submission.file_size_bytes,
            'image_width': submission.image_width,
            'image_height': submission.image_height,
            'page_count': submission.page_count,
            'submission_version': submission.submission_version,
            'parent_submission_id': submission.parent_submission_id,
            'is_current': submission.is_current,
            'ocr_text': submission.ocr_text,
            'uploaded_at': submission.uploaded_at,
        }
    ).model_dump()


def _serialize_entry(entry: PortfolioEntry) -> PortfolioEntryRead:
    return PortfolioEntryRead.model_validate(
        {
            'id': entry.id,
            'family_id': entry.family_id,
            'student_id': entry.student_id,
            'entry_type': entry.entry_type,
            'title': entry.title,
            'description': entry.description,
            'date': entry.date,
            'subject_id': entry.subject_id,
            'assignment_id': entry.assignment_id,
            'submission_id': entry.submission_id,
            'attachments': list(entry.attachments or []),
            'attachment_urls': list(entry.attachment_urls),
            'tags': list(entry.tags or []),
            'created_by_user_id': entry.created_by_user_id,
            'created_at': entry.created_at,
            'updated_at': entry.updated_at,
            'student': StudentRead.model_validate(entry.student).model_dump() if entry.student is not None else None,
            'subject': SubjectRead.model_validate(entry.subject).model_dump() if entry.subject is not None else None,
            'assignment': (
                {
                    'id': entry.assignment.id,
                    'title': entry.assignment.title,
                    'due_date': entry.assignment.due_date,
                }
                if entry.assignment is not None
                else None
            ),
            'submission': _serialize_submission(entry.submission),
        }
    )


def _serialize_public_entry(entry: PortfolioEntry) -> PublicPortfolioEntryRead:
    return PublicPortfolioEntryRead.model_validate(
        {
            'id': entry.id,
            'student_id': entry.student_id,
            'entry_type': entry.entry_type,
            'title': entry.title,
            'description': entry.description,
            'date': entry.date,
            'subject_id': entry.subject_id,
            'assignment_id': entry.assignment_id,
            'submission_id': entry.submission_id,
            'attachments': list(entry.attachments or []),
            'attachment_urls': list(entry.attachment_urls),
            'tags': list(entry.tags or []),
            'created_at': entry.created_at,
            'updated_at': entry.updated_at,
            'subject': SubjectRead.model_validate(entry.subject).model_dump() if entry.subject is not None else None,
            'assignment': (
                {
                    'id': entry.assignment.id,
                    'title': entry.assignment.title,
                    'due_date': entry.assignment.due_date,
                }
                if entry.assignment is not None
                else None
            ),
            'submission': _serialize_submission(entry.submission),
        }
    )


async def _store_portfolio_attachment(*, entry: PortfolioEntry, file: UploadFile) -> str:
    safe_name = sanitize_filename(file.filename or '')
    expected_mime, _ = mimetypes.guess_type(safe_name)
    effective_type = ((file.content_type or '').strip().lower() or (expected_mime or 'application/octet-stream').lower())
    if effective_type not in settings.upload_allowed_mime_types:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Unsupported file type')
    if expected_mime and expected_mime.lower() not in settings.upload_allowed_mime_types:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Unsupported file type')
    contents = await file.read()
    if not contents:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Uploaded file is empty')
    if len(contents) > settings.upload_max_bytes:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail='Uploaded file exceeds size limit')
    relative_path = Path('portfolio', str(entry.family_id), str(entry.student_id), str(entry.id), f'{uuid4().hex}_{safe_name}')
    destination = Path(settings.upload_dir) / relative_path
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(contents)
    return str(relative_path)


@router.get('/{student_id}/entries', response_model=list[PortfolioEntryRead])
async def list_portfolio_entries(
    student_id: int,
    entry_type: PortfolioEntryType | None = Query(default=None, alias='type'),
    subject_id: int | None = Query(default=None, ge=1),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    tags: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(get_auth_session),
) -> list[PortfolioEntryRead]:
    await _get_student_or_404(db, family_id=auth.family_id, student_id=student_id)
    _ensure_portfolio_access(auth, student_id=student_id, action='view portfolio entries')
    stmt = (
        select(PortfolioEntry)
        .options(*_entry_options())
        .where(PortfolioEntry.family_id == auth.family_id, PortfolioEntry.student_id == student_id)
        .order_by(PortfolioEntry.date.desc(), PortfolioEntry.updated_at.desc(), PortfolioEntry.id.desc())
    )
    if entry_type is not None:
        stmt = stmt.where(PortfolioEntry.entry_type == entry_type)
    if subject_id is not None:
        stmt = stmt.where(PortfolioEntry.subject_id == subject_id)
    if date_from is not None:
        stmt = stmt.where(PortfolioEntry.date >= date_from)
    if date_to is not None:
        stmt = stmt.where(PortfolioEntry.date <= date_to)
    rows = list((await db.execute(stmt)).scalars().all())
    if tags:
        required_tags = {item.strip().lower() for item in tags.split(',') if item.strip()}
        if required_tags:
            rows = [entry for entry in rows if required_tags.issubset({tag.lower() for tag in entry.tags or []})]
    return [_serialize_entry(entry) for entry in rows]


@router.post('/entries', response_model=PortfolioEntryRead, status_code=status.HTTP_201_CREATED)
async def create_portfolio_entry(
    payload: PortfolioEntryCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(get_auth_session),
) -> PortfolioEntryRead:
    _ensure_portfolio_access(auth, student_id=payload.student_id, action='manage portfolio entries')
    await _validate_entry_references(db, family_id=auth.family_id, payload=payload)
    entry = PortfolioEntry(
        family_id=auth.family_id,
        student_id=payload.student_id,
        entry_type=payload.entry_type,
        title=payload.title,
        description=payload.description,
        date=payload.date,
        subject_id=payload.subject_id,
        assignment_id=payload.assignment_id,
        submission_id=payload.submission_id,
        attachments=[],
        tags=payload.tags,
        created_by_user_id=auth.user_id,
    )
    db.add(entry)
    await db.flush()
    await log_event(
        db,
        action=AuditAction.portfolio_entry_create,
        actor=auth,
        family_id=auth.family_id,
        target_type='portfolio_entry',
        target_id=entry.id,
        before=None,
        after=_entry_audit_snapshot(entry),
        request=request,
    )
    await db.commit()
    return _serialize_entry(await _get_entry_or_404(db, family_id=auth.family_id, entry_id=entry.id))


@router.get('/entries/{entry_id}', response_model=PortfolioEntryRead)
async def get_portfolio_entry(
    entry_id: int,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(get_auth_session),
) -> PortfolioEntryRead:
    entry = await _get_entry_or_404(db, family_id=auth.family_id, entry_id=entry_id)
    _ensure_portfolio_access(auth, student_id=entry.student_id, action='view portfolio entries')
    return _serialize_entry(entry)


@router.put('/entries/{entry_id}', response_model=PortfolioEntryRead)
async def update_portfolio_entry(
    entry_id: int,
    payload: PortfolioEntryUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(get_auth_session),
) -> PortfolioEntryRead:
    entry = await _get_entry_or_404(db, family_id=auth.family_id, entry_id=entry_id)
    _ensure_portfolio_access(auth, student_id=entry.student_id, action='manage portfolio entries')
    _ensure_portfolio_access(auth, student_id=payload.student_id, action='manage portfolio entries')
    await _validate_entry_references(db, family_id=auth.family_id, payload=payload)
    before = _entry_audit_snapshot(entry)
    entry.student_id = payload.student_id
    entry.entry_type = payload.entry_type
    entry.title = payload.title
    entry.description = payload.description
    entry.date = payload.date
    entry.subject_id = payload.subject_id
    entry.assignment_id = payload.assignment_id
    entry.submission_id = payload.submission_id
    entry.tags = payload.tags
    await db.flush()
    after = _entry_audit_snapshot(entry)
    await log_event(
        db,
        action=AuditAction.portfolio_entry_update,
        actor=auth,
        family_id=auth.family_id,
        target_type='portfolio_entry',
        target_id=entry.id,
        before=before,
        after=after,
        request=request,
    )
    await db.commit()
    return _serialize_entry(await _get_entry_or_404(db, family_id=auth.family_id, entry_id=entry.id))


@router.delete('/entries/{entry_id}', status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_portfolio_entry(
    entry_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(get_auth_session),
) -> None:
    entry = await _get_entry_or_404(db, family_id=auth.family_id, entry_id=entry_id)
    _ensure_portfolio_access(auth, student_id=entry.student_id, action='manage portfolio entries')
    before = _entry_audit_snapshot(entry)
    collections = list(
        (
            await db.execute(
                select(PortfolioCollection).where(
                    PortfolioCollection.family_id == auth.family_id,
                    PortfolioCollection.student_id == entry.student_id,
                )
            )
        ).scalars().all()
    )
    for collection in collections:
        if entry.id in (collection.entry_ids or []):
            collection.entry_ids = [item for item in collection.entry_ids if item != entry.id]
    await log_event(
        db,
        action=AuditAction.portfolio_entry_delete,
        actor=auth,
        family_id=auth.family_id,
        target_type='portfolio_entry',
        target_id=entry.id,
        before=before,
        after=None,
        request=request,
    )
    await db.delete(entry)
    await db.commit()


@router.post('/entries/{entry_id}/attach', response_model=PortfolioEntryRead)
async def attach_portfolio_files(
    entry_id: int,
    request: Request,
    files: list[UploadFile] = File(...),
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(get_auth_session),
) -> PortfolioEntryRead:
    entry = await _get_entry_or_404(db, family_id=auth.family_id, entry_id=entry_id)
    _ensure_portfolio_access(auth, student_id=entry.student_id, action='manage portfolio entries')
    if not files:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='At least one file is required')
    before = _entry_audit_snapshot(entry)
    stored_paths = [await _store_portfolio_attachment(entry=entry, file=file) for file in files]
    entry.attachments = [*(entry.attachments or []), *stored_paths]
    await db.flush()
    after = _entry_audit_snapshot(entry)
    await log_event(
        db,
        action=AuditAction.portfolio_entry_update,
        actor=auth,
        family_id=auth.family_id,
        target_type='portfolio_entry',
        target_id=entry.id,
        before=before,
        after=after,
        request=request,
    )
    await db.commit()
    return _serialize_entry(await _get_entry_or_404(db, family_id=auth.family_id, entry_id=entry.id))


@router.get('/collections', response_model=list[PortfolioCollectionRead])
async def list_portfolio_collections(
    student_id: int | None = Query(default=None, ge=1),
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(get_auth_session),
) -> list[PortfolioCollectionRead]:
    if student_id is not None:
        await _get_student_or_404(db, family_id=auth.family_id, student_id=student_id)
        _ensure_portfolio_access(auth, student_id=student_id, action='view portfolio collections')
    stmt = (
        select(PortfolioCollection)
        .where(PortfolioCollection.family_id == auth.family_id)
        .order_by(PortfolioCollection.created_at.desc())
    )
    if student_id is not None:
        stmt = stmt.where(PortfolioCollection.student_id == student_id)
    collections = list((await db.execute(stmt)).scalars().all())
    return [await _serialize_collection(db, collection) for collection in collections]


@router.post('/collections', response_model=PortfolioCollectionRead, status_code=status.HTTP_201_CREATED)
async def create_portfolio_collection(
    payload: PortfolioCollectionCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(get_auth_session),
) -> PortfolioCollectionRead:
    _ensure_portfolio_access(auth, student_id=payload.student_id, action='manage portfolio collections')
    await _validate_collection_entries(
        db,
        family_id=auth.family_id,
        student_id=payload.student_id,
        entry_ids=payload.entry_ids,
    )
    collection = PortfolioCollection(
        family_id=auth.family_id,
        student_id=payload.student_id,
        name=payload.name,
        description=payload.description,
        entry_ids=payload.entry_ids,
        is_public=payload.is_public,
        share_token=str(uuid4()) if payload.is_public else None,
    )
    db.add(collection)
    await db.flush()
    after = _collection_audit_snapshot(collection)
    await log_event(
        db,
        action=AuditAction.portfolio_collection_create,
        actor=auth,
        family_id=auth.family_id,
        target_type='portfolio_collection',
        target_id=collection.id,
        before=None,
        after=after,
        request=request,
    )
    await db.commit()
    collection = await _get_collection_or_404(db, family_id=auth.family_id, collection_id=collection.id)
    return await _serialize_collection(db, collection)


@router.get('/collections/{collection_id}', response_model=PortfolioCollectionRead)
async def get_portfolio_collection(
    collection_id: int,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(get_auth_session),
) -> PortfolioCollectionRead:
    collection = await _get_collection_or_404(db, family_id=auth.family_id, collection_id=collection_id)
    _ensure_portfolio_access(auth, student_id=collection.student_id, action='view portfolio collections')
    return await _serialize_collection(db, collection)


@router.put('/collections/{collection_id}', response_model=PortfolioCollectionRead)
async def update_portfolio_collection(
    collection_id: int,
    payload: PortfolioCollectionUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(get_auth_session),
) -> PortfolioCollectionRead:
    collection = await _get_collection_or_404(db, family_id=auth.family_id, collection_id=collection_id)
    _ensure_portfolio_access(auth, student_id=collection.student_id, action='manage portfolio collections')
    _ensure_portfolio_access(auth, student_id=payload.student_id, action='manage portfolio collections')
    await _validate_collection_entries(
        db,
        family_id=auth.family_id,
        student_id=payload.student_id,
        entry_ids=payload.entry_ids,
    )
    before = _collection_audit_snapshot(collection)
    collection.student_id = payload.student_id
    collection.name = payload.name
    collection.description = payload.description
    collection.entry_ids = payload.entry_ids
    collection.is_public = payload.is_public
    collection.share_token = collection.share_token or str(uuid4()) if payload.is_public else None
    await db.flush()
    after = _collection_audit_snapshot(collection)
    await log_event(
        db,
        action=AuditAction.portfolio_collection_update,
        actor=auth,
        family_id=auth.family_id,
        target_type='portfolio_collection',
        target_id=collection.id,
        before=before,
        after=after,
        request=request,
    )
    await db.commit()
    collection = await _get_collection_or_404(db, family_id=auth.family_id, collection_id=collection.id)
    return await _serialize_collection(db, collection)


@router.delete('/collections/{collection_id}', status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_portfolio_collection(
    collection_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(get_auth_session),
) -> None:
    collection = await _get_collection_or_404(db, family_id=auth.family_id, collection_id=collection_id)
    _ensure_portfolio_access(auth, student_id=collection.student_id, action='manage portfolio collections')
    before = _collection_audit_snapshot(collection)
    await log_event(
        db,
        action=AuditAction.portfolio_collection_delete,
        actor=auth,
        family_id=auth.family_id,
        target_type='portfolio_collection',
        target_id=collection.id,
        before=before,
        after=None,
        request=request,
    )
    await db.delete(collection)
    await db.commit()


@router.get('/collections/{collection_id}/share', response_model=PortfolioShareLinkRead)
async def share_portfolio_collection(
    collection_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(get_auth_session),
) -> PortfolioShareLinkRead:
    collection = await _get_collection_or_404(db, family_id=auth.family_id, collection_id=collection_id)
    _ensure_portfolio_access(auth, student_id=collection.student_id, action='share portfolio collections')
    before = _collection_audit_snapshot(collection)
    if not collection.share_token:
        collection.share_token = str(uuid4())
    collection.is_public = True
    await db.flush()
    after = _collection_audit_snapshot(collection)
    await log_event(
        db,
        action=AuditAction.portfolio_share,
        actor=auth,
        family_id=auth.family_id,
        target_type='portfolio_collection',
        target_id=collection.id,
        before=before,
        after=after,
        request=request,
    )
    await db.commit()
    url = str(request.base_url).rstrip('/') + f'/portfolio/share/{collection.share_token}'
    return PortfolioShareLinkRead(collection_id=collection.id, share_token=collection.share_token, url=url)


@router.get('/public/{share_token}', response_model=PublicPortfolioCollectionRead)
async def public_portfolio_collection(
    share_token: str,
    db: AsyncSession = Depends(get_db),
) -> PublicPortfolioCollectionRead:
    result = await db.execute(
        select(PortfolioCollection).where(PortfolioCollection.share_token == share_token, PortfolioCollection.is_public.is_(True))
    )
    collection = result.scalar_one_or_none()
    if collection is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Shared portfolio collection not found')
    entries = await _load_entries_by_ids(
        db,
        family_id=collection.family_id,
        entry_ids=list(collection.entry_ids or []),
        student_id=collection.student_id,
    )
    return _serialize_public_collection(collection, entries)
