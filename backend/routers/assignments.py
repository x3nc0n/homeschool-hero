from __future__ import annotations

from datetime import date, datetime, time, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.database import get_db
from backend.models import (
    Assignment,
    AssignmentCategory,
    AssignmentRecurrence,
    AssignmentStatus,
    AssignmentTarget,
    AssignmentTargetStatus,
    GradingPeriod,
    Student,
    Subject,
)
from backend.schemas.assignments import (
    AssignmentCreate,
    AssignmentListResponse,
    AssignmentRead,
    AssignmentStatusUpdate,
    AssignmentUpdate,
)
from backend.security import AuthSession, get_family_record
from backend.services.authorization import Capability, get_student_scope_id, require_capabilities

router = APIRouter(prefix='/assignments', tags=['assignments'])

_allowed_transitions: dict[AssignmentStatus, set[AssignmentStatus]] = {
    AssignmentStatus.pending: {AssignmentStatus.complete, AssignmentStatus.pending, AssignmentStatus.graded},
    AssignmentStatus.complete: {AssignmentStatus.graded, AssignmentStatus.pending, AssignmentStatus.complete},
    AssignmentStatus.graded: {AssignmentStatus.complete, AssignmentStatus.graded},
}
_assignment_status_values = {item.value: item for item in AssignmentStatus}
_assignment_target_status_values = {item.value: item for item in AssignmentTargetStatus}


def _validate_transition(current: AssignmentStatus, nxt: AssignmentStatus) -> None:
    if nxt not in _allowed_transitions[current]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f'Invalid status transition from {current.value} to {nxt.value}',
        )


def _assignment_options():
    return (
        selectinload(Assignment.subject),
        selectinload(Assignment.grading_period),
        selectinload(Assignment.targets).selectinload(AssignmentTarget.student),
    )


def _serialize_history_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if hasattr(value, 'value'):
        return value.value
    return value


def _append_history(
    assignment: Assignment,
    *,
    field: str,
    before: Any,
    after: Any,
    change_type: str = 'assignment_update',
    student_id: int | None = None,
) -> None:
    assignment.status_history.append(
        {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'change_type': change_type,
            'field': field,
            'before': _serialize_history_value(before),
            'after': _serialize_history_value(after),
            'student_id': student_id,
        }
    )


def _assignment_query(auth: AuthSession):
    stmt = (
        select(Assignment)
        .options(*_assignment_options())
        .where(Assignment.family_id == auth.family_id)
    )
    if auth.role == 'student_viewer':
        scoped_student_id = get_student_scope_id(auth)
        stmt = stmt.where(
            or_(
                ~Assignment.targets.any(),
                Assignment.targets.any(AssignmentTarget.student_id == scoped_student_id),
            )
        )
    return stmt


def _normalize_date_floor(value: date | None) -> datetime | None:
    if value is None:
        return None
    return datetime.combine(value, time.min, tzinfo=timezone.utc)


def _normalize_date_ceil(value: date | None) -> datetime | None:
    if value is None:
        return None
    return datetime.combine(value, time.max, tzinfo=timezone.utc)


async def _get_assignment_or_404(db: AsyncSession, auth: AuthSession, assignment_id: int) -> Assignment:
    assignment = (
        await db.execute(_assignment_query(auth).where(Assignment.id == assignment_id))
    ).scalar_one_or_none()
    if not assignment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Assignment not found')
    return assignment


async def _validate_grading_period(
    db: AsyncSession,
    grading_period_id: int | None,
    family_id: int,
) -> None:
    if grading_period_id is None:
        return
    grading_period = await get_family_record(db, GradingPeriod, grading_period_id, family_id)
    if not grading_period:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Grading period not found')


async def _validate_targets(
    db: AsyncSession,
    *,
    family_id: int,
    targets: list[Any] | None,
) -> dict[int, Student]:
    if not targets:
        return {}
    students: dict[int, Student] = {}
    seen_student_ids: set[int] = set()
    for target in targets:
        if target.student_id in seen_student_ids:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Each student can only appear once per assignment')
        seen_student_ids.add(target.student_id)
        student = await get_family_record(db, Student, target.student_id, family_id)
        if not student:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Student not found')
        students[target.student_id] = student
    return students


def _apply_assignment_updates(assignment: Assignment, payload: AssignmentCreate | AssignmentUpdate) -> None:
    scalar_fields = (
        'title',
        'subject_id',
        'description',
        'due_date',
        'status',
        'category',
        'grading_period_id',
        'weight',
        'max_score',
        'recurrence',
        'recurrence_end_date',
        'rubric_description',
        'attachments',
        'lesson_plan_id',
    )
    for field in scalar_fields:
        setattr(assignment, field, getattr(payload, field))


