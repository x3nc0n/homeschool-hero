from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.database import get_db
from backend.models.calendar import CalendarEvent, GradingPeriod, SchoolYear, Term
from backend.schemas.calendar import (
    CalendarEventBulkCreate,
    CalendarEventCreate,
    CalendarEventRead,
    CalendarEventUpdate,
    GradingPeriodCreate,
    GradingPeriodRead,
    GradingPeriodUpdate,
    HolidayPresetRead,
    InstructionalDayCount,
    SchoolYearCreate,
    SchoolYearDetail,
    SchoolYearRead,
    SchoolYearTemplateRead,
    SchoolYearUpdate,
    SchoolYearWizardCreate,
    TermBulkCreate,
    TermCreate,
    TermRead,
    TermUpdate,
)
from backend.security import AuthSession, get_family_record
from backend.services.authorization import Capability, require_capabilities
from backend.services.school_year_wizard import (
    expand_break,
    expand_selected_holidays,
    generate_terms,
    get_school_year_templates,
    get_selectable_holiday_presets,
)

router = APIRouter(prefix='/calendar', tags=['calendar'])
wizard_router = APIRouter(prefix='/school-years/wizard', tags=['school-year-wizard'])


def _school_year_options():
    return (
        selectinload(SchoolYear.terms).selectinload(Term.grading_periods),
        selectinload(SchoolYear.calendar_events),
    )


async def _get_school_year_or_404(db: AsyncSession, school_year_id: int, family_id: int) -> SchoolYear:
    school_year = await get_family_record(db, SchoolYear, school_year_id, family_id, options=_school_year_options())
    if not school_year:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='School year not found')
    return school_year


async def _get_term_or_404(db: AsyncSession, term_id: int, family_id: int) -> Term:
    term = await get_family_record(
        db,
        Term,
        term_id,
        family_id,
        options=(selectinload(Term.grading_periods), selectinload(Term.school_year)),
    )
    if not term:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Term not found')
    return term


async def _get_grading_period_or_404(db: AsyncSession, grading_period_id: int, family_id: int) -> GradingPeriod:
    grading_period = await get_family_record(
        db,
        GradingPeriod,
        grading_period_id,
        family_id,
        options=(selectinload(GradingPeriod.term).selectinload(Term.school_year),),
    )
    if not grading_period:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Grading period not found')
    return grading_period


async def _get_event_or_404(db: AsyncSession, event_id: int, family_id: int) -> CalendarEvent:
    event = await get_family_record(db, CalendarEvent, event_id, family_id)
    if not event:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Calendar event not found')
    return event


def _ensure_date_range(name: str, start_date: date, end_date: date) -> None:
    if start_date > end_date:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f'{name} start_date must be on or before end_date')


def _ensure_within_range(
    *,
    name: str,
    start_date: date,
    end_date: date,
    parent_name: str,
    parent_start: date,
    parent_end: date,
) -> None:
    if start_date < parent_start or end_date > parent_end:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f'{name} dates must fall within the {parent_name} date range',
        )


def _ensure_bulk_school_year_match(resource_name: str, path_school_year_id: int, payload_school_year_id: int) -> None:
    if payload_school_year_id != path_school_year_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f'{resource_name} school_year_id must match the school year in the URL',
        )


def _ensure_calendar_event_within_school_year(event_date: date, school_year: SchoolYear) -> None:
    if event_date < school_year.start_date or event_date > school_year.end_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Calendar event dates must fall within the school year date range',
        )


def _term_ranges_overlap(start_date: date, end_date: date, other_start: date, other_end: date) -> bool:
    return other_start <= end_date and other_end >= start_date


async def _ensure_school_year_active_state(db: AsyncSession, family_id: int, school_year: SchoolYear) -> None:
    if not school_year.is_active:
        return
    result = await db.execute(
        select(SchoolYear).where(SchoolYear.family_id == family_id, SchoolYear.id != school_year.id, SchoolYear.is_active.is_(True))
    )
    for other in result.scalars().all():
        other.is_active = False


async def _ensure_term_unique_name(
    db: AsyncSession,
    *,
    family_id: int,
    school_year_id: int,
    name: str,
    current_term_id: int | None = None,
) -> None:
    stmt = select(Term).where(Term.family_id == family_id, Term.school_year_id == school_year_id, Term.name == name)
    if current_term_id is not None:
        stmt = stmt.where(Term.id != current_term_id)
    if (await db.execute(stmt)).scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='Term already exists')


