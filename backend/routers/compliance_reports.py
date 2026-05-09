from __future__ import annotations

from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models import AuditAction, ComplianceReportStatus, ComplianceReportType, Student
from backend.schemas.compliance_reports import (
    ComplianceReportGenerateRequest,
    ComplianceReportRead,
    ComplianceReportSummaryRead,
    RequiredComplianceReportListResponse,
    RequiredComplianceReportRead,
)
from backend.security import AuthSession, get_family_record
from backend.services.audit import log_event
from backend.services.authorization import Capability, ensure_student_scope, get_student_scope_id, require_capabilities
from backend.services.compliance import get_family_state_code
from backend.services.compliance_reports import (
    build_compliance_report_pdf,
    finalize_compliance_report,
    generate_compliance_report,
    get_compliance_report,
    list_compliance_reports,
    list_required_reports,
    report_to_read,
    report_to_summary,
)

router = APIRouter(prefix='/compliance-reports', tags=['compliance-reports'])


async def _get_student_or_404(db: AsyncSession, *, family_id: int, student_id: int) -> Student:
    student = await get_family_record(db, Student, student_id, family_id)
    if student is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Student not found')
    return student


def _ensure_report_access(auth: AuthSession, student_id: int) -> None:
    ensure_student_scope(auth, student_id, action='view compliance reports')


@router.post('/generate', response_model=ComplianceReportRead, status_code=status.HTTP_201_CREATED)
async def generate_report(
    payload: ComplianceReportGenerateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.manage_grading, action='generate compliance reports')),
) -> ComplianceReportRead:
    await _get_student_or_404(db, family_id=auth.family_id, student_id=payload.student_id)
    try:
        report = await generate_compliance_report(
            db,
            family_id=auth.family_id,
            student_id=payload.student_id,
            school_year_id=payload.school_year_id,
            report_type=payload.report_type,
            grading_period_id=payload.grading_period_id,
            generated_by_user_id=auth.user_id,
            notes=payload.notes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    serialized = ComplianceReportRead.model_validate(report_to_read(report))
    await log_event(
        db,
        action=AuditAction.report_generate,
        actor=auth,
        family_id=auth.family_id,
        target_type='compliance_report',
        target_id=report.id,
        before=None,
        after=serialized.model_dump(mode='json'),
        request=request,
    )
    await db.commit()
    refreshed = await get_compliance_report(db, family_id=auth.family_id, report_id=report.id)
    assert refreshed is not None
    return ComplianceReportRead.model_validate(report_to_read(refreshed))


@router.get('/required', response_model=RequiredComplianceReportListResponse)
async def required_reports(
    state: str | None = Query(default=None, min_length=2, max_length=8),
    student_id: int | None = Query(default=None, gt=0),
    school_year_id: int | None = Query(default=None, gt=0),
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.read_students, action='view required compliance reports')),
) -> RequiredComplianceReportListResponse:
    scoped_student_id = student_id
    if auth.role == 'student_viewer':
        scoped_student_id = get_student_scope_id(auth)
        if student_id is not None and student_id != scoped_student_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{auth.role}' is not allowed to view another student's compliance reports.",
            )
    state_code = (state or await get_family_state_code(db, family_id=auth.family_id)).upper()
    items = await list_required_reports(
        db,
        family_id=auth.family_id,
        state_code=state_code,
        student_id=scoped_student_id,
        school_year_id=school_year_id,
    )
    return RequiredComplianceReportListResponse(
        state_code=state_code,
        student_id=scoped_student_id,
        school_year_id=school_year_id,
        items=[RequiredComplianceReportRead.model_validate(item) for item in items],
    )


@router.get('', response_model=list[ComplianceReportSummaryRead])
async def get_reports(
    student_id: int | None = Query(default=None, gt=0),
    school_year_id: int | None = Query(default=None, gt=0),
    report_type: ComplianceReportType | None = Query(default=None),
    status_filter: ComplianceReportStatus | None = Query(default=None, alias='status'),
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.read_grades, action='view compliance reports')),
) -> list[ComplianceReportSummaryRead]:
    scoped_student_id = student_id
    if auth.role == 'student_viewer':
        scoped_student_id = get_student_scope_id(auth)
        if student_id is not None and student_id != scoped_student_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{auth.role}' is not allowed to view another student's compliance reports.",
            )
    reports = await list_compliance_reports(
        db,
        family_id=auth.family_id,
        student_id=scoped_student_id,
        school_year_id=school_year_id,
        report_type=report_type,
        status=status_filter,
    )
    return [ComplianceReportSummaryRead.model_validate(report_to_summary(report)) for report in reports]


@router.get('/{report_id}', response_model=ComplianceReportRead)
async def get_report_detail(
    report_id: int,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.read_grades, action='view compliance report detail')),
) -> ComplianceReportRead:
    report = await get_compliance_report(db, family_id=auth.family_id, report_id=report_id)
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Compliance report not found')
    _ensure_report_access(auth, report.student_id)
    return ComplianceReportRead.model_validate(report_to_read(report))


@router.post('/{report_id}/finalize', response_model=ComplianceReportRead)
async def finalize_report(
    report_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.manage_grading, action='finalize compliance reports')),
) -> ComplianceReportRead:
    report = await get_compliance_report(db, family_id=auth.family_id, report_id=report_id)
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Compliance report not found')
    before = ComplianceReportRead.model_validate(report_to_read(report)).model_dump(mode='json')
    try:
        finalized = await finalize_compliance_report(db, report=report)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    serialized = ComplianceReportRead.model_validate(report_to_read(finalized))
    await log_event(
        db,
        action=AuditAction.report_generate,
        actor=auth,
        family_id=auth.family_id,
        target_type='compliance_report',
        target_id=report_id,
        before=before,
        after=serialized.model_dump(mode='json'),
        request=request,
    )
    await db.commit()
    return serialized


@router.get('/{report_id}/pdf')
async def get_report_pdf(
    report_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.read_grades, action='download compliance reports')),
) -> StreamingResponse:
    report = await get_compliance_report(db, family_id=auth.family_id, report_id=report_id)
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Compliance report not found')
    _ensure_report_access(auth, report.student_id)
    pdf_bytes = build_compliance_report_pdf(report)
    await log_event(
        db,
        action=AuditAction.export,
        actor=auth,
        family_id=auth.family_id,
        target_type='compliance_report_pdf',
        target_id=report.id,
        before=None,
        after={'compliance_report_id': report.id, 'report_type': report.report_type.value, 'status': report.status.value},
        request=request,
    )
    await db.commit()
    filename = f'compliance-report-{report.student_id}-{report.report_type.value}.pdf'
    return StreamingResponse(
        BytesIO(pdf_bytes),
        media_type='application/pdf',
        headers={'Content-Disposition': f'attachment; filename="{filename}"'},
    )
