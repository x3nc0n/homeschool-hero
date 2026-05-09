from __future__ import annotations

from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
import logging
from typing import Awaitable, Callable, TypeVar

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.database import get_db
from backend.models import (
    Assignment,
    AssignmentTarget,
    AssignmentTargetStatus,
    AttendanceRecord,
    ComplianceState,
    Grade,
    Schedule,
    SchoolYear,
    Student,
    Submission,
    Subject,
)
from backend.routers.lesson_plans import _build_pacing_status_payload
from backend.routers.schedule import _build_daily_agenda_entries, _schedule_options
from backend.schemas.dashboard import (
    DashboardAssignmentItem,
    DashboardAttendanceItem,
    DashboardComplianceWarningItem,
    DashboardGradeItem,
    DashboardPacingAlertItem,
    DashboardRead,
    DashboardScheduleItem,
    DashboardStudentSummary,
    DashboardSystemStatus,
)
from backend.security import AuthSession
from backend.services.authorization import Capability, ensure_student_scope, get_student_scope_id, require_capabilities
from backend.services.compliance import get_dashboard_payload
from backend.services.gradebook import calculate_gradebook_summary
from backend.services.health import collect_service_health, summarize_health

router = APIRouter(prefix='/dashboard', tags=['dashboard'])
logger = logging.getLogger(__name__)
T = TypeVar('T')


def _normalize_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


async def _resolve_dashboard_students(
    db: AsyncSession,
    auth: AuthSession,
    requested_student_id: int | None,
) -> list[Student]:
    stmt = select(Student).where(Student.family_id == auth.family_id).order_by(Student.name, Student.id)
    if auth.role == 'student_viewer':
        scoped_student_id = get_student_scope_id(auth)
        if requested_student_id is not None and requested_student_id != scoped_student_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{auth.role}' is not allowed to view another student's dashboard.",
            )
        stmt = stmt.where(Student.id == scoped_student_id)
    elif requested_student_id is not None:
        stmt = stmt.where(Student.id == requested_student_id)

    students = list((await db.execute(stmt)).scalars().all())
    if requested_student_id is not None and not students:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Student not found')
    for student in students:
        ensure_student_scope(auth, student.id, action='view dashboard')
    return students


async def _resolve_school_year(db: AsyncSession, family_id: int, today: date) -> SchoolYear | None:
    active = (
        await db.execute(
            select(SchoolYear)
            .options(selectinload(SchoolYear.terms))
            .where(SchoolYear.family_id == family_id, SchoolYear.is_active.is_(True))
            .order_by(SchoolYear.start_date.desc(), SchoolYear.id.desc())
        )
    ).scalars().first()
    if active is not None:
        return active
    return (
        await db.execute(
            select(SchoolYear)
            .options(selectinload(SchoolYear.terms))
            .where(
                SchoolYear.family_id == family_id,
                SchoolYear.start_date <= today,
                SchoolYear.end_date >= today,
            )
            .order_by(SchoolYear.start_date.desc(), SchoolYear.id.desc())
        )
    ).scalars().first()


def _summarize_pacing_status(items: list[dict[str, object]]) -> str | None:
    statuses = [str(item.get('status')) for item in items]
    if not statuses:
        return None
    if 'behind' in statuses:
        return 'behind'
    if 'on_track' in statuses:
        return 'on_track'
    if 'ahead' in statuses:
        return 'ahead'
    return statuses[0]


def _summarize_compliance_status(statuses: list[object]) -> ComplianceState | None:
    resolved = [status.status for status in statuses if getattr(status, 'status', None) is not None]
    if not resolved:
        return None
    if ComplianceState.non_compliant in resolved:
        return ComplianceState.non_compliant
    if ComplianceState.warning in resolved:
        return ComplianceState.warning
    return ComplianceState.compliant


async def _best_effort_dashboard_section(section_name: str, loader: Callable[[], Awaitable[T]], fallback: T) -> T:
    try:
        return await loader()
    except Exception:
        logger.exception('Dashboard section failed to load', extra={'section': section_name})
        return fallback


