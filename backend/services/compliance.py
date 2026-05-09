from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
import re

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.models import (
    AttendanceRecord,
    AttendanceStatus,
    ComplianceRule,
    ComplianceRuleType,
    ComplianceState,
    ComplianceStatus,
    FamilySettings,
    PortfolioEntry,
    QuizAttempt,
    SchoolYear,
    Student,
    Subject,
)
from backend.services.notifications import FAMILY_MANAGER_ROLES, create_family_notifications
from backend.models.notification import NotificationType

CUSTOM_STATE_CODE = 'CUSTOM'
_TOKEN_RE = re.compile(r'[^a-z0-9]+')
ASSESSMENT_KEYWORDS = ('assessment', 'evaluation', 'test', 'testing', 'exam', 'examiner')
NOTIFICATION_KEYWORDS = ('notice', 'intent', 'report', 'quarterly', 'notification', 'affidavit')
PORTFOLIO_KEYWORDS = ('portfolio', 'sample', 'journal', 'work')
QUANTITATIVE_RULE_TYPES = {
    ComplianceRuleType.attendance_days,
    ComplianceRuleType.attendance_hours,
    ComplianceRuleType.subjects_required,
    ComplianceRuleType.assessment_required,
    ComplianceRuleType.notification_required,
    ComplianceRuleType.portfolio_required,
}


@dataclass(slots=True)
class ComplianceComputation:
    rule: ComplianceRule
    status: ComplianceState
    current_value: Decimal
    required_value: Decimal
    notes: str | None
    last_checked_at: datetime


def _decimal(value: object) -> Decimal:
    if isinstance(value, Decimal):
        return value.quantize(Decimal('0.01'))
    if value is None:
        return Decimal('0.00')
    return Decimal(str(value)).quantize(Decimal('0.01'))


def _normalized_token(value: str) -> str:
    return _TOKEN_RE.sub(' ', value.strip().lower()).strip()


def _string_list(value: list[str] | None) -> list[str]:
    if not value:
        return []
    return [item for item in (_normalized_token(entry) for entry in value) if item]


def _school_year_progress(school_year: SchoolYear, *, today: date | None = None) -> float:
    current_day = today or datetime.now(UTC).date()
    if current_day <= school_year.start_date:
        return 0.0
    total_days = max(1, (school_year.end_date - school_year.start_date).days + 1)
    elapsed_days = min(total_days, max(0, (current_day - school_year.start_date).days + 1))
    return round(elapsed_days / total_days, 4)


async def get_family_state_code(db: AsyncSession, *, family_id: int) -> str:
    state_code = (
        await db.execute(select(FamilySettings.state_code).where(FamilySettings.family_id == family_id))
    ).scalar_one_or_none()
    return (state_code or CUSTOM_STATE_CODE).upper()


async def set_family_state_code(db: AsyncSession, *, family_id: int, state_code: str) -> str:
    family_settings = await db.get(FamilySettings, family_id)
    if family_settings is None:
        family_settings = FamilySettings(family_id=family_id, timezone='UTC', grading_scale='letter', state_code=state_code)
        db.add(family_settings)
    else:
        family_settings.state_code = state_code
    await db.commit()
    return family_settings.state_code


