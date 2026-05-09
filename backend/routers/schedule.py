from __future__ import annotations

from datetime import date, time, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.database import get_db
from backend.models import Schedule, ScheduleBlock, ScheduleOverride, ScheduleOverrideType, SchoolYear, Student, Subject
from backend.schemas.schedule import (
    AgendaItemRead,
    DailyAgendaRead,
    ScheduleBlockCreate,
    ScheduleBlockRead,
    ScheduleBlockUpdate,
    ScheduleCreate,
    ScheduleDetail,
    ScheduleOverrideCreate,
    ScheduleOverrideRead,
    ScheduleRead,
    ScheduleUpdate,
    WeeklyAgendaRead,
)
from backend.security import AuthSession, get_family_record
from backend.services.authorization import Capability, ensure_student_scope, require_capabilities

router = APIRouter(prefix='/schedule', tags=['schedule'])

DAY_NAMES = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']


def _schedule_options():
    return (
        selectinload(Schedule.student),
        selectinload(Schedule.school_year),
        selectinload(Schedule.blocks).selectinload(ScheduleBlock.subject),
        selectinload(Schedule.overrides).selectinload(ScheduleOverride.subject),
    )


async def _get_student_or_404(db: AsyncSession, student_id: int, family_id: int) -> Student:
    student = await get_family_record(db, Student, student_id, family_id)
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Student not found')
    return student


async def _get_school_year_or_404(db: AsyncSession, school_year_id: int, family_id: int) -> SchoolYear:
    school_year = await get_family_record(db, SchoolYear, school_year_id, family_id)
    if not school_year:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='School year not found')
    return school_year


async def _get_subject_or_404(db: AsyncSession, subject_id: int, family_id: int) -> Subject:
    subject = await get_family_record(db, Subject, subject_id, family_id)
    if not subject:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Subject not found')
    return subject


async def _get_schedule_or_404(db: AsyncSession, schedule_id: int, family_id: int) -> Schedule:
    result = await db.execute(
        select(Schedule).options(*_schedule_options()).where(Schedule.id == schedule_id, Schedule.family_id == family_id)
    )
    schedule = result.scalar_one_or_none()
    if not schedule:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Schedule not found')
    return schedule


async def _get_block_or_404(db: AsyncSession, block_id: int, family_id: int) -> ScheduleBlock:
    result = await db.execute(
        select(ScheduleBlock)
        .options(selectinload(ScheduleBlock.subject), selectinload(ScheduleBlock.schedule))
        .join(Schedule, Schedule.id == ScheduleBlock.schedule_id)
        .where(ScheduleBlock.id == block_id, Schedule.family_id == family_id)
    )
    block = result.scalar_one_or_none()
    if not block:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Schedule block not found')
    return block


async def _get_override_or_404(db: AsyncSession, override_id: int, family_id: int) -> ScheduleOverride:
    result = await db.execute(
        select(ScheduleOverride)
        .options(selectinload(ScheduleOverride.subject), selectinload(ScheduleOverride.schedule))
        .join(Schedule, Schedule.id == ScheduleOverride.schedule_id)
        .where(ScheduleOverride.id == override_id, Schedule.family_id == family_id)
    )
    override = result.scalar_one_or_none()
    if not override:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Schedule override not found')
    return override


async def _ensure_unique_schedule_name(
    db: AsyncSession,
    *,
    family_id: int,
    student_id: int,
    school_year_id: int,
    name: str,
    current_schedule_id: int | None = None,
) -> None:
    stmt = select(Schedule).where(
        Schedule.family_id == family_id,
        Schedule.student_id == student_id,
        Schedule.school_year_id == school_year_id,
        Schedule.name == name,
    )
    if current_schedule_id is not None:
        stmt = stmt.where(Schedule.id != current_schedule_id)
    if (await db.execute(stmt)).scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='Schedule already exists for this student and school year')


def _format_time(value: time) -> str:
    return value.strftime('%H:%M')