async def _ensure_term_no_overlap(
    db: AsyncSession,
    *,
    family_id: int,
    school_year_id: int,
    start_date: date,
    end_date: date,
    current_term_id: int | None = None,
) -> None:
    stmt = select(Term).where(
        Term.family_id == family_id,
        Term.school_year_id == school_year_id,
        Term.start_date <= end_date,
        Term.end_date >= start_date,
    )
    if current_term_id is not None:
        stmt = stmt.where(Term.id != current_term_id)
    if (await db.execute(stmt)).scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='Term dates overlap an existing term')


async def _ensure_grading_period_unique_name(
    db: AsyncSession,
    *,
    family_id: int,
    term_id: int,
    name: str,
    current_id: int | None = None,
) -> None:
    stmt = select(GradingPeriod).where(
        GradingPeriod.family_id == family_id,
        GradingPeriod.term_id == term_id,
        GradingPeriod.name == name,
    )
    if current_id is not None:
        stmt = stmt.where(GradingPeriod.id != current_id)
    if (await db.execute(stmt)).scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='Grading period already exists')


def _calculate_instructional_day_count(school_year: SchoolYear) -> InstructionalDayCount:
    event_map: dict[date, bool] = {}
    for event in school_year.calendar_events:
        current = event_map.get(event.date)
        if current is True:
            continue
        event_map[event.date] = event.is_instructional_day

    weekday_days = 0
    instructional_days = 0
    current_day = school_year.start_date
    while current_day <= school_year.end_date:
        default_instructional = current_day.weekday() < 5
        if default_instructional:
            weekday_days += 1
        if event_map.get(current_day, default_instructional):
            instructional_days += 1
        current_day += timedelta(days=1)

    non_instructional_overrides = sum(1 for day, instructional in event_map.items() if not instructional and day.weekday() < 5)
    instructional_overrides = sum(1 for day, instructional in event_map.items() if instructional and day.weekday() >= 5)

    return InstructionalDayCount(
        school_year_id=school_year.id,
        instructional_days=instructional_days,
        weekday_days=weekday_days,
        non_instructional_overrides=non_instructional_overrides,
        instructional_overrides=instructional_overrides,
    )


@wizard_router.get('/holidays', response_model=list[HolidayPresetRead])
async def list_school_year_wizard_holidays(
    year: int = Query(..., ge=2024, le=2030),
    auth: AuthSession = Depends(require_capabilities(Capability.manage_curriculum, action='manage school year setup wizard')),
) -> list[dict]:
    del auth
    return get_selectable_holiday_presets(year)


@wizard_router.get('/templates', response_model=list[SchoolYearTemplateRead])
async def list_school_year_wizard_templates(
    auth: AuthSession = Depends(require_capabilities(Capability.manage_curriculum, action='manage school year setup wizard')),
) -> list[dict]:
    del auth
    return get_school_year_templates()


@wizard_router.post('', response_model=SchoolYearDetail, status_code=status.HTTP_201_CREATED)
async def create_school_year_from_wizard(
    payload: SchoolYearWizardCreate,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.manage_curriculum, action='manage school year setup wizard')),
) -> SchoolYear:
    existing = await db.execute(
        select(SchoolYear).where(SchoolYear.family_id == auth.family_id, SchoolYear.name == payload.name.strip())
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='School year already exists')

    school_year = SchoolYear(
        family_id=auth.family_id,
        name=payload.name.strip(),
        start_date=payload.start_date,
        end_date=payload.end_date,
        is_active=payload.is_active,
    )
    db.add(school_year)
    await db.flush()

    term_rows = generate_terms(
        start_date=payload.start_date,
        end_date=payload.end_date,
        term_structure=payload.term_structure,
    )
    for term_row in term_rows:
        db.add(
            Term(
                family_id=auth.family_id,
                school_year_id=school_year.id,
                name=term_row['name'],
                start_date=term_row['start_date'],
                end_date=term_row['end_date'],
                term_type=term_row['term_type'],
            )
        )

    try:
        generated_events = expand_selected_holidays(payload.holidays, payload.start_date, payload.end_date)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    for custom_break in payload.custom_breaks:
        _ensure_within_range(
            name='Custom break',
            start_date=custom_break.start_date,
            end_date=custom_break.end_date,
            parent_name='school year',
            parent_start=payload.start_date,
            parent_end=payload.end_date,
        )
        generated_events.extend(expand_break(custom_break.name, custom_break.start_date, custom_break.end_date))

    seen_events: set[tuple[date, str]] = set()
    for event in sorted(generated_events, key=lambda item: (item['date'], item['name'])):
        event_key = (event['date'], event['name'])
        if event_key in seen_events:
            continue
        seen_events.add(event_key)
        db.add(
            CalendarEvent(
                family_id=auth.family_id,
                school_year_id=school_year.id,
                date=event['date'],
                event_type=event['event_type'],
                name=event['name'],
                is_instructional_day=event['is_instructional_day'],
                notes=event['notes'],
            )
        )

    await _ensure_school_year_active_state(db, auth.family_id, school_year)
    await db.commit()
    return await _get_school_year_or_404(db, school_year.id, auth.family_id)


