from __future__ import annotations

from collections import defaultdict
from datetime import UTC, date, datetime, time, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.database import get_db
from backend.models import (
    Assignment,
    AssignmentCategory,
    AssignmentStatus,
    AssignmentTarget,
    AssignmentTargetStatus,
    CurriculumLesson,
    CurriculumPackage,
    CurriculumUnit,
    LessonPlan,
    LessonPlanStatus,
    PacingTarget,
    SchoolYear,
    Schedule,
    Student,
)
from backend.routers.schedule import _build_daily_agenda_entries, _schedule_options
from backend.schemas.assignments import AssignmentRead
from backend.schemas.lesson_plans import (
    LessonPlanAssignmentGenerationRequest,
    LessonPlanBulkUpdateRequest,
    LessonPlanCreate,
    LessonPlanGenerationRequest,
    LessonPlanRead,
    LessonPlanUpdate,
    PacingStatusRead,
    PacingStatusSummaryRead,
    PacingTargetCreate,
    PacingTargetRead,
    PacingTargetUpdate,
)
from backend.security import AuthSession, get_family_record
from backend.services.authorization import Capability, ensure_student_scope, get_student_scope_id, require_capabilities
from backend.services.cache import cache_headers, get_cache, invalidate_pacing_cache, is_not_modified

router = APIRouter(tags=['lesson-plans'])
PACING_TTL = timedelta(seconds=45)
PACING_MAX_AGE = 45

_finished_statuses = {LessonPlanStatus.completed, LessonPlanStatus.skipped}


def _lesson_plan_options():
    return (
        selectinload(LessonPlan.student),
        selectinload(LessonPlan.school_year),
        selectinload(LessonPlan.assignments),
        selectinload(LessonPlan.curriculum_lesson).selectinload(CurriculumLesson.resources),
        selectinload(LessonPlan.curriculum_lesson).selectinload(CurriculumLesson.unit).selectinload(CurriculumUnit.package),
    )


def _pacing_target_options():
    return (
        selectinload(PacingTarget.student),
        selectinload(PacingTarget.curriculum_unit).selectinload(CurriculumUnit.package),
        selectinload(PacingTarget.curriculum_unit).selectinload(CurriculumUnit.lessons),
    )


def _assignment_options():
    return (
        selectinload(Assignment.subject),
        selectinload(Assignment.grading_period),
        selectinload(Assignment.targets).selectinload(AssignmentTarget.student),
    )


def _instructional_day_map(school_year: SchoolYear) -> dict[date, bool]:
    event_map: dict[date, bool] = {}
    for event in school_year.calendar_events:
        current = event_map.get(event.date)
        if current is True:
            continue
        event_map[event.date] = event.is_instructional_day
    return event_map


def _is_instructional_day(day_value: date, event_map: dict[date, bool]) -> bool:
    return event_map.get(day_value, day_value.weekday() < 5)


def _assignment_due_datetime(day_value: date) -> datetime:
    return datetime.combine(day_value, time(hour=23, minute=59), tzinfo=UTC)


def _resource_attachments(lesson: CurriculumLesson) -> list[str]:
    attachments: list[str] = []
    for resource in lesson.resources:
        if resource.file_url:
            attachments.append(resource.file_url)
        elif resource.url:
            attachments.append(resource.url)
    return attachments


async def _get_school_year_or_404(db: AsyncSession, school_year_id: int, family_id: int) -> SchoolYear:
    school_year = await get_family_record(
        db,
        SchoolYear,
        school_year_id,
        family_id,
        options=(selectinload(SchoolYear.calendar_events),),
    )
    if not school_year:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='School year not found')
    return school_year


async def _get_student_or_404(db: AsyncSession, student_id: int, family_id: int) -> Student:
    student = await get_family_record(db, Student, student_id, family_id)
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Student not found')
    return student


async def _get_package_or_404(db: AsyncSession, package_id: int, family_id: int) -> CurriculumPackage:
    stmt = (
        select(CurriculumPackage)
        .options(
            selectinload(CurriculumPackage.units)
            .selectinload(CurriculumUnit.lessons)
            .selectinload(CurriculumLesson.resources),
            selectinload(CurriculumPackage.school_year).selectinload(SchoolYear.calendar_events),
        )
        .where(CurriculumPackage.id == package_id, CurriculumPackage.family_id == family_id)
    )
    package = (await db.execute(stmt)).scalar_one_or_none()
    if not package:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Curriculum package not found')
    return package