def _raise_block_conflict(conflicts: list[tuple[ScheduleBlock, Schedule]]) -> None:
    messages = [
        f"{block.subject.name} ({schedule.name}) from {_format_time(block.start_time)} to {_format_time(block.end_time)}"
        for block, schedule in conflicts
    ]
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=f"Schedule block overlap detected on {DAY_NAMES[conflicts[0][0].day_of_week]}: {'; '.join(messages)}",
    )


async def _ensure_block_no_conflicts(
    db: AsyncSession,
    *,
    schedule: Schedule,
    day_of_week: int,
    start_time: time,
    end_time: time,
    current_block_id: int | None = None,
) -> None:
    result = await db.execute(
        select(ScheduleBlock, Schedule)
        .join(Schedule, Schedule.id == ScheduleBlock.schedule_id)
        .options(selectinload(ScheduleBlock.subject))
        .where(
            Schedule.family_id == schedule.family_id,
            Schedule.student_id == schedule.student_id,
            Schedule.school_year_id == schedule.school_year_id,
            ScheduleBlock.day_of_week == day_of_week,
            ScheduleBlock.start_time < end_time,
            ScheduleBlock.end_time > start_time,
        )
    )
    conflicts = [(block, related_schedule) for block, related_schedule in result.all() if block.id != current_block_id]
    if conflicts:
        _raise_block_conflict(conflicts)


def _ensure_override_in_school_year(schedule: Schedule, override_date: date) -> None:
    if override_date < schedule.school_year.start_date or override_date > schedule.school_year.end_date:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Override date must fall within the linked school year')


async def _ensure_override_block_belongs_to_schedule(
    db: AsyncSession,
    *,
    schedule: Schedule,
    original_block_id: int | None,
) -> ScheduleBlock | None:
    if original_block_id is None:
        return None
    block = await _get_block_or_404(db, original_block_id, schedule.family_id)
    if block.schedule_id != schedule.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Override block must belong to the selected schedule')
    return block


def _agenda_sort_key(item: AgendaItemRead) -> tuple[str, str, str]:
    return (
        item.start_time.isoformat(),
        item.end_time.isoformat(),
        item.subject_name.lower(),
    )


def _build_daily_agenda_entries(schedules: list[Schedule], target_date: date, *, skip_override_id: int | None = None) -> list[AgendaItemRead]:
    items: dict[tuple[str, int], AgendaItemRead] = {}
    day_of_week = target_date.weekday()

    for schedule in schedules:
        block_lookup = {block.id: block for block in schedule.blocks}
        for block in schedule.blocks:
            if block.day_of_week != day_of_week:
                continue
            items[('block', block.id)] = AgendaItemRead(
                schedule_id=schedule.id,
                schedule_name=schedule.name,
                block_id=block.id,
                date=target_date,
                day_of_week=day_of_week,
                source='recurring',
                subject_id=block.subject_id,
                subject_name=block.subject.name,
                subject_color=block.subject.color,
                start_time=block.start_time,
                end_time=block.end_time,
                location=block.location,
                notes=block.notes,
            )

        for override in schedule.overrides:
            if override.id == skip_override_id or override.date != target_date:
                continue
            if override.override_type in {ScheduleOverrideType.cancel, ScheduleOverrideType.reschedule} and override.original_block_id is not None:
                items.pop(('block', override.original_block_id), None)
            if override.override_type == ScheduleOverrideType.cancel:
                continue
            if override.start_time is None or override.end_time is None:
                continue
            block = block_lookup.get(override.original_block_id or -1)
            subject = override.subject or (block.subject if block else None)
            if subject is None:
                continue
            items[('override', override.id)] = AgendaItemRead(
                schedule_id=schedule.id,
                schedule_name=schedule.name,
                block_id=override.original_block_id,
                override_id=override.id,
                date=target_date,
                day_of_week=day_of_week,
                source='override',
                override_type=override.override_type,
                subject_id=subject.id,
                subject_name=subject.name,
                subject_color=subject.color,
                start_time=override.start_time,
                end_time=override.end_time,
                location=block.location if block else None,
                notes=block.notes if block else None,
                reason=override.reason,
            )

    return sorted(items.values(), key=_agenda_sort_key)