@router.get('/school-years', response_model=list[SchoolYearRead])
async def list_school_years(
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.read_curriculum, action='view academic calendar')),
) -> list[SchoolYear]:
    result = await db.execute(select(SchoolYear).where(SchoolYear.family_id == auth.family_id).order_by(SchoolYear.start_date))
    return list(result.scalars().all())


@router.post('/school-years', response_model=SchoolYearRead, status_code=status.HTTP_201_CREATED)
async def create_school_year(
    payload: SchoolYearCreate,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.manage_curriculum, action='manage academic calendar')),
) -> SchoolYear:
    existing = await db.execute(
        select(SchoolYear).where(SchoolYear.family_id == auth.family_id, SchoolYear.name == payload.name.strip())
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='School year already exists')

    school_year = SchoolYear(
        family_id=auth.family_id,
        name=payload.name.strip(),
        start_date=payload.start_date,
        end_date=payload.end_date,
        is_active=payload.is_active,
    )
    db.add(school_year)
    await db.flush()
    await _ensure_school_year_active_state(db, auth.family_id, school_year)
    await db.commit()
    await db.refresh(school_year)
    return school_year


@router.get('/school-years/{school_year_id}', response_model=SchoolYearDetail)
async def get_school_year(
    school_year_id: int,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.read_curriculum, action='view academic calendar')),
) -> SchoolYear:
    return await _get_school_year_or_404(db, school_year_id, auth.family_id)


@router.put('/school-years/{school_year_id}', response_model=SchoolYearRead)
async def update_school_year(
    school_year_id: int,
    payload: SchoolYearUpdate,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.manage_curriculum, action='manage academic calendar')),
) -> SchoolYear:
    school_year = await _get_school_year_or_404(db, school_year_id, auth.family_id)
    existing = await db.execute(
        select(SchoolYear).where(
            SchoolYear.family_id == auth.family_id,
            SchoolYear.name == payload.name.strip(),
            SchoolYear.id != school_year_id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='School year already exists')

    school_year.name = payload.name.strip()
    school_year.start_date = payload.start_date
    school_year.end_date = payload.end_date
    school_year.is_active = payload.is_active

    for term in school_year.terms:
        _ensure_within_range(
            name='Term',
            start_date=term.start_date,
            end_date=term.end_date,
            parent_name='school year',
            parent_start=school_year.start_date,
            parent_end=school_year.end_date,
        )
    for event in school_year.calendar_events:
        _ensure_calendar_event_within_school_year(event.date, school_year)

    await _ensure_school_year_active_state(db, auth.family_id, school_year)
    await db.commit()
    await db.refresh(school_year)
    return school_year


@router.delete('/school-years/{school_year_id}', status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_school_year(
    school_year_id: int,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.manage_curriculum, action='manage academic calendar')),
) -> None:
    school_year = await _get_school_year_or_404(db, school_year_id, auth.family_id)
    await db.delete(school_year)
    await db.commit()


@router.get('/terms', response_model=list[TermRead])
async def list_terms(
    school_year_id: int = Query(..., ge=1),
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.read_curriculum, action='view academic calendar')),
) -> list[Term]:
    await _get_school_year_or_404(db, school_year_id, auth.family_id)
    result = await db.execute(
        select(Term)
        .options(selectinload(Term.grading_periods))
        .where(Term.family_id == auth.family_id, Term.school_year_id == school_year_id)
        .order_by(Term.start_date)
    )
    return list(result.scalars().all())