async def _get_unit_or_404(db: AsyncSession, unit_id: int, family_id: int) -> CurriculumUnit:
    stmt = (
        select(CurriculumUnit)
        .options(selectinload(CurriculumUnit.package), selectinload(CurriculumUnit.lessons))
        .join(CurriculumPackage, CurriculumPackage.id == CurriculumUnit.package_id)
        .where(CurriculumUnit.id == unit_id, CurriculumPackage.family_id == family_id)
    )
    unit = (await db.execute(stmt)).scalar_one_or_none()
    if not unit:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Curriculum unit not found')
    return unit


async def _get_lesson_or_404(db: AsyncSession, lesson_id: int, family_id: int) -> CurriculumLesson:
    stmt = (
        select(CurriculumLesson)
        .options(
            selectinload(CurriculumLesson.resources),
            selectinload(CurriculumLesson.unit).selectinload(CurriculumUnit.package),
        )
        .join(CurriculumUnit, CurriculumUnit.id == CurriculumLesson.unit_id)
        .join(CurriculumPackage, CurriculumPackage.id == CurriculumUnit.package_id)
        .where(CurriculumLesson.id == lesson_id, CurriculumPackage.family_id == family_id)
    )
    lesson = (await db.execute(stmt)).scalar_one_or_none()
    if not lesson:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Curriculum lesson not found')
    return lesson


async def _get_lesson_plan_or_404(db: AsyncSession, family_id: int, lesson_plan_id: int) -> LessonPlan:
    stmt = select(LessonPlan).options(*_lesson_plan_options()).where(
        LessonPlan.id == lesson_plan_id,
        LessonPlan.family_id == family_id,
    )
    lesson_plan = (await db.execute(stmt)).scalar_one_or_none()
    if not lesson_plan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Lesson plan not found')
    return lesson_plan


async def _get_pacing_target_or_404(db: AsyncSession, family_id: int, pacing_target_id: int) -> PacingTarget:
    stmt = select(PacingTarget).options(*_pacing_target_options()).where(
        PacingTarget.id == pacing_target_id,
        PacingTarget.family_id == family_id,
    )
    pacing_target = (await db.execute(stmt)).scalar_one_or_none()
    if not pacing_target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Pacing target not found')
    return pacing_target


async def _ensure_unique_lesson_plan(
    db: AsyncSession,
    *,
    student_id: int,
    curriculum_lesson_id: int,
    current_lesson_plan_id: int | None = None,
) -> None:
    stmt = select(LessonPlan).where(
        LessonPlan.student_id == student_id,
        LessonPlan.curriculum_lesson_id == curriculum_lesson_id,
    )
    if current_lesson_plan_id is not None:
        stmt = stmt.where(LessonPlan.id != current_lesson_plan_id)
    if (await db.execute(stmt)).scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail='A lesson plan already exists for this student and curriculum lesson',
        )


async def _ensure_unique_pacing_target(
    db: AsyncSession,
    *,
    student_id: int,
    curriculum_unit_id: int,
    current_pacing_target_id: int | None = None,
) -> None:
    stmt = select(PacingTarget).where(
        PacingTarget.student_id == student_id,
        PacingTarget.curriculum_unit_id == curriculum_unit_id,
    )
    if current_pacing_target_id is not None:
        stmt = stmt.where(PacingTarget.id != current_pacing_target_id)
    if (await db.execute(stmt)).scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail='A pacing target already exists for this student and curriculum unit',
        )


async def _validate_lesson_plan_payload(
    db: AsyncSession,
    *,
    family_id: int,
    curriculum_lesson_id: int,
    student_id: int,
    school_year_id: int,
) -> tuple[CurriculumLesson, Student, SchoolYear]:
    lesson = await _get_lesson_or_404(db, curriculum_lesson_id, family_id)
    student = await _get_student_or_404(db, student_id, family_id)
    school_year = await _get_school_year_or_404(db, school_year_id, family_id)
    if lesson.unit.package.school_year_id != school_year.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Lesson plans must use the school year linked to the curriculum package',
        )
    return lesson, student, school_year


async def _validate_pacing_target_payload(
    db: AsyncSession,
    *,
    family_id: int,
    curriculum_unit_id: int,
    student_id: int,
) -> None:
    await _get_unit_or_404(db, curriculum_unit_id, family_id)
    await _get_student_or_404(db, student_id, family_id)