async def _get_student_schedules_for_date(
    db: AsyncSession,
    *,
    family_id: int,
    student_id: int,
    target_date: date,
) -> list[Schedule]:
    result = await db.execute(
        select(Schedule)
        .options(*_schedule_options())
        .join(SchoolYear, SchoolYear.id == Schedule.school_year_id)
        .where(
            Schedule.family_id == family_id,
            Schedule.student_id == student_id,
            SchoolYear.start_date <= target_date,
            SchoolYear.end_date >= target_date,
        )
        .order_by(Schedule.name)
    )
    return list(result.scalars().all())


async def _ensure_override_no_duplicates(
    db: AsyncSession,
    *,
    schedule_id: int,
    date_value: date,
    original_block_id: int | None,
) -> None:
    if original_block_id is None:
        return
    stmt = select(ScheduleOverride).where(
        ScheduleOverride.schedule_id == schedule_id,
        ScheduleOverride.date == date_value,
        ScheduleOverride.original_block_id == original_block_id,
    )
    if (await db.execute(stmt)).scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='An override already exists for this block on that date')


async def _ensure_override_no_conflicts(
    db: AsyncSession,
    *,
    schedule: Schedule,
    payload: ScheduleOverrideCreate,
) -> None:
    if payload.override_type == ScheduleOverrideType.cancel or payload.start_time is None or payload.end_time is None:
        return
    schedules = await _get_student_schedules_for_date(
        db,
        family_id=schedule.family_id,
        student_id=schedule.student_id,
        target_date=payload.date,
    )
    agenda = _build_daily_agenda_entries(schedules, payload.date)
    excluded_block_id = payload.original_block_id if payload.override_type == ScheduleOverrideType.reschedule else None
    for item in agenda:
        if excluded_block_id is not None and item.block_id == excluded_block_id:
            continue
        if item.start_time < payload.end_time and item.end_time > payload.start_time:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Schedule override overlaps with {item.subject_name} "
                    f"from {_format_time(item.start_time)} to {_format_time(item.end_time)}"
                ),
            )


def _schedule_read_access(auth: AuthSession, student_id: int, *, action: str) -> None:
    ensure_student_scope(auth, student_id, action=action)


@router.get('/{student_id}/agenda', response_model=DailyAgendaRead)
async def get_daily_agenda(
    student_id: int,
    date_value: date = Query(..., alias='date'),
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.read_curriculum, action='view schedules')),
) -> DailyAgendaRead:
    student = await _get_student_or_404(db, student_id, auth.family_id)
    _schedule_read_access(auth, student.id, action='view daily agenda')
    schedules = await _get_student_schedules_for_date(db, family_id=auth.family_id, student_id=student.id, target_date=date_value)
    return DailyAgendaRead(student_id=student.id, date=date_value, items=_build_daily_agenda_entries(schedules, date_value))


@router.get('/{student_id}/week', response_model=WeeklyAgendaRead)
async def get_weekly_agenda(
    student_id: int,
    date_value: date = Query(..., alias='date'),
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.read_curriculum, action='view schedules')),
) -> WeeklyAgendaRead:
    student = await _get_student_or_404(db, student_id, auth.family_id)
    _schedule_read_access(auth, student.id, action='view weekly agenda')
    week_start = date_value - timedelta(days=date_value.weekday())
    days: list[DailyAgendaRead] = []
    for offset in range(7):
        current_date = week_start + timedelta(days=offset)
        schedules = await _get_student_schedules_for_date(
            db,
            family_id=auth.family_id,
            student_id=student.id,
            target_date=current_date,
        )
        days.append(DailyAgendaRead(student_id=student.id, date=current_date, items=_build_daily_agenda_entries(schedules, current_date)))
    return WeeklyAgendaRead(student_id=student.id, week_start=week_start, week_end=week_start + timedelta(days=6), days=days)


