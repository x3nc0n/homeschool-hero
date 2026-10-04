from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from datetime import date, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.database import get_db
from backend.models import (
    AttendanceRecord,
    AuditAction,
    SchoolYear,
    Student,
    Term,
)
from backend.schemas.attendance import (
    AttendanceDailyUpsert,
    AttendanceHoursLog,
    AttendanceHoursResponse,
    AttendanceRecordEntry,
    AttendanceRecordRead,
    AttendanceStateProfileProgress,
    AttendanceStateProfileRead,
    AttendanceSummaryBucket,
    AttendanceSummaryResponse,
)
from backend.security import AuthSession, get_family_record
from backend.services.audit import log_event
from backend.services.attendance_profiles import (
    get_state_requirement_profile,
    list_state_requirement_profiles,
)
from backend.services.authorization import Capability, ensure_student_scope, get_student_scope_id, require_capabilities
from backend.services.cache import invalidate_compliance_cache
from backend.services.compliance import get_family_state_code

router = APIRouter(prefix='/attendance', tags=['attendance'])


def _record_options():
    return (selectinload(AttendanceRecord.student),)


async def _get_student_or_404(db: AsyncSession, student_id: int, family_id: int) -> Student:
    student = await get_family_record(db, Student, student_id, family_id)
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Student not found')
    return student


async def _get_record_or_404(db: AsyncSession, record_id: int, family_id: int) -> AttendanceRecord:
    record = await get_family_record(db, AttendanceRecord, record_id, family_id, options=_record_options())
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Attendance record not found')
    return record


async def _resolve_school_year(
    db: AsyncSession,
    *,
    family_id: int,
    school_year_id: int | None = None,
    date_hint: date | None = None,
) -> SchoolYear | None:
    if school_year_id is not None:
        school_year = await get_family_record(
            db,
            SchoolYear,
            school_year_id,
            family_id,
            options=(selectinload(SchoolYear.terms),),
        )
        if not school_year:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='School year not found')
        return school_year

    active_stmt = (
        select(SchoolYear)
        .options(selectinload(SchoolYear.terms))
        .where(SchoolYear.family_id == family_id, SchoolYear.is_active.is_(True))
        .order_by(SchoolYear.start_date.desc())
    )
    active_school_year = (await db.execute(active_stmt)).scalars().first()
    if active_school_year:
        return active_school_year
    if date_hint is None:
        return None

    fallback_stmt = (
        select(SchoolYear)
        .options(selectinload(SchoolYear.terms))
        .where(SchoolYear.family_id == family_id, SchoolYear.start_date <= date_hint, SchoolYear.end_date >= date_hint)
        .order_by(SchoolYear.start_date.desc())
    )
    return (await db.execute(fallback_stmt)).scalars().first()


def _record_snapshot(record: AttendanceRecord) -> dict[str, object]:
    return {
        'id': record.id,
        'family_id': record.family_id,
        'student_id': record.student_id,
        'date': record.date.isoformat(),
        'is_instructional_day': record.is_instructional_day,
        'instructional_hours': str(record.instructional_hours) if record.instructional_hours is not None else None,
        'notes': record.notes,
    }


def _apply_record_entry(record: AttendanceRecord, payload: AttendanceRecordEntry, *, is_new: bool) -> None:
    if is_new or 'is_instructional_day' in payload.model_fields_set:
        record.is_instructional_day = payload.is_instructional_day
    if is_new or 'instructional_hours' in payload.model_fields_set:
        record.instructional_hours = payload.instructional_hours
    if is_new or 'notes' in payload.model_fields_set:
        record.notes = payload.notes


def _apply_hours_log(record: AttendanceRecord, payload: AttendanceHoursLog, *, is_new: bool) -> None:
    if is_new or payload.instructional_hours > 0:
        record.is_instructional_day = True
    record.instructional_hours = payload.instructional_hours
    record.notes = payload.notes


def _attendance_rate(*, instructional_days: int, total_records: int) -> float:
    if total_records == 0:
        return 0.0
    return round((instructional_days / total_records) * 100, 2)