async def _refresh_pacing_targets(
    db: AsyncSession,
    *,
    family_id: int,
    student_id: int,
    unit_ids: set[int],
) -> None:
    if not unit_ids:
        return

    pacing_targets = (
        await db.execute(
            select(PacingTarget)
            .options(*_pacing_target_options())
            .where(
                PacingTarget.family_id == family_id,
                PacingTarget.student_id == student_id,
                PacingTarget.curriculum_unit_id.in_(unit_ids),
            )
        )
    ).scalars().all()
    if not pacing_targets:
        return

    lesson_plans = (
        await db.execute(
            select(LessonPlan)
            .options(selectinload(LessonPlan.curriculum_lesson).selectinload(CurriculumLesson.unit))
            .join(CurriculumLesson, CurriculumLesson.id == LessonPlan.curriculum_lesson_id)
            .where(
                LessonPlan.family_id == family_id,
                LessonPlan.student_id == student_id,
                CurriculumLesson.unit_id.in_(unit_ids),
            )
        )
    ).scalars().all()

    plans_by_unit: dict[int, list[LessonPlan]] = defaultdict(list)
    for lesson_plan in lesson_plans:
        plans_by_unit[lesson_plan.curriculum_lesson.unit_id].append(lesson_plan)

    for pacing_target in pacing_targets:
        total_lessons = len(pacing_target.curriculum_unit.lessons)
        plans = plans_by_unit.get(pacing_target.curriculum_unit_id, [])
        if total_lessons and len(plans) == total_lessons and all(plan.status in _finished_statuses for plan in plans):
            completion_dates = [
                plan.completed_at.date() if plan.completed_at is not None else plan.target_date
                for plan in plans
            ]
            pacing_target.actual_completion_date = max(completion_dates) if completion_dates else None
        else:
            pacing_target.actual_completion_date = None


def _apply_lesson_plan_state(lesson_plan: LessonPlan, *, status_value: LessonPlanStatus) -> None:
    lesson_plan.status = status_value
    lesson_plan.completed_at = datetime.now(UTC) if status_value == LessonPlanStatus.completed else None


def _build_pacing_status(pacing_target: PacingTarget, plans: list[LessonPlan], today: date) -> PacingStatusRead:
    total_lessons = len(pacing_target.curriculum_unit.lessons)
    completed_lessons = sum(1 for plan in plans if plan.status in _finished_statuses)
    planned_lessons = len(plans)
    remaining_lessons = max(total_lessons - completed_lessons, 0)

    if pacing_target.actual_completion_date is not None:
        if pacing_target.actual_completion_date < pacing_target.target_end_date:
            pace_status = 'ahead'
        elif pacing_target.actual_completion_date > pacing_target.target_end_date:
            pace_status = 'behind'
        else:
            pace_status = 'on_track'
    elif today > pacing_target.target_end_date and completed_lessons < total_lessons:
        pace_status = 'behind'
    elif today < pacing_target.target_start_date or total_lessons == 0:
        pace_status = 'on_track'
    else:
        total_window_days = max((pacing_target.target_end_date - pacing_target.target_start_date).days + 1, 1)
        elapsed_days = min(max((today - pacing_target.target_start_date).days + 1, 0), total_window_days)
        expected_progress = elapsed_days / total_window_days
        actual_progress = completed_lessons / total_lessons
        if actual_progress > expected_progress + 0.15:
            pace_status = 'ahead'
        elif actual_progress + 0.15 < expected_progress:
            pace_status = 'behind'
        else:
            pace_status = 'on_track'

    return PacingStatusRead(
        pacing_target_id=pacing_target.id,
        curriculum_unit_id=pacing_target.curriculum_unit_id,
        unit_name=pacing_target.curriculum_unit.name,
        package_id=pacing_target.curriculum_unit.package_id,
        package_name=pacing_target.curriculum_unit.package.name,
        subject_id=pacing_target.curriculum_unit.package.subject_id,
        target_start_date=pacing_target.target_start_date,
        target_end_date=pacing_target.target_end_date,
        actual_completion_date=pacing_target.actual_completion_date,
        status=pace_status,
        total_lessons=total_lessons,
        planned_lessons=planned_lessons,
        completed_lessons=completed_lessons,
        remaining_lessons=remaining_lessons,
    )


@router.get('/lesson-plans', response_model=list[LessonPlanRead])
async def list_lesson_plans(
    student_id: int | None = Query(default=None, gt=0),
    school_year_id: int | None = Query(default=None, gt=0),
    subject_id: int | None = Query(default=None, gt=0),
    status_filter: LessonPlanStatus | None = Query(default=None, alias='status'),
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.read_curriculum, action='view lesson plans')),
) -> list[LessonPlan]:
    scoped_student_id = student_id
    if auth.role == 'student_viewer':
        scoped_student_id = get_student_scope_id(auth)
        if student_id is not None and student_id != scoped_student_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Role 'student_viewer' is not allowed to view lesson plans for another student.",
            )

    stmt = (
        select(LessonPlan)
        .options(*_lesson_plan_options())
        .join(CurriculumLesson, CurriculumLesson.id == LessonPlan.curriculum_lesson_id)
        .join(CurriculumUnit, CurriculumUnit.id == CurriculumLesson.unit_id)
        .join(CurriculumPackage, CurriculumPackage.id == CurriculumUnit.package_id)
        .where(LessonPlan.family_id == auth.family_id)
    )
    if scoped_student_id is not None:
        stmt = stmt.where(LessonPlan.student_id == scoped_student_id)
    if school_year_id is not None:
        stmt = stmt.where(LessonPlan.school_year_id == school_year_id)
    if subject_id is not None:
        stmt = stmt.where(CurriculumPackage.subject_id == subject_id)
    if status_filter is not None:
        stmt = stmt.where(LessonPlan.status == status_filter)
    if start_date is not None:
        stmt = stmt.where(LessonPlan.target_date >= start_date)
    if end_date is not None:
        stmt = stmt.where(LessonPlan.target_date <= end_date)
    result = await db.execute(stmt.order_by(LessonPlan.target_date, LessonPlan.id))
    return list(result.scalars().all())


