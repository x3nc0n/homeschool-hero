from __future__ import annotations

from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models import AuditAction, Student, TranscriptStatus
from backend.schemas.transcripts import (
    TranscriptGenerateRequest,
    TranscriptRead,
    TranscriptSummaryRead,
    TranscriptUpdateRequest,
)
from backend.security import AuthSession, get_family_record
from backend.services.audit import log_event
from backend.services.authorization import Capability, ensure_student_scope, get_student_scope_id, require_capabilities
from backend.services.transcripts import (
    build_transcript_pdf,
    finalize_transcript,
    generate_transcript,
    get_transcript,
    get_transcript_rank,
    list_transcripts,
    transcript_to_read,
    transcript_to_summary,
    update_transcript,
)

router = APIRouter(prefix='/transcripts', tags=['transcripts'])


async def _serialize_transcript(transcript, db: AsyncSession) -> TranscriptRead:
    class_rank, class_size = await get_transcript_rank(db, family_id=transcript.family_id, student_id=transcript.student_id)
    return TranscriptRead.model_validate(transcript_to_read(transcript, class_rank=class_rank, class_size=class_size))


async def _get_student_or_404(db: AsyncSession, *, family_id: int, student_id: int) -> Student:
    student = await get_family_record(db, Student, student_id, family_id)
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Student not found')
    return student


def _ensure_transcript_access(auth: AuthSession, student_id: int) -> None:
    ensure_student_scope(auth, student_id, action='view transcripts')


@router.post('/generate', response_model=TranscriptRead, status_code=status.HTTP_201_CREATED)
async def generate_student_transcript(
    payload: TranscriptGenerateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.manage_grading, action='generate transcripts')),
) -> TranscriptRead:
    await _get_student_or_404(db, family_id=auth.family_id, student_id=payload.student_id)
    try:
        transcript = await generate_transcript(
            db,
            family_id=auth.family_id,
            student_id=payload.student_id,
            generated_by_user_id=auth.user_id,
            notes=payload.notes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    serialized = await _serialize_transcript(transcript, db)
    await log_event(
        db,
        action=AuditAction.report_generate,
        actor=auth,
        family_id=auth.family_id,
        target_type='transcript',
        target_id=transcript.id,
        before=None,
        after=serialized.model_dump(mode='json'),
        request=request,
    )
    await db.commit()
    refreshed = await get_transcript(db, family_id=auth.family_id, transcript_id=transcript.id)
    assert refreshed is not None
    return await _serialize_transcript(refreshed, db)


@router.get('', response_model=list[TranscriptSummaryRead])
async def get_transcript_list(
    student_id: int | None = Query(default=None, gt=0),
    status_filter: TranscriptStatus | None = Query(default=None, alias='status'),
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.read_grades, action='view transcripts')),
) -> list[TranscriptSummaryRead]:
    scoped_student_id = student_id
    if auth.role == 'student_viewer':
        scoped_student_id = get_student_scope_id(auth)
        if student_id is not None and student_id != scoped_student_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{auth.role}' is not allowed to view another student's transcripts.",
            )
    transcripts = await list_transcripts(db, family_id=auth.family_id, student_id=scoped_student_id, status=status_filter)
    return [TranscriptSummaryRead.model_validate(transcript_to_summary(transcript)) for transcript in transcripts]


@router.get('/{transcript_id}', response_model=TranscriptRead)
async def get_transcript_detail(
    transcript_id: int,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.read_grades, action='view transcript detail')),
) -> TranscriptRead:
    transcript = await get_transcript(db, family_id=auth.family_id, transcript_id=transcript_id)
    if transcript is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Transcript not found')
    _ensure_transcript_access(auth, transcript.student_id)
    return await _serialize_transcript(transcript, db)


@router.patch('/{transcript_id}', response_model=TranscriptRead)
async def patch_transcript(
    transcript_id: int,
    payload: TranscriptUpdateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.manage_grading, action='update transcripts')),
) -> TranscriptRead:
    transcript = await get_transcript(db, family_id=auth.family_id, transcript_id=transcript_id)
    if transcript is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Transcript not found')
    before = (await _serialize_transcript(transcript, db)).model_dump(mode='json')
    updates = (
        {
            entry.entry_id: {
                key: value
                for key, value in {
                    'credits': entry.credits,
                    'is_honors': entry.is_honors,
                    'is_ap': entry.is_ap,
                    'notes': entry.notes,
                    'subject_name': entry.subject_name,
                }.items()
                if value is not None
            }
            for entry in payload.entries
        }
        if payload.entries
        else None
    )
    try:
        updated = await update_transcript(
            db,
            transcript=transcript,
            notes=payload.notes if 'notes' in payload.model_fields_set else ...,
            status=payload.status,
            entry_updates=updates,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    serialized = await _serialize_transcript(updated, db)
    await log_event(
        db,
        action=AuditAction.report_generate,
        actor=auth,
        family_id=auth.family_id,
        target_type='transcript',
        target_id=updated.id,
        before=before,
        after=serialized.model_dump(mode='json'),
        request=request,
    )
    await db.commit()
    return serialized


@router.post('/{transcript_id}/finalize', response_model=TranscriptRead)
async def finalize_student_transcript(
    transcript_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.manage_grading, action='finalize transcripts')),
) -> TranscriptRead:
    transcript = await get_transcript(db, family_id=auth.family_id, transcript_id=transcript_id)
    if transcript is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Transcript not found')
    before = (await _serialize_transcript(transcript, db)).model_dump(mode='json')
    try:
        finalized = await finalize_transcript(db, transcript=transcript)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    serialized = await _serialize_transcript(finalized, db)
    await log_event(
        db,
        action=AuditAction.report_generate,
        actor=auth,
        family_id=auth.family_id,
        target_type='transcript',
        target_id=finalized.id,
        before=before,
        after=serialized.model_dump(mode='json'),
        request=request,
    )
    await db.commit()
    return serialized


@router.get('/{transcript_id}/pdf')
async def download_transcript_pdf(
    transcript_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.read_grades, action='download transcripts')),
) -> StreamingResponse:
    transcript = await get_transcript(db, family_id=auth.family_id, transcript_id=transcript_id)
    if transcript is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Transcript not found')
    _ensure_transcript_access(auth, transcript.student_id)
    class_rank, class_size = await get_transcript_rank(db, family_id=auth.family_id, student_id=transcript.student_id)
    pdf_bytes = build_transcript_pdf(transcript, class_rank=class_rank, class_size=class_size)
    await log_event(
        db,
        action=AuditAction.export,
        actor=auth,
        family_id=auth.family_id,
        target_type='transcript_pdf',
        target_id=transcript.id,
        before=None,
        after={'transcript_id': transcript.id, 'status': transcript.status.value},
        request=request,
    )
    await db.commit()
    filename = f'transcript-{transcript.student_id}-{transcript.id}.pdf'
    return StreamingResponse(
        BytesIO(pdf_bytes),
        media_type='application/pdf',
        headers={'Content-Disposition': f'attachment; filename="{filename}"'},
    )
