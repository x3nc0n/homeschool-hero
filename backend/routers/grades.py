from datetime import date, datetime, time, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import Float, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.database import get_db
from backend.models import (
    Assignment,
    AssignmentTarget,
    AssignmentTargetStatus,
    AuditAction,
    Grade,
    GradingPeriod,
    Student,
    Subject,
    Submission,
    Term,
)
from backend.schemas.grades import (
    GradeAverageByStudent,
    GradeAverageBySubject,
    GradeCreate,
    GradeHistoryResponse,
    GradeHistoryItem,
    GradeListItem,
    GradeListResponse,
    GradeRead,
    GradeUpdate,
)
from backend.security import AuthSession, get_family_record
from backend.services.audit import log_event
from backend.services.authorization import (
    AppRole,
    Capability,
    ensure_student_scope,
    get_student_scope_id,
    require_any_role,
    require_capabilities,
    require_teacher,
)
from backend.services.cache import invalidate_gradebook_cache
from backend.services.gradebook import ensure_default_grade_scale, map_percent_to_grade
from backend.services.notifications import create_grading_complete_notifications

router = APIRouter(prefix='/grades', tags=['grades'])


def _normalize_date_floor(value: date | None) -> datetime | None:
    if value is None:
        return None
    return datetime.combine(value, time.min, tzinfo=timezone.utc)


def _normalize_date_ceil(value: date | None) -> datetime | None:
    if value is None:
        return None
    return datetime.combine(value, time.max, tzinfo=timezone.utc)


def _grade_snapshot(grade: Grade) -> dict[str, object | None]:
    return {
        'id': grade.id,
        'submission_id': grade.submission_id,
        'student_id': grade.student_id,
        'score': grade.score,
        'max_score': grade.max_score,
        'letter_grade': grade.letter_grade,
        'notes': grade.notes,
        'graded_by': grade.graded_by.value,
        'ai_confidence': grade.ai_confidence,
    }


@router.get('', response_model=GradeListResponse)
async def list_grades(
    student_id: int | None = Query(default=None),
    subject_id: int | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_any_role(AppRole.teacher, AppRole.student, action='view grades')),
) -> GradeListResponse:
    scoped_student_id = student_id
    if auth.role == 'student_viewer':
        scoped_student_id = get_student_scope_id(auth)
        if student_id is not None and student_id != scoped_student_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Role 'student_viewer' is not allowed to view grades for another student.")

    stmt = (
        select(Grade)
        .join(Submission, Submission.id == Grade.submission_id)
        .join(Assignment, Assignment.id == Submission.assignment_id)
        .where(Grade.family_id == auth.family_id)
    )
    if scoped_student_id:
        stmt = stmt.where(Grade.student_id == scoped_student_id)
    if subject_id:
        stmt = stmt.where(Assignment.subject_id == subject_id)
    total = (
        await db.execute(select(func.count()).select_from(stmt.order_by(None).subquery()))
    ).scalar_one()
    stmt = stmt.order_by(Grade.created_at.desc(), Grade.id.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(stmt)
    items = [GradeListItem.model_validate(item) for item in result.scalars().all()]
    total_pages = (int(total or 0) + page_size - 1) // page_size if total else 0
    return GradeListResponse(items=items, total=int(total or 0), page=page, page_size=page_size, total_pages=total_pages)


@router.post('', response_model=GradeRead, status_code=status.HTTP_201_CREATED)
async def create_grade(
    payload: GradeCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_teacher(action='manage grades')),
) -> Grade:
    submission = await get_family_record(db, Submission, payload.submission_id, auth.family_id)
    if not submission:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Submission not found')
    student = await get_family_record(db, Student, payload.student_id, auth.family_id)
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Student not found')
    if submission.student_id != payload.student_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Submission does not belong to the selected student')
    if not submission.is_current:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail='Only the current submission version can be graded',
        )

    existing = await db.execute(
        select(Grade).where(Grade.family_id == auth.family_id, Grade.submission_id == payload.submission_id)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='Grade already exists for submission')

    assignment = await get_family_record(db, Assignment, submission.assignment_id, auth.family_id)
    subject = (
        await get_family_record(db, Subject, assignment.subject_id, auth.family_id, options=(selectinload(Subject.grade_scale),))
        if assignment is not None
        else None
    )
    default_scale = await ensure_default_grade_scale(db, auth.family_id)
    letter_grade = payload.letter_grade
    if letter_grade is None and assignment is not None:
        scale = subject.grade_scale if subject and subject.grade_scale else default_scale
        letter_grade, _ = map_percent_to_grade(scale, (payload.score / payload.max_score) * 100)

    grade = Grade(family_id=auth.family_id, **payload.model_dump(exclude={'letter_grade'}), letter_grade=letter_grade)
    db.add(grade)
    await db.flush()
    assignment_target = (
        await db.execute(
            select(AssignmentTarget).where(
                AssignmentTarget.assignment_id == submission.assignment_id,
                AssignmentTarget.student_id == payload.student_id,
            )
        )
    ).scalar_one_or_none()
    if assignment_target:
        assignment_target.status = AssignmentTargetStatus.graded
    await log_event(
        db,
        action=AuditAction.grade_create,
        actor=auth,
        family_id=auth.family_id,
        target_type='grade',
        target_id=grade.id,
        before=None,
        after=_grade_snapshot(grade),
        request=request,
    )
    await create_grading_complete_notifications(
        db,
        family_id=auth.family_id,
        assignment_title=assignment.title if assignment else 'Assignment',
        student_name=student.name,
        score=grade.score,
        max_score=grade.max_score,
    )
    await db.commit()
    invalidate_gradebook_cache(family_id=auth.family_id, student_id=payload.student_id)
    await db.refresh(grade)
    return grade