@router.post('/lesson-plans', response_model=LessonPlanRead, status_code=status.HTTP_201_CREATED)
async def create_lesson_plan(
    payload: LessonPlanCreate,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.manage_curriculum, action='manage lesson plans')),
) -> LessonPlan:
    lesson, _, _ = await _validate_lesson_plan_payload(
        db,
        family_id=auth.family_id,
        curriculum_lesson_id=payload.curriculum_lesson_id,
        student_id=payload.student_id,
        school_year_id=payload.school_year_id,
    )
    await _ensure_unique_lesson_plan(
        db,
        student_id=payload.student_id,
        curriculum_lesson_id=payload.curriculum_lesson_id,
    )

    lesson_plan = LessonPlan(
        family_id=auth.family_id,
        curriculum_lesson_id=payload.curriculum_lesson_id,
        student_id=payload.student_id,
        school_year_id=payload.school_year_id,
        target_date=payload.target_date,
        estimated_duration_minutes=payload.estimated_duration_minutes,
        notes=payload.notes,
    )
    _apply_lesson_plan_state(lesson_plan, status_value=payload.status)
    db.add(lesson_plan)
    await db.flush()
    await _refresh_pacing_targets(
        db,
        family_id=auth.family_id,
        student_id=payload.student_id,
        unit_ids={lesson.unit_id},
    )
    await db.commit()
    invalidate_pacing_cache(family_id=auth.family_id, student_id=payload.student_id)
    return await _get_lesson_plan_or_404(db, auth.family_id, lesson_plan.id)


@router.get('/lesson-plans/{lesson_plan_id:int}', response_model=LessonPlanRead)
async def get_lesson_plan(
    lesson_plan_id: int,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.read_curriculum, action='view lesson plans')),
) -> LessonPlan:
    lesson_plan = await _get_lesson_plan_or_404(db, auth.family_id, lesson_plan_id)
    ensure_student_scope(auth, lesson_plan.student_id, action='view lesson plans')
    return lesson_plan


@router.put('/lesson-plans/{lesson_plan_id:int}', response_model=LessonPlanRead)
async def update_lesson_plan(
    lesson_plan_id: int,
    payload: LessonPlanUpdate,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.manage_curriculum, action='manage lesson plans')),
) -> LessonPlan:
    lesson_plan = await _get_lesson_plan_or_404(db, auth.family_id, lesson_plan_id)
    lesson, _, _ = await _validate_lesson_plan_payload(
        db,
        family_id=auth.family_id,
        curriculum_lesson_id=payload.curriculum_lesson_id,
        student_id=payload.student_id,
        school_year_id=payload.school_year_id,
    )
    await _ensure_unique_lesson_plan(
        db,
        student_id=payload.student_id,
        curriculum_lesson_id=payload.curriculum_lesson_id,
        current_lesson_plan_id=lesson_plan.id,
    )

    impacted_unit_ids = {lesson_plan.curriculum_lesson.unit_id, lesson.unit_id}
    impacted_student_ids = {lesson_plan.student_id, payload.student_id}

    lesson_plan.curriculum_lesson_id = payload.curriculum_lesson_id
    lesson_plan.student_id = payload.student_id
    lesson_plan.school_year_id = payload.school_year_id
    lesson_plan.target_date = payload.target_date
    lesson_plan.estimated_duration_minutes = payload.estimated_duration_minutes
    lesson_plan.notes = payload.notes
    _apply_lesson_plan_state(lesson_plan, status_value=payload.status)

    for student_id_value in impacted_student_ids:
        await _refresh_pacing_targets(
            db,
            family_id=auth.family_id,
            student_id=student_id_value,
            unit_ids=impacted_unit_ids,
        )
    await db.commit()
    for student_id_value in impacted_student_ids:
        invalidate_pacing_cache(family_id=auth.family_id, student_id=student_id_value)
    return await _get_lesson_plan_or_404(db, auth.family_id, lesson_plan.id)


