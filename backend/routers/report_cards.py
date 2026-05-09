from __future__ import annotations

from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models import AuditAction, ReportCardStatus, Student
from backend.schemas.report_cards import (
    ReportCardGenerateRequest,
    ReportCardRead,
    ReportCardSummaryRead,
    ReportCardUpdateRequest,
)
from backend.security import AuthSession, get_family_record
from backend.services.audit import log_event
from backend.services.authorization import Capability, ensure_student_scope, get_student_scope_id, require_capabilities
from backend.services.report_cards import (
    build_report_card_pdf,
    finalize_report_card,
    generate_report_card,
    get_report_card,
    list_report_cards,
    report_card_to_read,
    report_card_to_summary,
    update_report_card,
)

router = APIRouter(prefix='/report-cards', tags=['report-cards'])


def _snapshot(report_card: ReportCardRead | dict[str, object]) -> dict[str, object]:
    if isinstance(report_card, dict):
        return report_card
    return report_card.model_dump(mode='json')


async def _get_student_or_404(db: AsyncSession, *, family_id: int, student_id: int) -> Student:
    student = await get_family_record(db, Student, student_id, family_id)
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Student not found')
    return student


def _ensure_report_access(auth: AuthSession, student_id: int) -> None:
    ensure_student_scope(auth, student_id, action='view report cards')


@router.post('/generate', response_model=ReportCardRead, status_code=status.HTTP_201_CREATED)
async def generate_report(
    payload: ReportCardGenerateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.manage_grading, action='generate report cards')),
) -> ReportCardRead:
    await _get_student_or_404(db, family_id=auth.family_id, student_id=payload.student_id)
    try:
        report_card = await generate_report_card(
            db,
            family_id=auth.family_id,
            student_id=payload.student_id,
            grading_period_id=payload.grading_period_id,
            generated_by_user_id=auth.user_id,
            notes=payload.notes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    serialized = ReportCardRead.model_validate(report_card_to_read(report_card))
    await log_event(
        db,
        action=AuditAction.report_generate,
        actor=auth,
        family_id=auth.family_id,
        target_type='report_card',
        target_id=report_card.id,
        before=None,
        after=serialized.model_dump(mode='json'),
        request=request,
    )
    await db.commit()
    refreshed = await get_report_card(db, family_id=auth.family_id, report_card_id=report_card.id)
    assert refreshed is not None
    return ReportCardRead.model_validate(report_card_to_read(refreshed))


@router.get('', response_model=list[ReportCardSummaryRead])
async def get_report_cards(
    student_id: int | None = Query(default=None, gt=0),
    grading_period_id: int | None = Query(default=None, gt=0),
    status_filter: ReportCardStatus | None = Query(default=None, alias='status'),
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.read_grades, action='view report cards')),
) -> list[ReportCardSummaryRead]:
    scoped_student_id = student_id
    if auth.role == 'student_viewer':
        scoped_student_id = get_student_scope_id(auth)
        if student_id is not None and student_id != scoped_student_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{auth.role}' is not allowed to view another student's report cards.",
            )
    cards = await list_report_cards(
        db,
        family_id=auth.family_id,
        student_id=scoped_student_id,
        grading_period_id=grading_period_id,
        status=status_filter,
    )
    return [ReportCardSummaryRead.model_validate(report_card_to_summary(card)) for card in cards]


@router.get('/{report_card_id}', response_model=ReportCardRead)
async def get_report_card_detail(
    report_card_id: int,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.read_grades, action='view report card detail')),
) -> ReportCardRead:
    report_card = await get_report_card(db, family_id=auth.family_id, report_card_id=report_card_id)
    if report_card is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Report card not found')
    _ensure_report_access(auth, report_card.student_id)
    return ReportCardRead.model_validate(report_card_to_read(report_card))


@router.patch('/{report_card_id}', response_model=ReportCardRead)
async def patch_report_card(
    report_card_id: int,
    payload: ReportCardUpdateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.manage_grading, action='update report cards')),
) -> ReportCardRead:
    report_card = await get_report_card(db, family_id=auth.family_id, report_card_id=report_card_id)
    if report_card is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Report card not found')
    before = ReportCardRead.model_validate(report_card_to_read(report_card)).model_dump(mode='json')
    entry_comments = {entry.entry_id: entry.teacher_comments for entry in payload.entries} if payload.entries else None
    try:
        updated = await update_report_card(
            db,
            report_card=report_card,
            notes=payload.notes if 'notes' in payload.model_fields_set else ...,
            status=payload.status,
            entry_comments=entry_comments,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    serialized = ReportCardRead.model_validate(report_card_to_read(updated))
    await log_event(
        db,
        action=AuditAction.report_generate,
        actor=auth,
        family_id=auth.family_id,
        target_type='report_card',
        target_id=updated.id,
        before=before,
        after=serialized.model_dump(mode='json'),
        request=request,
    )
    await db.commit()
    return serialized


@router.post('/{report_card_id}/finalize', response_model=ReportCardRead)
async def finalize_report(
    report_card_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.manage_grading, action='finalize report cards')),
) -> ReportCardRead:
    report_card = await get_report_card(db, family_id=auth.family_id, report_card_id=report_card_id)
    if report_card is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Report card not found')
    before = ReportCardRead.model_validate(report_card_to_read(report_card)).model_dump(mode='json')
    try:
        finalized = await finalize_report_card(db, report_card=report_card)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    serialized = ReportCardRead.model_validate(report_card_to_read(finalized))
    await log_event(
        db,
        action=AuditAction.report_generate,
        actor=auth,
        family_id=auth.family_id,
        target_type='report_card',
        target_id=finalized.id,
        before=before,
        after=serialized.model_dump(mode='json'),
        request=request,
    )
    await db.commit()
    return serialized


@router.get('/{report_card_id}/pdf')
async def download_report_card_pdf(
    report_card_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.read_grades, action='download report cards')),
) -> StreamingResponse:
    report_card = await get_report_card(db, family_id=auth.family_id, report_card_id=report_card_id)
    if report_card is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Report card not found')
    _ensure_report_access(auth, report_card.student_id)
    pdf_bytes = build_report_card_pdf(report_card)
    await log_event(
        db,
        action=AuditAction.export,
        actor=auth,
        family_id=auth.family_id,
        target_type='report_card_pdf',
        target_id=report_card.id,
        before=None,
        after={'report_card_id': report_card.id, 'status': report_card.status.value},
        request=request,
    )
    await db.commit()
    filename = f'report-card-{report_card.student_id}-{report_card.grading_period_id}.pdf'
    return StreamingResponse(
        BytesIO(pdf_bytes),
        media_type='application/pdf',
        headers={'Content-Disposition': f'attachment; filename="{filename}"'},
    )