@router.get('', response_model=list[ScheduleRead])
async def list_schedules(
    student_id: int | None = Query(default=None, ge=1),
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.read_curriculum, action='view schedules')),
) -> list[Schedule]:
    stmt = select(Schedule).options(selectinload(Schedule.student), selectinload(Schedule.school_year)).where(Schedule.family_id == auth.family_id)
    if student_id is not None:
        student = await _get_student_or_404(db, student_id, auth.family_id)
        _schedule_read_access(auth, student.id, action='view schedules')
        stmt = stmt.where(Schedule.student_id == student.id)
    elif auth.role == 'student_viewer' and auth.student_id is not None:
        stmt = stmt.where(Schedule.student_id == auth.student_id)
    stmt = stmt.order_by(Schedule.student_id, Schedule.name)
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.post('', response_model=ScheduleRead, status_code=status.HTTP_201_CREATED)
async def create_schedule(
    payload: ScheduleCreate,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.manage_curriculum, action='manage schedules')),
) -> Schedule:
    await _get_student_or_404(db, payload.student_id, auth.family_id)
    await _get_school_year_or_404(db, payload.school_year_id, auth.family_id)
    await _ensure_unique_schedule_name(
        db,
        family_id=auth.family_id,
        student_id=payload.student_id,
        school_year_id=payload.school_year_id,
        name=payload.name,
    )
    schedule = Schedule(
        family_id=auth.family_id,
        student_id=payload.student_id,
        school_year_id=payload.school_year_id,
        name=payload.name,
    )
    db.add(schedule)
    await db.commit()
    return await _get_schedule_or_404(db, schedule.id, auth.family_id)


@router.get('/{schedule_id}', response_model=ScheduleDetail)
async def get_schedule(
    schedule_id: int,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.read_curriculum, action='view schedules')),
) -> Schedule:
    schedule = await _get_schedule_or_404(db, schedule_id, auth.family_id)
    _schedule_read_access(auth, schedule.student_id, action='view schedules')
    return schedule


@router.put('/{schedule_id}', response_model=ScheduleRead)
async def update_schedule(
    schedule_id: int,
    payload: ScheduleUpdate,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.manage_curriculum, action='manage schedules')),
) -> Schedule:
    schedule = await _get_schedule_or_404(db, schedule_id, auth.family_id)
    await _get_student_or_404(db, payload.student_id, auth.family_id)
    await _get_school_year_or_404(db, payload.school_year_id, auth.family_id)
    await _ensure_unique_schedule_name(
        db,
        family_id=auth.family_id,
        student_id=payload.student_id,
        school_year_id=payload.school_year_id,
        name=payload.name,
        current_schedule_id=schedule_id,
    )
    schedule.student_id = payload.student_id
    schedule.school_year_id = payload.school_year_id
    schedule.name = payload.name
    await db.commit()
    return await _get_schedule_or_404(db, schedule.id, auth.family_id)


@router.delete('/{schedule_id}', status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_schedule(
    schedule_id: int,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.manage_curriculum, action='manage schedules')),
) -> Response:
    schedule = await _get_schedule_or_404(db, schedule_id, auth.family_id)
    await db.delete(schedule)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get('/{schedule_id}/blocks', response_model=list[ScheduleBlockRead])
async def list_schedule_blocks(
    schedule_id: int,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.read_curriculum, action='view schedules')),
) -> list[ScheduleBlock]:
    schedule = await _get_schedule_or_404(db, schedule_id, auth.family_id)
    _schedule_read_access(auth, schedule.student_id, action='view schedules')
    return schedule.blocks