@router.delete('/lesson-plans/{lesson_plan_id:int}', status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_lesson_plan(
    lesson_plan_id: int,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.manage_curriculum, action='manage lesson plans')),
) -> None:
    lesson_plan = await _get_lesson_plan_or_404(db, auth.family_id, lesson_plan_id)
    unit_id = lesson_plan.curriculum_lesson.unit_id
    await db.execute(
        update(Assignment)
        .where(Assignment.family_id == auth.family_id, Assignment.lesson_plan_id == lesson_plan.id)
        .values(lesson_plan_id=None)
    )
    await db.delete(lesson_plan)
    await db.flush()
    await _refresh_pacing_targets(
        db,
        family_id=auth.family_id,
        student_id=lesson_plan.student_id,
        unit_ids={unit_id},
    )
    await db.commit()
    invalidate_pacing_cache(family_id=auth.family_id, student_id=lesson_plan.student_id)


@router.post('/lesson-plans/generate', response_model=list[LessonPlanRead], status_code=status.HTTP_201_CREATED)
async def generate_lesson_plans(
    payload: LessonPlanGenerationRequest,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.manage_curriculum, action='generate lesson plans')),
) -> list[LessonPlan]:
    package = await _get_package_or_404(db, payload.package_id, auth.family_id)
    await _get_student_or_404(db, payload.student_id, auth.family_id)
    school_year = package.school_year
    if payload.school_year_id is not None and payload.school_year_id != school_year.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Generated lesson plans must use the curriculum package school year',
        )

    lessons = [
        lesson
        for unit in sorted(package.units, key=lambda item: (item.sequence_order, item.id))
        for lesson in sorted(unit.lessons, key=lambda item: (item.sequence_order, item.id))
    ]
    if not lessons:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Curriculum package has no lessons to schedule')

    existing_plans = (
        await db.execute(
            select(LessonPlan)
            .options(selectinload(LessonPlan.curriculum_lesson).selectinload(CurriculumLesson.unit))
            .join(CurriculumLesson, CurriculumLesson.id == LessonPlan.curriculum_lesson_id)
            .join(CurriculumUnit, CurriculumUnit.id == CurriculumLesson.unit_id)
            .where(
                LessonPlan.family_id == auth.family_id,
                LessonPlan.student_id == payload.student_id,
                CurriculumUnit.package_id == package.id,
            )
        )
    ).scalars().all()
    if existing_plans and not payload.overwrite_existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail='Lesson plans already exist for this curriculum package and student',
        )
    if existing_plans:
        existing_ids = [plan.id for plan in existing_plans]
        linked_assignment = (
            await db.execute(
                select(Assignment.id).where(
                    Assignment.family_id == auth.family_id,
                    Assignment.lesson_plan_id.in_(existing_ids),
                )
            )
        ).first()
        if linked_assignment:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail='Existing lesson plans already have generated assignments and cannot be overwritten',
            )
        for existing_plan in existing_plans:
            await db.delete(existing_plan)
        await db.flush()

    schedule_rows = (
        await db.execute(
            select(Schedule)
            .options(*_schedule_options())
            .where(
                Schedule.family_id == auth.family_id,
                Schedule.student_id == payload.student_id,
                Schedule.school_year_id == school_year.id,
            )
            .order_by(Schedule.name)
        )
    ).scalars().all()
    if not schedule_rows:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Create a student schedule for this school year before generating lesson plans',
        )

    start_date = max(payload.start_date or school_year.start_date, school_year.start_date)
    event_map = _instructional_day_map(school_year)
    available_slots: list[tuple[date, time]] = []
    current_day = start_date
    while current_day <= school_year.end_date and len(available_slots) < len(lessons):
        if _is_instructional_day(current_day, event_map):
            agenda = [item for item in _build_daily_agenda_entries(schedule_rows, current_day) if item.subject_id == package.subject_id]
            for item in agenda:
                available_slots.append((current_day, item.start_time))
                if len(available_slots) >= len(lessons):
                    break
        current_day += timedelta(days=1)

    if len(available_slots) < len(lessons):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Not enough scheduled class blocks are available to place every lesson in this package',
        )

    created_plans: list[LessonPlan] = []
    unit_ranges: dict[int, list[date]] = defaultdict(list)
    for lesson, (target_day, _) in zip(lessons, available_slots, strict=False):
        unit_ranges[lesson.unit_id].append(target_day)
        lesson_plan = LessonPlan(
            family_id=auth.family_id,
            curriculum_lesson_id=lesson.id,
            student_id=payload.student_id,
            school_year_id=school_year.id,
            target_date=target_day,
            estimated_duration_minutes=lesson.estimated_duration_minutes or payload.default_duration_minutes,
            status=LessonPlanStatus.planned,
        )
        db.add(lesson_plan)
        created_plans.append(lesson_plan)
    await db.flush()

    existing_targets = {
        target.curriculum_unit_id: target
        for target in (
            await db.execute(
                select(PacingTarget).where(
                    PacingTarget.family_id == auth.family_id,
                    PacingTarget.student_id == payload.student_id,
                    PacingTarget.curriculum_unit_id.in_(set(unit_ranges)),
                )
            )
        ).scalars().all()
    }
    for unit in package.units:
        if unit.id not in unit_ranges:
            continue
        start_day = min(unit_ranges[unit.id])
        end_day = max(unit_ranges[unit.id])
        target = existing_targets.get(unit.id)
        if target is None:
            db.add(
                PacingTarget(
                    family_id=auth.family_id,
                    curriculum_unit_id=unit.id,
                    student_id=payload.student_id,
                    target_start_date=start_day,
                    target_end_date=end_day,
                )
            )
        else:
            target.target_start_date = start_day
            target.target_end_date = end_day
    await db.flush()
    await _refresh_pacing_targets(
        db,
        family_id=auth.family_id,
        student_id=payload.student_id,
        unit_ids=set(unit_ranges),
    )
    await db.commit()
    invalidate_pacing_cache(family_id=auth.family_id, student_id=payload.student_id)

    result = await db.execute(
        select(LessonPlan)
        .options(*_lesson_plan_options())
        .where(LessonPlan.id.in_([lesson_plan.id for lesson_plan in created_plans]))
        .order_by(LessonPlan.target_date, LessonPlan.id)
    )
    return list(result.scalars().all())