@router.post('/terms', response_model=TermRead, status_code=status.HTTP_201_CREATED)
async def create_term(
    payload: TermCreate,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.manage_curriculum, action='manage academic calendar')),
) -> Term:
    school_year = await _get_school_year_or_404(db, payload.school_year_id, auth.family_id)
    _ensure_within_range(
        name='Term',
        start_date=payload.start_date,
        end_date=payload.end_date,
        parent_name='school year',
        parent_start=school_year.start_date,
        parent_end=school_year.end_date,
    )
    await _ensure_term_unique_name(
        db,
        family_id=auth.family_id,
        school_year_id=school_year.id,
        name=payload.name.strip(),
    )
    await _ensure_term_no_overlap(
        db,
        family_id=auth.family_id,
        school_year_id=school_year.id,
        start_date=payload.start_date,
        end_date=payload.end_date,
    )

    term = Term(
        family_id=auth.family_id,
        school_year_id=school_year.id,
        name=payload.name.strip(),
        start_date=payload.start_date,
        end_date=payload.end_date,
        term_type=payload.term_type,
    )
    db.add(term)
    await db.commit()
    await db.refresh(term)
    return await _get_term_or_404(db, term.id, auth.family_id)


@router.post('/school-years/{school_year_id}/terms/bulk', response_model=list[TermRead], status_code=status.HTTP_201_CREATED)
async def bulk_create_terms(
    school_year_id: int,
    payload: TermBulkCreate,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.manage_curriculum, action='manage academic calendar')),
) -> list[Term]:
    school_year = await _get_school_year_or_404(db, school_year_id, auth.family_id)
    existing_names = {term.name for term in school_year.terms}
    existing_ranges = [(term.start_date, term.end_date) for term in school_year.terms]
    created_terms: list[Term] = []
    pending_names: set[str] = set()
    pending_ranges: list[tuple[date, date]] = []

    for item in payload.root:
        _ensure_bulk_school_year_match('Term', school_year_id, item.school_year_id)
        normalized_name = item.name.strip()
        if normalized_name in existing_names or normalized_name in pending_names:
            continue
        _ensure_within_range(
            name='Term',
            start_date=item.start_date,
            end_date=item.end_date,
            parent_name='school year',
            parent_start=school_year.start_date,
            parent_end=school_year.end_date,
        )
        for range_start, range_end in [*existing_ranges, *pending_ranges]:
            if _term_ranges_overlap(item.start_date, item.end_date, range_start, range_end):
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='Term dates overlap an existing term')

        created_terms.append(
            Term(
                family_id=auth.family_id,
                school_year_id=school_year.id,
                name=normalized_name,
                start_date=item.start_date,
                end_date=item.end_date,
                term_type=item.term_type,
            )
        )
        pending_names.add(normalized_name)
        pending_ranges.append((item.start_date, item.end_date))

    if not created_terms:
        return []

    db.add_all(created_terms)
    await db.flush()
    created_ids = [term.id for term in created_terms]
    await db.commit()
    result = await db.execute(
        select(Term)
        .options(selectinload(Term.grading_periods))
        .where(Term.family_id == auth.family_id, Term.id.in_(created_ids))
        .order_by(Term.start_date, Term.name)
    )
    return list(result.scalars().all())


@router.get('/terms/{term_id}', response_model=TermRead)
async def get_term(
    term_id: int,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.read_curriculum, action='view academic calendar')),
) -> Term:
    return await _get_term_or_404(db, term_id, auth.family_id)


@router.put('/terms/{term_id}', response_model=TermRead)
async def update_term(
    term_id: int,
    payload: TermUpdate,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.manage_curriculum, action='manage academic calendar')),
) -> Term:
    term = await _get_term_or_404(db, term_id, auth.family_id)
    school_year = await _get_school_year_or_404(db, term.school_year_id, auth.family_id)
    _ensure_within_range(
        name='Term',
        start_date=payload.start_date,
        end_date=payload.end_date,
        parent_name='school year',
        parent_start=school_year.start_date,
        parent_end=school_year.end_date,
    )
    await _ensure_term_unique_name(
        db,
        family_id=auth.family_id,
        school_year_id=school_year.id,
        name=payload.name.strip(),
        current_term_id=term.id,
    )
    await _ensure_term_no_overlap(
        db,
        family_id=auth.family_id,
        school_year_id=school_year.id,
        start_date=payload.start_date,
        end_date=payload.end_date,
        current_term_id=term.id,
    )

    term.name = payload.name.strip()
    term.start_date = payload.start_date
    term.end_date = payload.end_date
    term.term_type = payload.term_type

    for grading_period in term.grading_periods:
        _ensure_within_range(
            name='Grading period',
            start_date=grading_period.start_date,
            end_date=grading_period.end_date,
            parent_name='term',
            parent_start=term.start_date,
            parent_end=term.end_date,
        )

    await db.commit()
    return await _get_term_or_404(db, term.id, auth.family_id)