def _sum_hours(records: Iterable[AttendanceRecord]) -> Decimal | None:
    hours = [record.instructional_hours for record in records if record.instructional_hours is not None]
    if not hours:
        return None
    return sum(hours, Decimal('0')).quantize(Decimal('0.01'))


def _bucket_from_records(
    label: str,
    *,
    start_date: date,
    end_date: date,
    records: list[AttendanceRecord],
) -> AttendanceSummaryBucket:
    instructional_days = sum(1 for record in records if record.is_instructional_day)
    total_records = len(records)
    return AttendanceSummaryBucket(
        label=label,
        start_date=start_date,
        end_date=end_date,
        total_records=total_records,
        instructional_days=instructional_days,
        non_instructional_days=total_records - instructional_days,
        attendance_rate=_attendance_rate(instructional_days=instructional_days, total_records=total_records),
        total_hours=_sum_hours(records),
    )


@router.get('', response_model=list[AttendanceRecordRead])
async def list_attendance_records(
    student_id: int | None = Query(default=None, ge=1),
    date_value: date | None = Query(default=None, alias='date'),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.read_students, action='view attendance')),
) -> list[AttendanceRecord]:
    scoped_student_id = student_id
    if auth.role == 'student_viewer':
        scoped_student_id = get_student_scope_id(auth)
    elif student_id is not None:
        await _get_student_or_404(db, student_id, auth.family_id)

    stmt = select(AttendanceRecord).options(*_record_options()).where(AttendanceRecord.family_id == auth.family_id)
    if scoped_student_id is not None:
        stmt = stmt.where(AttendanceRecord.student_id == scoped_student_id)
    if date_value is not None:
        stmt = stmt.where(AttendanceRecord.date == date_value)
    if date_from is not None:
        stmt = stmt.where(AttendanceRecord.date >= date_from)
    if date_to is not None:
        stmt = stmt.where(AttendanceRecord.date <= date_to)
    stmt = stmt.order_by(AttendanceRecord.date.desc(), AttendanceRecord.student_id.asc())
    return list((await db.execute(stmt)).scalars().all())


@router.get('/state-profiles', response_model=list[AttendanceStateProfileRead])
async def list_attendance_state_profiles(
    auth: AuthSession = Depends(require_capabilities(Capability.read_students, action='view attendance state profiles')),
) -> list[AttendanceStateProfileRead]:
    return list_state_requirement_profiles()


@router.post('/daily', response_model=list[AttendanceRecordRead], status_code=status.HTTP_201_CREATED)
async def record_daily_attendance(
    payload: AttendanceDailyUpsert,
    request: Request,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.manage_curriculum, action='manage attendance')),
) -> list[AttendanceRecord]:
    student_ids = [entry.student_id for entry in payload.records]
    students = (
        await db.execute(select(Student).where(Student.family_id == auth.family_id, Student.id.in_(student_ids)))
    ).scalars().all()
    if len(students) != len(student_ids):
        found_ids = {student.id for student in students}
        missing = next(student_id for student_id in student_ids if student_id not in found_ids)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f'Student {missing} not found')

    existing_records = (
        await db.execute(
            select(AttendanceRecord)
            .options(*_record_options())
            .where(
                AttendanceRecord.family_id == auth.family_id,
                AttendanceRecord.date == payload.date,
                AttendanceRecord.student_id.in_(student_ids),
            )
        )
    ).scalars().all()
    existing_by_student = {record.student_id: record for record in existing_records}

    updated_records: list[AttendanceRecord] = []
    for entry in payload.records:
        record = existing_by_student.get(entry.student_id)
        before = _record_snapshot(record) if record else None
        is_new = record is None
        if record is None:
            record = AttendanceRecord(
                family_id=auth.family_id,
                student_id=entry.student_id,
                date=payload.date,
                is_instructional_day=True,
            )
            db.add(record)
            await db.flush()
        _apply_record_entry(record, entry, is_new=is_new)
        await db.flush()
        await log_event(
            db,
            action=AuditAction.attendance_edit,
            actor=auth,
            family_id=auth.family_id,
            target_type='attendance_record',
            target_id=record.id,
            before=before,
            after=_record_snapshot(record),
            request=request,
        )
        updated_records.append(record)

    await db.commit()
    for student_id in student_ids:
        invalidate_compliance_cache(family_id=auth.family_id, student_id=student_id)
    return [await _get_record_or_404(db, record.id, auth.family_id) for record in updated_records]