@router.post('/lesson-plans/bulk-status', response_model=list[LessonPlanRead])
async def bulk_update_lesson_plan_status(
    payload: LessonPlanBulkUpdateRequest,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.manage_curriculum, action='manage lesson plans')),
) -> list[LessonPlan]:
    lesson_plans = (
        await db.execute(
            select(LessonPlan)
            .options(*_lesson_plan_options())
            .where(
                LessonPlan.family_id == auth.family_id,
                LessonPlan.id.in_(payload.lesson_plan_ids),
            )
            .order_by(LessonPlan.target_date, LessonPlan.id)
        )
    ).scalars().all()
    if len(lesson_plans) != len(set(payload.lesson_plan_ids)):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='One or more lesson plans were not found')

    impacted_units: dict[int, set[int]] = defaultdict(set)
    for lesson_plan in lesson_plans:
        impacted_units[lesson_plan.student_id].add(lesson_plan.curriculum_lesson.unit_id)
        _apply_lesson_plan_state(lesson_plan, status_value=payload.status)
        if payload.status == LessonPlanStatus.rescheduled and payload.target_date is not None:
            lesson_plan.target_date = payload.target_date
        if payload.notes is not None:
            lesson_plan.notes = payload.notes

    for student_id_value, unit_ids in impacted_units.items():
        await _refresh_pacing_targets(
            db,
            family_id=auth.family_id,
            student_id=student_id_value,
            unit_ids=unit_ids,
        )
    await db.commit()
    for student_id_value in impacted_units:
        invalidate_pacing_cache(family_id=auth.family_id, student_id=student_id_value)
    return lesson_plans