@router.delete('/terms/{term_id}', status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_term(
    term_id: int,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.manage_curriculum, action='manage academic calendar')),
) -> None:
    term = await _get_term_or_404(db, term_id, auth.family_id)
    await db.delete(term)
    await db.commit()


@router.get('/grading-periods', response_model=list[GradingPeriodRead])
async def list_grading_periods(
    term_id: int = Query(..., ge=1),
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.read_curriculum, action='view academic calendar')),
) -> list[GradingPeriod]:
    await _get_term_or_404(db, term_id, auth.family_id)
    result = await db.execute(
        select(GradingPeriod)
        .where(GradingPeriod.family_id == auth.family_id, GradingPeriod.term_id == term_id)
        .order_by(GradingPeriod.start_date)
    )
    return list(result.scalars().all())


@router.post('/grading-periods', response_model=GradingPeriodRead, status_code=status.HTTP_201_CREATED)
async def create_grading_period(
    payload: GradingPeriodCreate,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.manage_curriculum, action='manage academic calendar')),
) -> GradingPeriod:
    term = await _get_term_or_404(db, payload.term_id, auth.family_id)
    _ensure_within_range(
        name='Grading period',
        start_date=payload.start_date,
        end_date=payload.end_date,
        parent_name='term',
        parent_start=term.start_date,
        parent_end=term.end_date,
    )
    await _ensure_grading_period_unique_name(
        db,
        family_id=auth.family_id,
        term_id=term.id,
        name=payload.name.strip(),
    )

    grading_period = GradingPeriod(
        family_id=auth.family_id,
        term_id=term.id,
        name=payload.name.strip(),
        start_date=payload.start_date,
        end_date=payload.end_date,
    )
    db.add(grading_period)
    await db.commit()
    await db.refresh(grading_period)
    return grading_period


@router.get('/grading-periods/{grading_period_id}', response_model=GradingPeriodRead)
async def get_grading_period(
    grading_period_id: int,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.read_curriculum, action='view academic calendar')),
) -> GradingPeriod:
    return await _get_grading_period_or_404(db, grading_period_id, auth.family_id)


@router.put('/grading-periods/{grading_period_id}', response_model=GradingPeriodRead)
async def update_grading_period(
    grading_period_id: int,
    payload: GradingPeriodUpdate,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.manage_curriculum, action='manage academic calendar')),
) -> GradingPeriod:
    grading_period = await _get_grading_period_or_404(db, grading_period_id, auth.family_id)
    term = await _get_term_or_404(db, grading_period.term_id, auth.family_id)
    _ensure_within_range(
        name='Grading period',
        start_date=payload.start_date,
        end_date=payload.end_date,
        parent_name='term',
        parent_start=term.start_date,
        parent_end=term.end_date,
    )
    await _ensure_grading_period_unique_name(
        db,
        family_id=auth.family_id,
        term_id=term.id,
        name=payload.name.strip(),
        current_id=grading_period.id,
    )
    grading_period.name = payload.name.strip()
    grading_period.start_date = payload.start_date
    grading_period.end_date = payload.end_date
    await db.commit()
    await db.refresh(grading_period)
    return grading_period


@router.delete('/grading-periods/{grading_period_id}', status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_grading_period(
    grading_period_id: int,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.manage_curriculum, action='manage academic calendar')),
) -> None:
    grading_period = await _get_grading_period_or_404(db, grading_period_id, auth.family_id)
    await db.delete(grading_period)
    await db.commit()


@router.get('/events', response_model=list[CalendarEventRead])
async def list_calendar_events(
    school_year_id: int = Query(..., ge=1),
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.read_curriculum, action='view academic calendar')),
) -> list[CalendarEvent]:
    await _get_school_year_or_404(db, school_year_id, auth.family_id)
    result = await db.execute(
        select(CalendarEvent)
        .where(CalendarEvent.family_id == auth.family_id, CalendarEvent.school_year_id == school_year_id)
        .order_by(CalendarEvent.date, CalendarEvent.name)
    )
    return list(result.scalars().all())