def _track_assignment_changes(assignment: Assignment, payload: AssignmentUpdate) -> None:
    tracked_fields = (
        'title',
        'description',
        'due_date',
        'status',
        'category',
        'grading_period_id',
        'weight',
        'max_score',
        'recurrence',
        'recurrence_end_date',
        'rubric_description',
        'attachments',
        'lesson_plan_id',
    )
    for field in tracked_fields:
        before = getattr(assignment, field)
        after = getattr(payload, field)
        if _serialize_history_value(before) != _serialize_history_value(after):
            _append_history(assignment, field=field, before=before, after=after)


def _track_target_changes(assignment: Assignment, payload: AssignmentUpdate) -> None:
    if payload.targets is None:
        return
    existing_by_student = {target.student_id: target for target in assignment.targets}
    incoming_by_student = {target.student_id: target for target in payload.targets}

    for student_id, target in existing_by_student.items():
        replacement = incoming_by_student.get(student_id)
        if replacement is None:
            _append_history(
                assignment,
                field='target_assignment',
                before={'status': target.status.value, 'due_date': _serialize_history_value(target.due_date)},
                after=None,
                change_type='target_removed',
                student_id=student_id,
            )
            continue
        if _serialize_history_value(target.due_date) != _serialize_history_value(replacement.due_date):
            _append_history(
                assignment,
                field='target_due_date',
                before=target.due_date,
                after=replacement.due_date,
                change_type='target_update',
                student_id=student_id,
            )
        if target.status != replacement.status:
            _append_history(
                assignment,
                field='target_status',
                before=target.status,
                after=replacement.status,
                change_type='target_update',
                student_id=student_id,
            )

    for student_id, target in incoming_by_student.items():
        if student_id not in existing_by_student:
            _append_history(
                assignment,
                field='target_assignment',
                before=None,
                after={'status': target.status.value, 'due_date': _serialize_history_value(target.due_date)},
                change_type='target_added',
                student_id=student_id,
            )


def _replace_targets(assignment: Assignment, payload: AssignmentCreate | AssignmentUpdate) -> None:
    if payload.targets is None:
        return
    existing_by_student = {target.student_id: target for target in assignment.targets}
    incoming_student_ids = {target.student_id for target in payload.targets}

    for target in list(assignment.targets):
        if target.student_id not in incoming_student_ids:
            assignment.targets.remove(target)

    for target_payload in payload.targets:
        existing = existing_by_student.get(target_payload.student_id)
        if existing:
            existing.due_date = target_payload.due_date
            existing.status = target_payload.status
            continue
        assignment.targets.append(
            AssignmentTarget(
                student_id=target_payload.student_id,
                due_date=target_payload.due_date,
                status=target_payload.status,
            )
        )


def _apply_status_filter(stmt, status_value: str):
    if status_value in _assignment_status_values:
        return stmt.where(Assignment.status == _assignment_status_values[status_value])
    if status_value in _assignment_target_status_values:
        target_status = _assignment_target_status_values[status_value]
        legacy_match = None
        if target_status == AssignmentTargetStatus.assigned:
            legacy_match = AssignmentStatus.pending
        elif target_status == AssignmentTargetStatus.submitted:
            legacy_match = AssignmentStatus.complete
        elif target_status == AssignmentTargetStatus.graded:
            legacy_match = AssignmentStatus.graded
        clauses = [Assignment.targets.any(AssignmentTarget.status == target_status)]
        if legacy_match is not None:
            clauses.append(~Assignment.targets.any() & (Assignment.status == legacy_match))
        return stmt.where(or_(*clauses))
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Unsupported assignment status filter')