@router.post('/hours', response_model=AttendanceRecordRead)
async def log_instructional_time(
    payload: AttendanceHoursLog,
    request: Request,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.manage_curriculum, action='manage attendance')),
) -> AttendanceRecord:
    await _get_student_or_404(db, payload.student_id, auth.family_id)
    stmt = (
        select(AttendanceRecord)
        .options(*_record_options())
        .where(
            AttendanceRecord.family_id == auth.family_id,
            AttendanceRecord.student_id == payload.student_id,
            AttendanceRecord.date == payload.date,
        )
    )
    record = (await db.execute(stmt)).scalar_one_or_none()
    before = _record_snapshot(record) if record else None
    is_new = record is None
    if record is None:
        record = AttendanceRecord(
            family_id=auth.family_id,
            student_id=payload.student_id,
            date=payload.date,
            is_instructional_day=True,
        )
        db.add(record)
        await db.flush()

    _apply_hours_log(record, payload, is_new=is_new)
    await db.flush()
    await log_event(
        db,
        action=AuditAction.attendance_edit,
        actor=auth,
        family_id=auth.family_id,
        target_type='attendance_record',
        target_id=record.id,
        before=before,
        after=_record_snapshot(record),
        request=request,
    )
    await db.commit()
    invalidate_compliance_cache(family_id=auth.family_id, student_id=payload.student_id)
    return await _get_record_or_404(db, record.id, auth.family_id)