@router.get('/averages/student/{student_id}', response_model=list[GradeAverageByStudent])
async def averages_by_student(
    student_id: int,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.read_grades, action='view grade averages')),
) -> list[GradeAverageByStudent]:
    student = await get_family_record(db, Student, student_id, auth.family_id)
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Student not found')
    ensure_student_scope(auth, student.id, action='view grade averages')
    stmt = (
        select(
            Grade.student_id,
            Student.name,
            Subject.id,
            Subject.name,
            func.avg(cast(Grade.score / Grade.max_score * 100.0, Float)),
        )
        .join(Student, Student.id == Grade.student_id)
        .join(Submission, Submission.id == Grade.submission_id)
        .join(Assignment, Assignment.id == Submission.assignment_id)
        .join(Subject, Subject.id == Assignment.subject_id)
        .where(Grade.family_id == auth.family_id, Grade.student_id == student_id)
        .group_by(Grade.student_id, Student.name, Subject.id, Subject.name)
        .order_by(Subject.name)
    )
    rows = (await db.execute(stmt)).all()
    return [
        GradeAverageByStudent(
            student_id=row[0],
            student_name=row[1],
            subject_id=row[2],
            subject_name=row[3],
            average_percent=round(float(row[4]), 2),
        )
        for row in rows
    ]


@router.get('/averages/subject/{subject_id}', response_model=list[GradeAverageBySubject])
async def averages_by_subject(
    subject_id: int,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.read_grades, action='view grade averages')),
) -> list[GradeAverageBySubject]:
    subject = await get_family_record(db, Subject, subject_id, auth.family_id)
    if not subject:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Subject not found')
    stmt = (
        select(
            Subject.id,
            Subject.name,
            Grade.student_id,
            Student.name,
            func.avg(cast(Grade.score / Grade.max_score * 100.0, Float)),
        )
        .join(Submission, Submission.id == Grade.submission_id)
        .join(Assignment, Assignment.id == Submission.assignment_id)
        .join(Subject, Subject.id == Assignment.subject_id)
        .join(Student, Student.id == Grade.student_id)
        .where(Grade.family_id == auth.family_id, Subject.id == subject_id)
        .group_by(Subject.id, Subject.name, Grade.student_id, Student.name)
        .order_by(Student.name)
    )
    if auth.role == 'student_viewer':
        stmt = stmt.where(Grade.student_id == get_student_scope_id(auth))
    rows = (await db.execute(stmt)).all()
    return [
        GradeAverageBySubject(
            subject_id=row[0],
            subject_name=row[1],
            student_id=row[2],
            student_name=row[3],
            average_percent=round(float(row[4]), 2),
        )
        for row in rows
    ]


