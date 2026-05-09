from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models import ComplianceState
from backend.schemas.compliance import (
    ComplianceDashboardResponse,
    ComplianceDashboardStudent,
    ComplianceRuleCreate,
    ComplianceRuleListResponse,
    ComplianceRuleRead,
    ComplianceRuleSummary,
    ComplianceStudentStatusResponse,
    FamilyComplianceStateRead,
    FamilyComplianceStateUpdate,
)
from backend.schemas.students import StudentRead
from backend.security import AuthSession
from backend.services.authorization import Capability, ensure_student_scope, get_student_scope_id, require_capabilities
from backend.services.compliance import (
    CUSTOM_STATE_CODE,
    create_custom_rule,
    get_dashboard_payload,
    get_family_state_code,
    get_student_status_payload,
    list_rules_for_state,
    resolve_school_year,
    set_family_state_code,
)

router = APIRouter(prefix='/compliance', tags=['compliance'])


def _summary_counts(statuses) -> dict[ComplianceState, int]:
    summary = {state: 0 for state in ComplianceState}
    for item in statuses:
        summary[item.status] += 1
    return summary


@router.get('/rules', response_model=ComplianceRuleListResponse)
async def list_compliance_rules(
    state: str | None = Query(default=None, min_length=2, max_length=8),
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.read_students, action='view compliance rules')),
) -> ComplianceRuleListResponse:
    state_code = (state or await get_family_state_code(db, family_id=auth.family_id)).upper()
    rules = await list_rules_for_state(db, family_id=auth.family_id, state_code=state_code)
    return ComplianceRuleListResponse(
        state_code=state_code,
        summary=ComplianceRuleSummary(total_rules=len(rules), active_rules=sum(1 for rule in rules if rule.is_active)),
        rules=[ComplianceRuleRead.model_validate(rule) for rule in rules],
    )


@router.get('/family/state', response_model=FamilyComplianceStateRead)
async def get_family_state(
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.read_students, action='view family compliance state')),
) -> FamilyComplianceStateRead:
    return FamilyComplianceStateRead(state_code=await get_family_state_code(db, family_id=auth.family_id))


@router.put('/family/state', response_model=FamilyComplianceStateRead)
async def update_family_state(
    payload: FamilyComplianceStateUpdate,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.manage_family, action='update family compliance state')),
) -> FamilyComplianceStateRead:
    state_code = await set_family_state_code(db, family_id=auth.family_id, state_code=payload.state_code)
    return FamilyComplianceStateRead(state_code=state_code)


@router.post('/rules/custom', response_model=ComplianceRuleRead, status_code=status.HTTP_201_CREATED)
async def add_custom_rule(
    payload: ComplianceRuleCreate,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.manage_family, action='create custom compliance rules')),
) -> ComplianceRuleRead:
    state_code = payload.state_code or await get_family_state_code(db, family_id=auth.family_id)
    rule = await create_custom_rule(
        db,
        family_id=auth.family_id,
        state_code=state_code if state_code != CUSTOM_STATE_CODE else CUSTOM_STATE_CODE,
        rule_type=payload.rule_type,
        rule_name=payload.rule_name,
        description=payload.description,
        threshold_value=payload.threshold_value,
        threshold_unit=payload.threshold_unit,
        subjects_list=payload.subjects_list,
        is_active=payload.is_active,
    )
    return ComplianceRuleRead.model_validate(rule)


@router.get('/dashboard', response_model=ComplianceDashboardResponse)
async def compliance_dashboard(
    school_year_id: int | None = Query(default=None, ge=1),
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.read_students, action='view compliance dashboard')),
) -> ComplianceDashboardResponse:
    state_code, school_year, payload = await get_dashboard_payload(db, family_id=auth.family_id, school_year_id=school_year_id)
    checked_at = datetime.utcnow()
    students = payload
    if auth.role == 'student_viewer':
        scoped_student_id = get_student_scope_id(auth)
        students = [(student, statuses) for student, statuses in payload if student.id == scoped_student_id]
    items = [
        ComplianceDashboardStudent(
            student=StudentRead.model_validate(student),
            statuses=statuses,
            summary_counts=_summary_counts(statuses),
        )
        for student, statuses in students
    ]
    latest_checked = max(
        (status.last_checked_at for _, statuses in students for status in statuses),
        default=checked_at,
    )
    return ComplianceDashboardResponse(
        state_code=state_code,
        school_year_id=school_year.id if school_year else None,
        checked_at=latest_checked,
        students=items,
    )


@router.get('/{student_id}/status', response_model=ComplianceStudentStatusResponse)
async def student_compliance_status(
    student_id: int,
    school_year_id: int | None = Query(default=None, ge=1),
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.read_students, action='view student compliance')),
) -> ComplianceStudentStatusResponse:
    ensure_student_scope(auth, student_id, action='view compliance')
    try:
        state_code, school_year, _student, statuses = await get_student_status_payload(
            db,
            family_id=auth.family_id,
            student_id=student_id,
            school_year_id=school_year_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    checked_at = max((item.last_checked_at for item in statuses), default=datetime.utcnow())
    return ComplianceStudentStatusResponse(
        student_id=student_id,
        school_year_id=school_year.id if school_year else None,
        state_code=state_code,
        checked_at=checked_at,
        statuses=statuses,
        summary_counts=_summary_counts(statuses),
    )