@router.post('/lesson-plans/generate-assignments', response_model=list[AssignmentRead], status_code=status.HTTP_201_CREATED)
async def generate_assignments_from_lesson_plans(
    payload: LessonPlanAssignmentGenerationRequest,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.manage_curriculum, action='generate assignments from lesson plans')),
) -> list[Assignment]:
    lesson_plans = (
        await db.execute(
            select(LessonPlan)
            .options(*_lesson_plan_options())
            .where(
                LessonPlan.family_id == auth.family_id,
                LessonPlan.id.in_(payload.lesson_plan_ids),
            )
            .order_by(LessonPlan.target_date, LessonPlan.id)
        )
    ).scalars().all()
    if len(lesson_plans) != len(set(payload.lesson_plan_ids)):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='One or more lesson plans were not found')

    assignment_ids: list[int] = []
    for lesson_plan in lesson_plans:
        due_date = _assignment_due_datetime(lesson_plan.target_date)
        existing_assignment = (
            await db.execute(
                select(Assignment)
                .options(*_assignment_options())
                .where(Assignment.family_id == auth.family_id, Assignment.lesson_plan_id == lesson_plan.id)
            )
        ).scalar_one_or_none()
        if existing_assignment is not None:
            if payload.include_existing:
                assignment_ids.append(existing_assignment.id)
            continue

        assignment = Assignment(
            family_id=auth.family_id,
            title=lesson_plan.curriculum_lesson.name,
            subject_id=lesson_plan.curriculum_lesson.unit.package.subject_id,
            description=lesson_plan.curriculum_lesson.description or lesson_plan.notes,
            due_date=due_date,
            status=AssignmentStatus.pending,
            category=AssignmentCategory.homework,
            attachments=_resource_attachments(lesson_plan.curriculum_lesson),
            lesson_plan_id=lesson_plan.id,
        )
        assignment.targets.append(
            AssignmentTarget(
                student_id=lesson_plan.student_id,
                due_date=due_date,
                status=AssignmentTargetStatus.assigned,
            )
        )
        db.add(assignment)
        await db.flush()
        assignment_ids.append(assignment.id)

    await db.commit()
    if not assignment_ids:
        return []
    assignments = (
        await db.execute(
            select(Assignment)
            .options(*_assignment_options())
            .where(Assignment.id.in_(assignment_ids))
            .order_by(Assignment.due_date, Assignment.id)
        )
    ).scalars().all()
    return list(assignments)


@router.get('/pacing-targets', response_model=list[PacingTargetRead])
async def list_pacing_targets(
    student_id: int | None = Query(default=None, gt=0),
    subject_id: int | None = Query(default=None, gt=0),
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.read_curriculum, action='view pacing targets')),
) -> list[PacingTarget]:
    scoped_student_id = student_id
    if auth.role == 'student_viewer':
        scoped_student_id = get_student_scope_id(auth)
        if student_id is not None and student_id != scoped_student_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Role 'student_viewer' is not allowed to view pacing targets for another student.",
            )

    stmt = (
        select(PacingTarget)
        .options(*_pacing_target_options())
        .join(CurriculumUnit, CurriculumUnit.id == PacingTarget.curriculum_unit_id)
        .join(CurriculumPackage, CurriculumPackage.id == CurriculumUnit.package_id)
        .where(PacingTarget.family_id == auth.family_id)
    )
    if scoped_student_id is not None:
        stmt = stmt.where(PacingTarget.student_id == scoped_student_id)
    if subject_id is not None:
        stmt = stmt.where(CurriculumPackage.subject_id == subject_id)
    result = await db.execute(stmt.order_by(PacingTarget.target_start_date, PacingTarget.id))
    return list(result.scalars().all())


@router.post('/pacing-targets', response_model=PacingTargetRead, status_code=status.HTTP_201_CREATED)
async def create_pacing_target(
    payload: PacingTargetCreate,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.manage_curriculum, action='manage pacing targets')),
) -> PacingTarget:
    await _validate_pacing_target_payload(
        db,
        family_id=auth.family_id,
        curriculum_unit_id=payload.curriculum_unit_id,
        student_id=payload.student_id,
    )
    await _ensure_unique_pacing_target(
        db,
        student_id=payload.student_id,
        curriculum_unit_id=payload.curriculum_unit_id,
    )

    pacing_target = PacingTarget(
        family_id=auth.family_id,
        curriculum_unit_id=payload.curriculum_unit_id,
        student_id=payload.student_id,
        target_start_date=payload.target_start_date,
        target_end_date=payload.target_end_date,
    )
    db.add(pacing_target)
    await db.flush()
    await _refresh_pacing_targets(
        db,
        family_id=auth.family_id,
        student_id=payload.student_id,
        unit_ids={payload.curriculum_unit_id},
    )
    await db.commit()
    invalidate_pacing_cache(family_id=auth.family_id, student_id=payload.student_id)
    return await _get_pacing_target_or_404(db, auth.family_id, pacing_target.id)


@router.get('/pacing-targets/{pacing_target_id}', response_model=PacingTargetRead)
async def get_pacing_target(
    pacing_target_id: int,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.read_curriculum, action='view pacing targets')),
) -> PacingTarget:
    pacing_target = await _get_pacing_target_or_404(db, auth.family_id, pacing_target_id)
    ensure_student_scope(auth, pacing_target.student_id, action='view pacing targets')
    return pacing_target