@router.get('/summary', response_model=AttendanceSummaryResponse)
async def get_attendance_summary(
    student_id: int = Query(..., ge=1),
    period: str = Query(default='term', pattern='^(day|week|term|year)$'),
    school_year_id: int | None = Query(default=None, ge=1),
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.read_students, action='view attendance summaries')),
) -> AttendanceSummaryResponse:
    await _get_student_or_404(db, student_id, auth.family_id)
    ensure_student_scope(auth, student_id, action='view attendance summaries')
    school_year = await _resolve_school_year(db, family_id=auth.family_id, school_year_id=school_year_id)

    stmt = (
        select(AttendanceRecord)
        .where(AttendanceRecord.family_id == auth.family_id, AttendanceRecord.student_id == student_id)
        .order_by(AttendanceRecord.date.asc())
    )
    if school_year is not None:
        stmt = stmt.where(AttendanceRecord.date >= school_year.start_date, AttendanceRecord.date <= school_year.end_date)
    records = list((await db.execute(stmt)).scalars().all())

    if period == 'day':
        grouped: dict[tuple[date, date, str], list[AttendanceRecord]] = defaultdict(list)
        for record in records:
            grouped[(record.date, record.date, record.date.isoformat())].append(record)
    elif period == 'week':
        grouped = defaultdict(list)
        for record in records:
            start_date = record.date - timedelta(days=record.date.weekday())
            end_date = start_date + timedelta(days=6)
            grouped[(start_date, end_date, f'Week of {start_date.isoformat()}')].append(record)
    elif period == 'term':
        if school_year is None:
            school_year = await _resolve_school_year(
                db,
                family_id=auth.family_id,
                date_hint=records[-1].date if records else None,
            )
        grouped = defaultdict(list)
        if school_year is not None:
            term_records = [
                record
                for record in records
                if school_year.start_date <= record.date <= school_year.end_date
            ]
            for record in term_records:
                term = next(
                    (candidate for candidate in school_year.terms if candidate.start_date <= record.date <= candidate.end_date),
                    None,
                )
                if term is None:
                    grouped[(school_year.start_date, school_year.end_date, school_year.name)].append(record)
                else:
                    grouped[(term.start_date, term.end_date, term.name)].append(record)
            records = term_records
        else:
            grouped[(records[0].date, records[-1].date, 'All records')] = records if records else []
    else:
        grouped = defaultdict(list)
        if school_year is not None:
            grouped[(school_year.start_date, school_year.end_date, school_year.name)] = records
        else:
            school_years = (
                await db.execute(select(SchoolYear).where(SchoolYear.family_id == auth.family_id).order_by(SchoolYear.start_date.asc()))
            ).scalars().all()
            for record in records:
                record_school_year = next(
                    (candidate for candidate in school_years if candidate.start_date <= record.date <= candidate.end_date),
                    None,
                )
                if record_school_year is None:
                    start_date = date(record.date.year, 1, 1)
                    end_date = date(record.date.year, 12, 31)
                    label = str(record.date.year)
                else:
                    start_date = record_school_year.start_date
                    end_date = record_school_year.end_date
                    label = record_school_year.name
                grouped[(start_date, end_date, label)].append(record)

    buckets = [
        _bucket_from_records(label, start_date=start_date, end_date=end_date, records=bucket_records)
        for (start_date, end_date, label), bucket_records in sorted(grouped.items(), key=lambda item: item[0][0])
        if bucket_records
    ]
    total_records = sum(bucket.total_records for bucket in buckets)
    instructional_days = sum(bucket.instructional_days for bucket in buckets)
    non_instructional_days = sum(bucket.non_instructional_days for bucket in buckets)
    recorded_hours = [bucket.total_hours for bucket in buckets if bucket.total_hours is not None]
    total_hours = sum(recorded_hours, Decimal('0')).quantize(Decimal('0.01')) if recorded_hours else None
    state_code = await get_family_state_code(db, family_id=auth.family_id)
    state_profile = get_state_requirement_profile(state_code)
    state_profile_progress = None
    if (
        state_profile is not None
        and school_year is not None
        and (state_profile.required_days is not None or state_profile.required_hours is not None or state_profile.show_hours_ui)
    ):
        state_profile_progress = AttendanceStateProfileProgress(
            required_days=state_profile.required_days,
            days_remaining=(
                max(state_profile.required_days - instructional_days, 0)
                if state_profile.required_days is not None
                else None
            ),
            required_hours=state_profile.required_hours,
            hours_remaining=(
                max(Decimal(state_profile.required_hours) - (total_hours or Decimal('0')), Decimal('0')).quantize(
                    Decimal('0.01')
                )
                if state_profile.required_hours is not None
                else None
            ),
        )

    return AttendanceSummaryResponse(
        student_id=student_id,
        school_year_id=school_year.id if school_year is not None else school_year_id,
        period=period,  # type: ignore[arg-type]
        total_records=total_records,
        instructional_days=instructional_days,
        non_instructional_days=non_instructional_days,
        attendance_rate=_attendance_rate(instructional_days=instructional_days, total_records=total_records),
        total_hours=total_hours,
        buckets=buckets,
        state_profile_progress=state_profile_progress,
    )


@router.get('/hours', response_model=AttendanceHoursResponse)
async def get_instructional_hours(
    student_id: int = Query(..., ge=1),
    school_year_id: int = Query(..., ge=1),
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.read_students, action='view instructional hours')),
) -> AttendanceHoursResponse:
    await _get_student_or_404(db, student_id, auth.family_id)
    ensure_student_scope(auth, student_id, action='view instructional hours')
    school_year = await _resolve_school_year(db, family_id=auth.family_id, school_year_id=school_year_id)
    assert school_year is not None

    stmt = select(AttendanceRecord).where(
        AttendanceRecord.family_id == auth.family_id,
        AttendanceRecord.student_id == student_id,
        AttendanceRecord.date >= school_year.start_date,
        AttendanceRecord.date <= school_year.end_date,
    )
    records = list((await db.execute(stmt)).scalars().all())
    total_hours = _sum_hours(records) or Decimal('0')
    recorded_days = len(records)
    average = float(total_hours / recorded_days) if recorded_days else 0.0
    return AttendanceHoursResponse(
        student_id=student_id,
        school_year_id=school_year.id,
        total_hours=total_hours,
        recorded_days=recorded_days,
        average_hours_per_day=round(average, 2),
    )