async def _build_system_status(generated_at: datetime) -> DashboardSystemStatus:
    services = await collect_service_health()
    overall, summary = summarize_health(services)
    affected_services = [
        str(service.get('label') or service.get('name'))
        for service in services.values()
        if service.get('status') in {'degraded', 'unhealthy'}
    ]
    return DashboardSystemStatus(
        status=overall,
        checked_at=generated_at,
        healthy_services=summary['healthy'],
        degraded_services=summary['degraded'],
        unhealthy_services=summary['unhealthy'],
        not_configured_services=summary['not_configured'],
        affected_services=affected_services,
    )


@router.get('', response_model=DashboardRead)
async def get_dashboard(
    request: Request,
    student_id: int | None = Query(default=None, ge=1),
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(
        require_capabilities(Capability.read_curriculum, Capability.read_grades, action='view dashboard')
    ),
) -> DashboardRead:
    today = datetime.now(UTC).date()
    generated_at = datetime.now(UTC)
    students = await _resolve_dashboard_students(db, auth, student_id)
    student_ids = [student.id for student in students]
    student_map = {student.id: student for student in students}

    if not students:
        system_status = None
        if auth.role != 'student_viewer':
            system_status = await _best_effort_dashboard_section(
                'system status',
                lambda: _build_system_status(generated_at),
                None,
            )
        return DashboardRead(
            role=auth.role,
            generated_at=generated_at,
            selected_student_id=student_id,
            system_status=system_status,
        )

    school_year = await _resolve_school_year(db, auth.family_id, today)

    schedule_rows = (
        await db.execute(
            select(Schedule)
            .options(*_schedule_options())
            .join(SchoolYear, SchoolYear.id == Schedule.school_year_id)
            .where(
                Schedule.family_id == auth.family_id,
                Schedule.student_id.in_(student_ids),
                SchoolYear.start_date <= today,
                SchoolYear.end_date >= today,
            )
            .order_by(Schedule.student_id, Schedule.name, Schedule.id)
        )
    ).scalars().all()
    schedules_by_student: dict[int, list[Schedule]] = defaultdict(list)
    for schedule in schedule_rows:
        schedules_by_student[schedule.student_id].append(schedule)

    today_schedule: list[DashboardScheduleItem] = []
    for current_student_id, student_schedules in schedules_by_student.items():
        for item in _build_daily_agenda_entries(student_schedules, today):
            today_schedule.append(
                DashboardScheduleItem(
                    student_id=current_student_id,
                    student_name=student_map[current_student_id].name,
                    schedule_id=item.schedule_id,
                    schedule_name=item.schedule_name,
                    subject_id=item.subject_id,
                    subject_name=item.subject_name,
                    subject_color=item.subject_color,
                    date=item.date,
                    start_time=item.start_time,
                    end_time=item.end_time,
                    source=item.source,
                    override_type=item.override_type,
                    location=item.location,
                    notes=item.notes,
                    reason=item.reason,
                )
            )
    today_schedule.sort(key=lambda item: (item.start_time, item.student_name.lower(), item.subject_name.lower()))

    assignments = (
        await db.execute(
            select(Assignment)
            .options(
                selectinload(Assignment.subject),
                selectinload(Assignment.targets).selectinload(AssignmentTarget.student),
            )
            .where(Assignment.family_id == auth.family_id)
            .order_by(Assignment.due_date.asc().nullslast(), Assignment.id.asc())
        )
    ).scalars().all()
    upcoming_assignments: list[DashboardAssignmentItem] = []
    for assignment in assignments:
        target_rows = [target for target in assignment.targets if target.student_id in student_map]
        if target_rows:
            scoped_targets = target_rows
        else:
            scoped_targets = [
                AssignmentTarget(
                    assignment_id=assignment.id,
                    student_id=current_student.id,
                    due_date=assignment.due_date,
                    status=AssignmentTargetStatus.assigned,
                )
                for current_student in students
            ]
        for target in scoped_targets:
            due_date = _normalize_datetime(target.due_date or assignment.due_date)
            if due_date is None:
                continue
            if due_date.date() < today or due_date.date() > today + timedelta(days=7):
                continue
            if target.status in {AssignmentTargetStatus.graded, AssignmentTargetStatus.excused}:
                continue
            current_student = student_map.get(target.student_id)
            if current_student is None:
                continue
            upcoming_assignments.append(
                DashboardAssignmentItem(
                    assignment_id=assignment.id,
                    title=assignment.title,
                    subject_id=assignment.subject_id,
                    subject_name=assignment.subject.name if assignment.subject else None,
                    student_id=current_student.id,
                    student_name=current_student.name,
                    due_date=due_date,
                    status=target.status.value,
                    days_until_due=(due_date.date() - today).days,
                )
            )
    upcoming_assignments.sort(key=lambda item: (item.due_date, item.student_name or '', item.title.lower()))
    upcoming_assignments = upcoming_assignments[:12]

    recent_grade_rows = (
        await db.execute(
            select(Grade, Submission, Assignment, Subject, Student)
            .join(Submission, Submission.id == Grade.submission_id)
            .join(Assignment, Assignment.id == Submission.assignment_id)
            .join(Subject, Subject.id == Assignment.subject_id)
            .join(Student, Student.id == Grade.student_id)
            .where(Grade.family_id == auth.family_id, Grade.student_id.in_(student_ids))
            .order_by(Grade.created_at.desc(), Grade.id.desc())
            .limit(8)
        )
    ).all()
    recent_grades = [
        DashboardGradeItem(
            grade_id=grade.id,
            assignment_id=assignment.id,
            assignment_title=assignment.title,
            subject_name=subject.name,
            student_id=student.id,
            student_name=student.name,
            score=float(grade.score),
            max_score=float(grade.max_score),
            percent=round((float(grade.score) / float(grade.max_score)) * 100, 2) if grade.max_score else 0.0,
            letter_grade=grade.letter_grade,
            graded_at=_normalize_datetime(grade.created_at) or generated_at,
        )
        for grade, _submission, assignment, subject, student in recent_grade_rows
    ]

    attendance_today: list[DashboardAttendanceItem] = []
    attendance_by_student: dict[int, list[AttendanceRecord]] = defaultdict(list)
    today_records = (
        await db.execute(
            select(AttendanceRecord)
            .where(
                AttendanceRecord.family_id == auth.family_id,
                AttendanceRecord.student_id.in_(student_ids),
                AttendanceRecord.date == today,
            )
            .order_by(AttendanceRecord.student_id)
        )
    ).scalars().all()
    for record in today_records:
        attendance_by_student[record.student_id].append(record)

    if auth.role != 'student_viewer':
        for current_student in students:
            record = attendance_by_student.get(current_student.id, [None])[0]
            attendance_today.append(
                DashboardAttendanceItem(
                    student_id=current_student.id,
                    student_name=current_student.name,
                    date=today,
                    status=record.status.value if record is not None else 'not_recorded',
                    instructional_hours=record.instructional_hours if record is not None else None,
                    notes=record.notes if record is not None else None,
                )
            )

    attendance_summary_records: list[AttendanceRecord] = []
    if school_year is not None:
        attendance_summary_records = (
            await db.execute(
                select(AttendanceRecord)
                .where(
                    AttendanceRecord.family_id == auth.family_id,
                    AttendanceRecord.student_id.in_(student_ids),
                    AttendanceRecord.date >= school_year.start_date,
                    AttendanceRecord.date <= school_year.end_date,
                )
                .order_by(AttendanceRecord.student_id, AttendanceRecord.date)
            )
        ).scalars().all()
    attendance_summary_by_student: dict[int, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for record in attendance_summary_records:
        attendance_summary_by_student[record.student_id][record.status.value] += 1
        attendance_summary_by_student[record.student_id]['total'] += 1

    pacing_by_student: dict[int, list[dict[str, object]]] = defaultdict(list)
    pacing_alerts: list[DashboardPacingAlertItem] = []
    if auth.role != 'student_viewer':
        for current_student in students:
            pacing_payload = await _best_effort_dashboard_section(
                f'pacing:{current_student.id}',
                lambda current_student=current_student: _build_pacing_status_payload(
                    db,
                    family_id=auth.family_id,
                    student_id=current_student.id,
                    subject_id=None,
                ),
                {'items': []},
            )
            items = list(pacing_payload.get('items', []))
            pacing_by_student[current_student.id] = items
            for item in items:
                if item.get('status') != 'behind':
                    continue
                pacing_alerts.append(
                    DashboardPacingAlertItem(
                        student_id=current_student.id,
                        student_name=current_student.name,
                        pacing_target_id=int(item['pacing_target_id']),
                        unit_name=str(item['unit_name']),
                        package_name=str(item['package_name']),
                        target_end_date=date.fromisoformat(str(item['target_end_date'])),
                        remaining_lessons=int(item['remaining_lessons']),
                        status=str(item['status']),
                    )
                )
        pacing_alerts.sort(key=lambda item: (item.target_end_date, item.student_name.lower(), item.unit_name.lower()))

    compliance_by_student: dict[int, list[object]] = defaultdict(list)
    compliance_warnings: list[DashboardComplianceWarningItem] = []
    if auth.role != 'student_viewer':
        compliance_payload = await _best_effort_dashboard_section(
            'compliance',
            lambda: _load_compliance_payload(
                db,
                family_id=auth.family_id,
                school_year_id=school_year.id if school_year is not None else None,
            ),
            [],
        )
        for student_record, statuses in compliance_payload:
            if student_record.id not in student_map:
                continue
            compliance_by_student[student_record.id] = statuses
            for compliance_status in statuses:
                if compliance_status.status not in {ComplianceState.warning, ComplianceState.non_compliant}:
                    continue
                compliance_warnings.append(
                    DashboardComplianceWarningItem(
                        student_id=student_record.id,
                        student_name=student_record.name,
                        rule_name=compliance_status.rule.rule_name,
                        status=compliance_status.status,
                        current_value=compliance_status.current_value,
                        required_value=compliance_status.required_value,
                        threshold_unit=compliance_status.rule.threshold_unit,
                        last_checked_at=compliance_status.last_checked_at,
                        notes=compliance_status.notes,
                    )
                )
        compliance_warnings.sort(
            key=lambda item: (item.status.value, item.student_name.lower(), item.rule_name.lower())
        )

    student_summaries: list[DashboardStudentSummary] = []
    assignments_due_by_student: dict[int, int] = defaultdict(int)
    for item in upcoming_assignments:
        if item.student_id is not None:
            assignments_due_by_student[item.student_id] += 1
    for current_student in students:
        gradebook_summary = await _best_effort_dashboard_section(
            f'gradebook-summary:{current_student.id}',
            lambda current_student=current_student: calculate_gradebook_summary(
                db,
                family_id=auth.family_id,
                student_id=current_student.id,
            ),
            {'gpa': None},
        )
        attendance_counts = attendance_summary_by_student.get(current_student.id, {})
        total_records = int(attendance_counts.get('total', 0))
        attended = int(attendance_counts.get('present', 0)) + int(attendance_counts.get('tardy', 0)) + int(
            attendance_counts.get('excused', 0)
        )
        attendance_rate = round((attended / total_records) * 100, 2) if total_records else None
        student_summaries.append(
            DashboardStudentSummary(
                student_id=current_student.id,
                student_name=current_student.name,
                current_gpa=gradebook_summary.get('gpa'),
                attendance_rate=attendance_rate,
                assignments_due_count=assignments_due_by_student.get(current_student.id, 0),
                pacing_status=_summarize_pacing_status(pacing_by_student.get(current_student.id, [])),
                compliance_status=_summarize_compliance_status(compliance_by_student.get(current_student.id, [])),
            )
        )

    system_status = None
    if auth.role != 'student_viewer':
        system_status = await _best_effort_dashboard_section(
            'system status',
            lambda: _build_system_status(generated_at),
            None,
        )

    return DashboardRead(
        role=auth.role,
        generated_at=generated_at,
        selected_student_id=student_id,
        today_schedule=today_schedule,
        upcoming_assignments=upcoming_assignments,
        recent_grades=recent_grades,
        attendance_today=attendance_today,
        pacing_alerts=pacing_alerts,
        compliance_warnings=compliance_warnings,
        system_status=system_status,
        student_summaries=student_summaries,
    )


async def _load_compliance_payload(
    db: AsyncSession,
    *,
    family_id: int,
    school_year_id: int | None,
) -> list[tuple[Student, list[object]]]:
    _state_code, _resolved_school_year, compliance_payload = await get_dashboard_payload(
        db,
        family_id=family_id,
        school_year_id=school_year_id,
    )
    return compliance_payload