@router.put('/pacing-targets/{pacing_target_id}', response_model=PacingTargetRead)
async def update_pacing_target(
    pacing_target_id: int,
    payload: PacingTargetUpdate,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.manage_curriculum, action='manage pacing targets')),
) -> PacingTarget:
    pacing_target = await _get_pacing_target_or_404(db, auth.family_id, pacing_target_id)
    previous_student_id = pacing_target.student_id
    await _validate_pacing_target_payload(
        db,
        family_id=auth.family_id,
        curriculum_unit_id=payload.curriculum_unit_id,
        student_id=payload.student_id,
    )
    await _ensure_unique_pacing_target(
        db,
        student_id=payload.student_id,
        curriculum_unit_id=payload.curriculum_unit_id,
        current_pacing_target_id=pacing_target.id,
    )

    pacing_target.curriculum_unit_id = payload.curriculum_unit_id
    pacing_target.student_id = payload.student_id
    pacing_target.target_start_date = payload.target_start_date
    pacing_target.target_end_date = payload.target_end_date
    await _refresh_pacing_targets(
        db,
        family_id=auth.family_id,
        student_id=payload.student_id,
        unit_ids={payload.curriculum_unit_id},
    )
    await db.commit()
    invalidate_pacing_cache(family_id=auth.family_id, student_id=payload.student_id)
    if previous_student_id != payload.student_id:
        invalidate_pacing_cache(family_id=auth.family_id, student_id=previous_student_id)
    return await _get_pacing_target_or_404(db, auth.family_id, pacing_target.id)


@router.delete('/pacing-targets/{pacing_target_id}', status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_pacing_target(
    pacing_target_id: int,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.manage_curriculum, action='manage pacing targets')),
) -> None:
    pacing_target = await _get_pacing_target_or_404(db, auth.family_id, pacing_target_id)
    student_id = pacing_target.student_id
    await db.delete(pacing_target)
    await db.commit()
    invalidate_pacing_cache(family_id=auth.family_id, student_id=student_id)


@router.get('/pacing/{student_id}', response_model=PacingStatusSummaryRead)
async def get_pacing_status(
    student_id: int,
    request: Request,
    response: Response,
    subject_id: int | None = Query(default=None, gt=0),
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.read_curriculum, action='view pacing status')),
) -> PacingStatusSummaryRead:
    await _get_student_or_404(db, student_id, auth.family_id)
    ensure_student_scope(auth, student_id, action='view pacing status')
    entry = await get_cache().get_or_set(
        f'pacing:{auth.family_id}:{student_id}:status:{subject_id or "all"}',
        ttl=PACING_TTL,
        factory=lambda: _build_pacing_status_payload(db, family_id=auth.family_id, student_id=student_id, subject_id=subject_id),
    )
    headers = cache_headers(entry, max_age_seconds=PACING_MAX_AGE)
    if request is not None and is_not_modified(request, entry):
        return Response(status_code=status.HTTP_304_NOT_MODIFIED, headers=headers)
    if response is not None:
        response.headers.update(headers)
    return PacingStatusSummaryRead.model_validate(entry.value)


async def _build_pacing_status_payload(
    db: AsyncSession,
    *,
    family_id: int,
    student_id: int,
    subject_id: int | None,
) -> dict[str, object]:
    stmt = (
        select(PacingTarget)
        .options(*_pacing_target_options())
        .join(CurriculumUnit, CurriculumUnit.id == PacingTarget.curriculum_unit_id)
        .join(CurriculumPackage, CurriculumPackage.id == CurriculumUnit.package_id)
        .where(
            PacingTarget.family_id == family_id,
            PacingTarget.student_id == student_id,
        )
    )
    if subject_id is not None:
        stmt = stmt.where(CurriculumPackage.subject_id == subject_id)
    pacing_targets = (await db.execute(stmt.order_by(PacingTarget.target_start_date, PacingTarget.id))).scalars().all()
    if not pacing_targets:
        return PacingStatusSummaryRead(student_id=student_id, subject_id=subject_id, items=[]).model_dump(mode='json')

    unit_ids = {target.curriculum_unit_id for target in pacing_targets}
    lesson_plans = (
        await db.execute(
            select(LessonPlan)
            .options(selectinload(LessonPlan.curriculum_lesson).selectinload(CurriculumLesson.unit))
            .join(CurriculumLesson, CurriculumLesson.id == LessonPlan.curriculum_lesson_id)
            .where(
                LessonPlan.family_id == family_id,
                LessonPlan.student_id == student_id,
                CurriculumLesson.unit_id.in_(unit_ids),
            )
        )
    ).scalars().all()
    plans_by_unit: dict[int, list[LessonPlan]] = defaultdict(list)
    for lesson_plan in lesson_plans:
        plans_by_unit[lesson_plan.curriculum_lesson.unit_id].append(lesson_plan)

    today = datetime.now(UTC).date()
    items = [_build_pacing_status(pacing_target, plans_by_unit.get(pacing_target.curriculum_unit_id, []), today) for pacing_target in pacing_targets]
    return PacingStatusSummaryRead(student_id=student_id, subject_id=subject_id, items=items).model_dump(mode='json')