@router.get('/history', response_model=GradeHistoryResponse)
async def grade_history(
    q: str | None = Query(default=None, min_length=1, max_length=200),
    student_id: int | None = Query(default=None),
    subject_id: int | None = Query(default=None),
    grading_period_id: int | None = Query(default=None, gt=0),
    term_id: int | None = Query(default=None, gt=0),
    score_min: float | None = Query(default=None, ge=0),
    score_max: float | None = Query(default=None, ge=0),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_any_role(AppRole.teacher, AppRole.student, action='view grade history')),
) -> GradeHistoryResponse:
    scoped_student_id = student_id
    if auth.role == 'student_viewer':
        scoped_student_id = get_student_scope_id(auth)
        if student_id is not None and student_id != scoped_student_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Role 'student_viewer' is not allowed to view grade history for another student.")

    stmt = (
        select(
            Grade.id,
            Grade.student_id,
            Student.name,
            Subject.id,
            Subject.name,
            Assignment.id,
            Assignment.title,
            Grade.score,
            Grade.max_score,
            Grade.letter_grade,
            Grade.graded_by,
            Grade.created_at,
            Assignment.grading_period_id,
            GradingPeriod.name,
            Grade.notes,
        )
        .join(Student, Student.id == Grade.student_id)
        .join(Submission, Submission.id == Grade.submission_id)
        .join(Assignment, Assignment.id == Submission.assignment_id)
        .join(Subject, Subject.id == Assignment.subject_id)
        .outerjoin(GradingPeriod, GradingPeriod.id == Assignment.grading_period_id)
        .where(Grade.family_id == auth.family_id)
    )
    if scoped_student_id:
        stmt = stmt.where(Grade.student_id == scoped_student_id)
    if subject_id:
        stmt = stmt.where(Subject.id == subject_id)
    if grading_period_id:
        stmt = stmt.where(Assignment.grading_period_id == grading_period_id)
    if term_id:
        stmt = stmt.join(Term, Term.id == GradingPeriod.term_id).where(Term.id == term_id)
    if score_min is not None:
        stmt = stmt.where((Grade.score / Grade.max_score) * 100.0 >= score_min)
    if score_max is not None:
        stmt = stmt.where((Grade.score / Grade.max_score) * 100.0 <= score_max)
    if date_from is not None:
        stmt = stmt.where(Grade.created_at >= _normalize_date_floor(date_from))
    if date_to is not None:
        stmt = stmt.where(Grade.created_at <= _normalize_date_ceil(date_to))
    if q:
        lowered = f'%{q.strip().lower()}%'
        stmt = stmt.where(
            func.lower(
                func.coalesce(Assignment.title, '')
                + ' '
                + func.coalesce(Subject.name, '')
                + ' '
                + func.coalesce(Student.name, '')
                + ' '
                + func.coalesce(Grade.notes, '')
            ).like(lowered)
        )
    total = (
        await db.execute(select(func.count()).select_from(stmt.order_by(None).subquery()))
    ).scalar_one()
    stmt = stmt.order_by(Grade.created_at.desc(), Grade.id.desc()).offset((page - 1) * page_size).limit(page_size)
    rows = (await db.execute(stmt)).all()
    items = [
        GradeHistoryItem(
            grade_id=row[0],
            student_id=row[1],
            student_name=row[2],
            subject_id=row[3],
            subject_name=row[4],
            assignment_id=row[5],
            assignment_title=row[6],
            score=float(row[7]),
            max_score=float(row[8]),
            percent=round((float(row[7]) / float(row[8])) * 100, 2),
            letter_grade=row[9],
            graded_by=row[10],
            created_at=row[11],
            grading_period_id=row[12],
            grading_period_name=row[13],
            notes=row[14],
        )
        for row in rows
    ]
    total_pages = (int(total or 0) + page_size - 1) // page_size if total else 0
    return GradeHistoryResponse(items=items, total=int(total or 0), page=page, page_size=page_size, total_pages=total_pages)


@router.get('/gradebook')
async def gradebook(
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.read_grades, action='view gradebook')),
):
    history = await grade_history(student_id=None, subject_id=None, page=1, page_size=100, db=db, auth=auth)
    return {'items': history.items}


@router.get('/{grade_id}', response_model=GradeRead)
async def get_grade(
    grade_id: int,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.read_grades, action='view grades')),
) -> Grade:
    grade = await get_family_record(db, Grade, grade_id, auth.family_id)
    if not grade:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Grade not found')
    ensure_student_scope(auth, grade.student_id, action='view grades')
    return grade


@router.put('/{grade_id}', response_model=GradeRead)
async def update_grade(
    grade_id: int,
    payload: GradeUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.manage_grading, action='manage grades')),
) -> Grade:
    grade = await get_family_record(db, Grade, grade_id, auth.family_id)
    if not grade:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Grade not found')
    before_snapshot = _grade_snapshot(grade)
    for key, value in payload.model_dump().items():
        setattr(grade, key, value)
    if payload.letter_grade is None:
        submission = await get_family_record(db, Submission, grade.submission_id, auth.family_id)
        assignment = await get_family_record(db, Assignment, submission.assignment_id, auth.family_id) if submission else None
        subject = (
            await get_family_record(db, Subject, assignment.subject_id, auth.family_id, options=(selectinload(Subject.grade_scale),))
            if assignment is not None
            else None
        )
        default_scale = await ensure_default_grade_scale(db, auth.family_id)
        scale = subject.grade_scale if subject and subject.grade_scale else default_scale
        grade.letter_grade, _ = map_percent_to_grade(scale, (grade.score / grade.max_score) * 100)
    await db.flush()
    await log_event(
        db,
        action=AuditAction.grade_update,
        actor=auth,
        family_id=auth.family_id,
        target_type='grade',
        target_id=grade.id,
        before=before_snapshot,
        after=_grade_snapshot(grade),
        request=request,
    )
    await db.commit()
    invalidate_gradebook_cache(family_id=auth.family_id, student_id=grade.student_id)
    await db.refresh(grade)
    return grade


@router.delete('/{grade_id}', status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_grade(
    grade_id: int,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.manage_grading, action='manage grades')),
) -> None:
    grade = await get_family_record(db, Grade, grade_id, auth.family_id)
    if not grade:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Grade not found')
    student_id = grade.student_id
    await db.delete(grade)
    await db.commit()
    invalidate_gradebook_cache(family_id=auth.family_id, student_id=student_id)