async def resolve_school_year(
    db: AsyncSession,
    *,
    family_id: int,
    school_year_id: int | None = None,
    date_hint: date | None = None,
) -> SchoolYear | None:
    if school_year_id is not None:
        return (
            await db.execute(
                select(SchoolYear)
                .where(SchoolYear.id == school_year_id, SchoolYear.family_id == family_id)
                .limit(1)
            )
        ).scalar_one_or_none()
    active = (
        await db.execute(
            select(SchoolYear)
            .where(SchoolYear.family_id == family_id, SchoolYear.is_active.is_(True))
            .order_by(SchoolYear.start_date.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if active is not None:
        return active
    if date_hint is None:
        date_hint = datetime.now(UTC).date()
    return (
        await db.execute(
            select(SchoolYear)
            .where(
                SchoolYear.family_id == family_id,
                SchoolYear.start_date <= date_hint,
                SchoolYear.end_date >= date_hint,
            )
            .order_by(SchoolYear.start_date.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


async def list_rules_for_state(db: AsyncSession, *, family_id: int, state_code: str) -> list[ComplianceRule]:
    normalized_state = state_code.upper()
    stmt = (
        select(ComplianceRule)
        .where(
            ComplianceRule.is_active.is_(True),
            or_(
                and_(ComplianceRule.family_id.is_(None), ComplianceRule.state_code == normalized_state),
                and_(
                    ComplianceRule.family_id == family_id,
                    ComplianceRule.state_code.in_((normalized_state, CUSTOM_STATE_CODE)),
                ),
            ),
        )
        .order_by(ComplianceRule.family_id.is_not(None), ComplianceRule.rule_type.asc(), ComplianceRule.rule_name.asc())
    )
    return list((await db.execute(stmt)).scalars().all())


async def list_students_for_compliance(db: AsyncSession, *, family_id: int) -> list[Student]:
    stmt = select(Student).where(Student.family_id == family_id).order_by(Student.name.asc(), Student.id.asc())
    return list((await db.execute(stmt)).scalars().all())


async def create_custom_rule(
    db: AsyncSession,
    *,
    family_id: int,
    state_code: str,
    rule_type: ComplianceRuleType,
    rule_name: str,
    description: str,
    threshold_value: Decimal,
    threshold_unit: str,
    subjects_list: list[str] | None,
    is_active: bool,
) -> ComplianceRule:
    rule = ComplianceRule(
        family_id=family_id,
        state_code=state_code.upper(),
        rule_type=rule_type,
        rule_name=rule_name,
        description=description,
        threshold_value=threshold_value,
        threshold_unit=threshold_unit,
        subjects_list=subjects_list or None,
        is_active=is_active,
    )
    db.add(rule)
    await db.commit()
    await db.refresh(rule)
    return rule


def _status_summary(statuses: list[ComplianceStatus]) -> dict[ComplianceState, int]:
    summary = {state: 0 for state in ComplianceState}
    for item in statuses:
        summary[item.status] += 1
    return summary


def _build_date_range(school_year: SchoolYear) -> tuple[date, date, datetime, datetime]:
    start_dt = datetime.combine(school_year.start_date, time.min, tzinfo=UTC)
    end_dt = datetime.combine(school_year.end_date, time.max, tzinfo=UTC)
    return school_year.start_date, school_year.end_date, start_dt, end_dt


def _derive_status(
    *,
    rule_type: ComplianceRuleType,
    current_value: Decimal,
    required_value: Decimal,
    school_year_progress: float,
    missing_items: list[str] | None = None,
) -> ComplianceState:
    if required_value <= Decimal('0'):
        return ComplianceState.compliant
    if current_value >= required_value:
        return ComplianceState.compliant
    if school_year_progress >= 1:
        return ComplianceState.non_compliant
    if rule_type == ComplianceRuleType.subjects_required:
        return ComplianceState.warning if missing_items else ComplianceState.compliant
    if rule_type in {
        ComplianceRuleType.assessment_required,
        ComplianceRuleType.notification_required,
        ComplianceRuleType.portfolio_required,
    }:
        return ComplianceState.warning if school_year_progress >= 0.8 else ComplianceState.compliant
    expected_progress = required_value * Decimal(str(max(school_year_progress, 0)))
    if school_year_progress >= 0.25 and current_value < (expected_progress * Decimal('0.9')):
        return ComplianceState.warning
    return ComplianceState.compliant


async def _attendance_progress(
    db: AsyncSession,
    *,
    family_id: int,
    student_id: int,
    school_year: SchoolYear,
) -> tuple[Decimal, Decimal]:
    start_date, end_date, _, _ = _build_date_range(school_year)
    rows = (
        await db.execute(
            select(AttendanceRecord.status, AttendanceRecord.instructional_hours).where(
                AttendanceRecord.family_id == family_id,
                AttendanceRecord.student_id == student_id,
                AttendanceRecord.date >= start_date,
                AttendanceRecord.date <= end_date,
            )
        )
    ).all()
    attendance_days = Decimal(sum(1 for status, _ in rows if status != AttendanceStatus.absent)).quantize(Decimal('0.01'))
    attendance_hours = sum((_decimal(hours) for _, hours in rows), start=Decimal('0.00')).quantize(Decimal('0.01'))
    return attendance_days, attendance_hours


async def _family_subject_names(db: AsyncSession, *, family_id: int) -> list[str]:
    names = (
        await db.execute(select(Subject.name).where(Subject.family_id == family_id).order_by(Subject.name.asc()))
    ).scalars().all()
    return [_normalized_token(name) for name in names if name]


def _subject_coverage(rule: ComplianceRule, subject_names: list[str]) -> tuple[Decimal, list[str]]:
    required_subjects = _string_list(rule.subjects_list)
    matched = [required for required in required_subjects if any(required in name or name in required for name in subject_names)]
    missing = [required for required in required_subjects if required not in matched]
    return Decimal(len(matched)).quantize(Decimal('0.01')), missing


async def _supporting_entries(
    db: AsyncSession,
    *,
    family_id: int,
    student_id: int,
    school_year: SchoolYear,
) -> list[PortfolioEntry]:
    start_date, end_date, _, _ = _build_date_range(school_year)
    stmt = (
        select(PortfolioEntry)
        .where(
            PortfolioEntry.family_id == family_id,
            PortfolioEntry.student_id == student_id,
            PortfolioEntry.date >= start_date,
            PortfolioEntry.date <= end_date,
        )
        .order_by(PortfolioEntry.date.asc(), PortfolioEntry.id.asc())
    )
    return list((await db.execute(stmt)).scalars().all())


def _entry_matches(entry: PortfolioEntry, keywords: tuple[str, ...]) -> bool:
    haystacks = [entry.title or '', entry.description or ''] + list(entry.tags or [])
    normalized = ' '.join(_normalized_token(item) for item in haystacks if item)
    return any(keyword in normalized for keyword in keywords)


async def _assessment_count(
    db: AsyncSession,
    *,
    family_id: int,
    student_id: int,
    school_year: SchoolYear,
    entries: list[PortfolioEntry],
) -> Decimal:
    _, _, start_dt, end_dt = _build_date_range(school_year)
    quiz_attempts = (
        await db.execute(
            select(func.count(QuizAttempt.id)).where(
                QuizAttempt.family_id == family_id,
                QuizAttempt.student_id == student_id,
                QuizAttempt.completed_at >= start_dt,
                QuizAttempt.completed_at <= end_dt,
            )
        )
    ).scalar_one()
    evidence_count = sum(1 for entry in entries if _entry_matches(entry, ASSESSMENT_KEYWORDS))
    return _decimal((quiz_attempts or 0) + evidence_count)


def _notification_count(entries: list[PortfolioEntry]) -> Decimal:
    return _decimal(sum(1 for entry in entries if _entry_matches(entry, NOTIFICATION_KEYWORDS)))


def _portfolio_count(entries: list[PortfolioEntry]) -> Decimal:
    meaningful_entries = [
        entry for entry in entries if entry.title or entry.description or entry.attachments or _entry_matches(entry, PORTFOLIO_KEYWORDS)
    ]
    return _decimal(len(meaningful_entries))


def _rule_note(
    *,
    rule: ComplianceRule,
    current_value: Decimal,
    required_value: Decimal,
    status: ComplianceState,
    missing_subjects: list[str] | None = None,
) -> str:
    if rule.rule_type == ComplianceRuleType.subjects_required:
        if missing_subjects:
            return f"Missing required subjects: {', '.join(missing_subjects)}."
        return 'All required subjects are represented in the family curriculum.'
    label = rule.threshold_unit.replace('_', ' ')
    if status == ComplianceState.compliant:
        return f'{current_value:g} of {required_value:g} {label} recorded.'
    return f'{current_value:g} of {required_value:g} {label} recorded so far.'


async def _upsert_statuses(
    db: AsyncSession,
    *,
    family_id: int,
    student_id: int,
    school_year_id: int,
    computations: list[ComplianceComputation],
) -> list[ComplianceStatus]:
    existing_rows = (
        await db.execute(
            select(ComplianceStatus)
            .options(selectinload(ComplianceStatus.rule))
            .where(
                ComplianceStatus.family_id == family_id,
                ComplianceStatus.student_id == student_id,
                ComplianceStatus.school_year_id == school_year_id,
            )
        )
    ).scalars().all()
    by_rule_id = {row.rule_id: row for row in existing_rows}
    results: list[ComplianceStatus] = []
    for computation in computations:
        row = by_rule_id.get(computation.rule.id)
        if row is None:
            row = ComplianceStatus(
                family_id=family_id,
                student_id=student_id,
                school_year_id=school_year_id,
                rule_id=computation.rule.id,
                status=computation.status,
                current_value=computation.current_value,
                required_value=computation.required_value,
                last_checked_at=computation.last_checked_at,
                notes=computation.notes,
            )
            db.add(row)
        else:
            row.status = computation.status
            row.current_value = computation.current_value
            row.required_value = computation.required_value
            row.last_checked_at = computation.last_checked_at
            row.notes = computation.notes
        row.rule = computation.rule
        results.append(row)
    await db.flush()
    results.sort(key=lambda item: (item.rule.rule_type.value, item.rule.rule_name.lower()))
    return results


async def _emit_compliance_notifications(
    db: AsyncSession,
    *,
    family_id: int,
    student: Student,
    statuses: list[ComplianceStatus],
) -> None:
    for item in statuses:
        if item.status == ComplianceState.compliant:
            continue
        title = f'Compliance {item.status.value.replace("_", " ")}: {student.name}'
        message = f'{item.rule.rule_name}: {item.notes or "Review this rule before the school year ends."}'
        await create_family_notifications(
            db,
            family_id=family_id,
            notification_type=NotificationType.compliance_reminder,
            title=title,
            message=message,
            link='/compliance',
            roles=FAMILY_MANAGER_ROLES,
            student_id=student.id,
            suppress_duplicates_for=timedelta(hours=12),
        )


async def compute_student_statuses(
    db: AsyncSession,
    *,
    family_id: int,
    student: Student,
    school_year: SchoolYear,
    state_code: str,
) -> list[ComplianceStatus]:
    rules = await list_rules_for_state(db, family_id=family_id, state_code=state_code)
    checked_at = datetime.now(UTC)
    progress = _school_year_progress(school_year)
    attendance_days, attendance_hours = await _attendance_progress(
        db,
        family_id=family_id,
        student_id=student.id,
        school_year=school_year,
    )
    subject_names = await _family_subject_names(db, family_id=family_id)
    entries = await _supporting_entries(db, family_id=family_id, student_id=student.id, school_year=school_year)

    computations: list[ComplianceComputation] = []
    for rule in rules:
        required_value = _decimal(rule.threshold_value)
        current_value = Decimal('0.00')
        missing_subjects: list[str] | None = None
        if rule.rule_type == ComplianceRuleType.attendance_days:
            current_value = attendance_days
        elif rule.rule_type == ComplianceRuleType.attendance_hours:
            current_value = attendance_hours
        elif rule.rule_type == ComplianceRuleType.subjects_required:
            current_value, missing_subjects = _subject_coverage(rule, subject_names)
        elif rule.rule_type == ComplianceRuleType.assessment_required:
            current_value = await _assessment_count(
                db,
                family_id=family_id,
                student_id=student.id,
                school_year=school_year,
                entries=entries,
            )
        elif rule.rule_type == ComplianceRuleType.notification_required:
            current_value = _notification_count(entries)
        elif rule.rule_type == ComplianceRuleType.portfolio_required:
            current_value = _portfolio_count(entries)

        status = _derive_status(
            rule_type=rule.rule_type,
            current_value=current_value,
            required_value=required_value,
            school_year_progress=progress,
            missing_items=missing_subjects,
        )
        computations.append(
            ComplianceComputation(
                rule=rule,
                status=status,
                current_value=current_value,
                required_value=required_value,
                notes=_rule_note(
                    rule=rule,
                    current_value=current_value,
                    required_value=required_value,
                    status=status,
                    missing_subjects=missing_subjects,
                ),
                last_checked_at=checked_at,
            )
        )

    statuses = await _upsert_statuses(
        db,
        family_id=family_id,
        student_id=student.id,
        school_year_id=school_year.id,
        computations=computations,
    )
    await _emit_compliance_notifications(db, family_id=family_id, student=student, statuses=statuses)
    return statuses


async def get_student_status_payload(
    db: AsyncSession,
    *,
    family_id: int,
    student_id: int,
    school_year_id: int | None = None,
) -> tuple[str, SchoolYear | None, Student, list[ComplianceStatus]]:
    state_code = await get_family_state_code(db, family_id=family_id)
    student = (
        await db.execute(select(Student).where(Student.family_id == family_id, Student.id == student_id).limit(1))
    ).scalar_one_or_none()
    if student is None:
        raise ValueError('Student not found')
    school_year = await resolve_school_year(db, family_id=family_id, school_year_id=school_year_id)
    if school_year is None:
        return state_code, None, student, []
    statuses = await compute_student_statuses(
        db,
        family_id=family_id,
        student=student,
        school_year=school_year,
        state_code=state_code,
    )
    await db.commit()
    return state_code, school_year, student, statuses


async def get_dashboard_payload(
    db: AsyncSession,
    *,
    family_id: int,
    school_year_id: int | None = None,
) -> tuple[str, SchoolYear | None, list[tuple[Student, list[ComplianceStatus]]]]:
    state_code = await get_family_state_code(db, family_id=family_id)
    school_year = await resolve_school_year(db, family_id=family_id, school_year_id=school_year_id)
    students = await list_students_for_compliance(db, family_id=family_id)
    if school_year is None:
        return state_code, None, [(student, []) for student in students]
    payload: list[tuple[Student, list[ComplianceStatus]]] = []
    for student in students:
        statuses = await compute_student_statuses(
            db,
            family_id=family_id,
            student=student,
            school_year=school_year,
            state_code=state_code,
        )
        payload.append((student, statuses))
    await db.commit()
    return state_code, school_year, payload