@router.get('', response_model=AssignmentListResponse)
async def list_assignments(
    q: str | None = Query(default=None, min_length=1, max_length=200),
    category: AssignmentCategory | None = Query(default=None),
    grading_period_id: int | None = Query(default=None, gt=0),
    subject_id: int | None = Query(default=None, gt=0),
    student_id: int | None = Query(default=None, gt=0),
    status_filter: str | None = Query(default=None, alias='status'),
    due_from: date | None = Query(default=None),
    due_to: date | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.read_curriculum, action='view assignments')),
) -> AssignmentListResponse:
    scoped_student_id = student_id
    if auth.role == 'student_viewer':
        scoped_student_id = get_student_scope_id(auth)
        if student_id is not None and student_id != scoped_student_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Role 'student_viewer' is not allowed to view assignments for another student.",
            )

    stmt = _assignment_query(auth)
    if q:
        lowered = f'%{q.strip().lower()}%'
        stmt = stmt.join(Subject, Subject.id == Assignment.subject_id).where(
            or_(
                func.lower(Assignment.title).like(lowered),
                func.lower(func.coalesce(Assignment.description, '')).like(lowered),
                func.lower(func.coalesce(Assignment.rubric_description, '')).like(lowered),
                func.lower(Subject.name).like(lowered),
            )
        )
    if category is not None:
        stmt = stmt.where(Assignment.category == category)
    if grading_period_id is not None:
        stmt = stmt.where(Assignment.grading_period_id == grading_period_id)
    if subject_id is not None:
        stmt = stmt.where(Assignment.subject_id == subject_id)
    if scoped_student_id is not None:
        stmt = stmt.where(
            or_(
                ~Assignment.targets.any(),
                Assignment.targets.any(AssignmentTarget.student_id == scoped_student_id),
            )
        )
    if status_filter:
        stmt = _apply_status_filter(stmt, status_filter.strip().lower())

    due_from_dt = _normalize_date_floor(due_from)
    due_to_dt = _normalize_date_ceil(due_to)
    if due_from_dt is not None:
        stmt = stmt.where(
            or_(
                Assignment.due_date >= due_from_dt,
                Assignment.targets.any(AssignmentTarget.due_date >= due_from_dt),
            )
        )
    if due_to_dt is not None:
        stmt = stmt.where(
            or_(
                Assignment.due_date <= due_to_dt,
                Assignment.targets.any(AssignmentTarget.due_date <= due_to_dt),
            )
        )

    total = (await db.execute(select(func.count()).select_from(stmt.order_by(None).subquery()))).scalar_one()
    total_pages = (total + page_size - 1) // page_size if total else 0
    items = (
        await db.execute(
            stmt.order_by(Assignment.created_at.desc(), Assignment.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).scalars().all()
    return AssignmentListResponse(
        items=list(items),
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.post('', response_model=AssignmentRead, status_code=status.HTTP_201_CREATED)
async def create_assignment(
    payload: AssignmentCreate,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.manage_curriculum, action='manage assignments')),
) -> Assignment:
    subject = await get_family_record(db, Subject, payload.subject_id, auth.family_id)
    if not subject:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Subject not found')
    await _validate_grading_period(db, payload.grading_period_id, auth.family_id)
    await _validate_targets(db, family_id=auth.family_id, targets=payload.targets)

    assignment = Assignment(family_id=auth.family_id)
    db.add(assignment)
    _apply_assignment_updates(assignment, payload)
    _replace_targets(assignment, payload)
    await db.commit()
    return await _get_assignment_or_404(db, auth, assignment.id)


@router.get('/{assignment_id}', response_model=AssignmentRead)
async def get_assignment(
    assignment_id: int,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.read_curriculum, action='view assignments')),
) -> Assignment:
    return await _get_assignment_or_404(db, auth, assignment_id)


@router.put('/{assignment_id}', response_model=AssignmentRead)
async def update_assignment(
    assignment_id: int,
    payload: AssignmentUpdate,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.manage_curriculum, action='manage assignments')),
) -> Assignment:
    assignment = await _get_assignment_or_404(db, auth, assignment_id)
    subject = await get_family_record(db, Subject, payload.subject_id, auth.family_id)
    if not subject:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Subject not found')
    await _validate_grading_period(db, payload.grading_period_id, auth.family_id)
    await _validate_targets(db, family_id=auth.family_id, targets=payload.targets)
    _validate_transition(assignment.status, payload.status)
    _track_assignment_changes(assignment, payload)
    _track_target_changes(assignment, payload)
    _apply_assignment_updates(assignment, payload)
    _replace_targets(assignment, payload)
    await db.commit()
    return await _get_assignment_or_404(db, auth, assignment_id)


@router.patch('/{assignment_id}/status', response_model=AssignmentRead)
async def update_assignment_status(
    assignment_id: int,
    payload: AssignmentStatusUpdate,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.manage_curriculum, action='manage assignments')),
) -> Assignment:
    assignment = await _get_assignment_or_404(db, auth, assignment_id)
    _validate_transition(assignment.status, payload.status)
    if assignment.status != payload.status:
        _append_history(assignment, field='status', before=assignment.status, after=payload.status, change_type='status_update')
    assignment.status = payload.status
    await db.commit()
    return await _get_assignment_or_404(db, auth, assignment_id)


@router.delete('/{assignment_id}', status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_assignment(
    assignment_id: int,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.manage_curriculum, action='manage assignments')),
) -> None:
    assignment = await _get_assignment_or_404(db, auth, assignment_id)
    await db.delete(assignment)
    await db.commit()