@router.post('/events', response_model=CalendarEventRead, status_code=status.HTTP_201_CREATED)
async def create_calendar_event(
    payload: CalendarEventCreate,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.manage_curriculum, action='manage academic calendar')),
) -> CalendarEvent:
    school_year = await _get_school_year_or_404(db, payload.school_year_id, auth.family_id)
    _ensure_calendar_event_within_school_year(payload.date, school_year)
    event = CalendarEvent(
        family_id=auth.family_id,
        school_year_id=school_year.id,
        date=payload.date,
        event_type=payload.event_type,
        name=payload.name.strip(),
        is_instructional_day=payload.is_instructional_day,
        notes=payload.notes.strip() if payload.notes else None,
    )
    db.add(event)
    await db.commit()
    await db.refresh(event)
    return event


@router.post('/school-years/{school_year_id}/events/bulk', response_model=list[CalendarEventRead], status_code=status.HTTP_201_CREATED)
async def bulk_create_calendar_events(
    school_year_id: int,
    payload: CalendarEventBulkCreate,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.manage_curriculum, action='manage academic calendar')),
) -> list[CalendarEvent]:
    school_year = await _get_school_year_or_404(db, school_year_id, auth.family_id)
    existing_keys = {(event.date, event.name) for event in school_year.calendar_events}
    created_events: list[CalendarEvent] = []
    pending_keys: set[tuple[date, str]] = set()

    for item in payload.root:
        _ensure_bulk_school_year_match('Calendar event', school_year_id, item.school_year_id)
        _ensure_calendar_event_within_school_year(item.date, school_year)
        normalized_name = item.name.strip()
        event_key = (item.date, normalized_name)
        if event_key in existing_keys or event_key in pending_keys:
            continue
        created_events.append(
            CalendarEvent(
                family_id=auth.family_id,
                school_year_id=school_year.id,
                date=item.date,
                event_type=item.event_type,
                name=normalized_name,
                is_instructional_day=item.is_instructional_day,
                notes=item.notes.strip() if item.notes else None,
            )
        )
        pending_keys.add(event_key)

    if not created_events:
        return []

    db.add_all(created_events)
    await db.flush()
    created_ids = [event.id for event in created_events]
    await db.commit()
    result = await db.execute(
        select(CalendarEvent)
        .where(CalendarEvent.family_id == auth.family_id, CalendarEvent.id.in_(created_ids))
        .order_by(CalendarEvent.date, CalendarEvent.name)
    )
    return list(result.scalars().all())


@router.get('/events/{event_id}', response_model=CalendarEventRead)
async def get_calendar_event(
    event_id: int,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.read_curriculum, action='view academic calendar')),
) -> CalendarEvent:
    return await _get_event_or_404(db, event_id, auth.family_id)


@router.put('/events/{event_id}', response_model=CalendarEventRead)
async def update_calendar_event(
    event_id: int,
    payload: CalendarEventUpdate,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.manage_curriculum, action='manage academic calendar')),
) -> CalendarEvent:
    event = await _get_event_or_404(db, event_id, auth.family_id)
    school_year = await _get_school_year_or_404(db, event.school_year_id, auth.family_id)
    _ensure_calendar_event_within_school_year(payload.date, school_year)
    event.date = payload.date
    event.event_type = payload.event_type
    event.name = payload.name.strip()
    event.is_instructional_day = payload.is_instructional_day
    event.notes = payload.notes.strip() if payload.notes else None
    await db.commit()
    await db.refresh(event)
    return event


@router.delete('/events/{event_id}', status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_calendar_event(
    event_id: int,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.manage_curriculum, action='manage academic calendar')),
) -> None:
    event = await _get_event_or_404(db, event_id, auth.family_id)
    await db.delete(event)
    await db.commit()


@router.get('/active', response_model=SchoolYearDetail)
async def get_active_school_year(
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.read_curriculum, action='view academic calendar')),
) -> SchoolYear:
    result = await db.execute(
        select(SchoolYear)
        .options(*_school_year_options())
        .where(SchoolYear.family_id == auth.family_id, SchoolYear.is_active.is_(True))
        .order_by(SchoolYear.start_date.desc())
    )
    school_year = result.scalars().first()
    if not school_year:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='No active school year found')
    return school_year


@router.get('/{school_year_id}/days', response_model=InstructionalDayCount)
async def get_instructional_day_count(
    school_year_id: int,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.read_curriculum, action='view academic calendar')),
) -> InstructionalDayCount:
    school_year = await _get_school_year_or_404(db, school_year_id, auth.family_id)
    return _calculate_instructional_day_count(school_year)