@router.post('/{schedule_id}/blocks', response_model=ScheduleBlockRead, status_code=status.HTTP_201_CREATED)
async def create_schedule_block(
    schedule_id: int,
    payload: ScheduleBlockCreate,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.manage_curriculum, action='manage schedules')),
) -> ScheduleBlock:
    schedule = await _get_schedule_or_404(db, schedule_id, auth.family_id)
    await _get_subject_or_404(db, payload.subject_id, auth.family_id)
    await _ensure_block_no_conflicts(
        db,
        schedule=schedule,
        day_of_week=payload.day_of_week,
        start_time=payload.start_time,
        end_time=payload.end_time,
    )
    block = ScheduleBlock(
        schedule_id=schedule.id,
        subject_id=payload.subject_id,
        day_of_week=payload.day_of_week,
        start_time=payload.start_time,
        end_time=payload.end_time,
        location=payload.location,
        notes=payload.notes,
    )
    db.add(block)
    await db.commit()
    return await _get_block_or_404(db, block.id, auth.family_id)


@router.put('/blocks/{block_id}', response_model=ScheduleBlockRead)
async def update_schedule_block(
    block_id: int,
    payload: ScheduleBlockUpdate,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.manage_curriculum, action='manage schedules')),
) -> ScheduleBlock:
    block = await _get_block_or_404(db, block_id, auth.family_id)
    await _get_subject_or_404(db, payload.subject_id, auth.family_id)
    schedule = await _get_schedule_or_404(db, block.schedule_id, auth.family_id)
    await _ensure_block_no_conflicts(
        db,
        schedule=schedule,
        day_of_week=payload.day_of_week,
        start_time=payload.start_time,
        end_time=payload.end_time,
        current_block_id=block.id,
    )
    block.subject_id = payload.subject_id
    block.day_of_week = payload.day_of_week
    block.start_time = payload.start_time
    block.end_time = payload.end_time
    block.location = payload.location
    block.notes = payload.notes
    await db.commit()
    return await _get_block_or_404(db, block.id, auth.family_id)


@router.delete('/blocks/{block_id}', status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_schedule_block(
    block_id: int,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.manage_curriculum, action='manage schedules')),
) -> Response:
    block = await _get_block_or_404(db, block_id, auth.family_id)
    await db.delete(block)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post('/override', response_model=ScheduleOverrideRead, status_code=status.HTTP_201_CREATED)
async def create_schedule_override(
    payload: ScheduleOverrideCreate,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.manage_curriculum, action='manage schedules')),
) -> ScheduleOverride:
    schedule = await _get_schedule_or_404(db, payload.schedule_id, auth.family_id)
    original_block = await _ensure_override_block_belongs_to_schedule(
        db,
        schedule=schedule,
        original_block_id=payload.original_block_id,
    )
    if payload.subject_id is not None:
        await _get_subject_or_404(db, payload.subject_id, auth.family_id)
    elif payload.override_type == ScheduleOverrideType.reschedule and original_block is not None:
        payload.subject_id = original_block.subject_id
    _ensure_override_in_school_year(schedule, payload.date)
    await _ensure_override_no_duplicates(
        db,
        schedule_id=schedule.id,
        date_value=payload.date,
        original_block_id=payload.original_block_id,
    )
    await _ensure_override_no_conflicts(db, schedule=schedule, payload=payload)
    override = ScheduleOverride(
        schedule_id=schedule.id,
        date=payload.date,
        original_block_id=payload.original_block_id,
        override_type=payload.override_type,
        subject_id=payload.subject_id,
        start_time=payload.start_time,
        end_time=payload.end_time,
        reason=payload.reason,
    )
    db.add(override)
    await db.commit()
    return await _get_override_or_404(db, override.id, auth.family_id)


@router.delete('/override/{override_id}', status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_schedule_override(
    override_id: int,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.manage_curriculum, action='manage schedules')),
) -> Response:
    override = await _get_override_or_404(db, override_id, auth.family_id)
    await db.delete(override)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
