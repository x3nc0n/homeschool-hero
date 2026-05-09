from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from io import BytesIO
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy import Select, and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.models import (
    Assignment,
    AttendanceRecord,
    AttendanceStatus,
    ComplianceReport,
    ComplianceReportStatus,
    ComplianceReportType,
    ComplianceRuleType,
    Family,
    Grade,
    GradeScale,
    GradingPeriod,
    PortfolioEntry,
    Quiz,
    QuizAttempt,
    SchoolYear,
    Submission,
    Student,
    Subject,
)
from backend.services.compliance import get_family_state_code, list_rules_for_state
from backend.services.gradebook import ensure_default_grade_scale, map_percent_to_grade


@dataclass(frozen=True, slots=True)
class RequiredReportDefinition:
    report_type: ComplianceReportType
    label: str
    description: str
    cadence: str
    required_count: int


DEFAULT_REQUIRED_REPORTS = (
    RequiredReportDefinition(
        report_type=ComplianceReportType.attendance_log,
        label='Attendance log',
        description='Keep a year-end attendance log with daily records and total hours or days.',
        cadence='annual',
        required_count=1,
    ),
    RequiredReportDefinition(
        report_type=ComplianceReportType.annual_assessment,
        label='Annual assessment',
        description='Maintain a year-end assessment summary with grades, test scores, and subject coverage.',
        cadence='annual',
        required_count=1,
    ),
)
STATE_REQUIRED_REPORTS: dict[str, tuple[RequiredReportDefinition, ...]] = {
    'TX': (
        DEFAULT_REQUIRED_REPORTS[0],
        DEFAULT_REQUIRED_REPORTS[1],
        RequiredReportDefinition(
            report_type=ComplianceReportType.portfolio_review,
            label='Portfolio review',
            description='Summarize portfolio work samples and learning artifacts kept for the year.',
            cadence='annual',
            required_count=1,
        ),
    ),
    'CA': (
        DEFAULT_REQUIRED_REPORTS[0],
        RequiredReportDefinition(
            report_type=ComplianceReportType.portfolio_review,
            label='Portfolio review',
            description='Maintain a portfolio summary of work samples, journals, and supporting artifacts.',
            cadence='annual',
            required_count=1,
        ),
    ),
    'VA': (
        RequiredReportDefinition(
            report_type=ComplianceReportType.notice_of_intent,
            label='Notice of intent',
            description='Prepare a notice of intent letter with family and student details.',
            cadence='annual',
            required_count=1,
        ),
        DEFAULT_REQUIRED_REPORTS[0],
        DEFAULT_REQUIRED_REPORTS[1],
    ),
    'NY': (
        RequiredReportDefinition(
            report_type=ComplianceReportType.notice_of_intent,
            label='Notice of intent',
            description='File a notice of intent at the start of the homeschool year.',
            cadence='annual',
            required_count=1,
        ),
        RequiredReportDefinition(
            report_type=ComplianceReportType.quarterly_report,
            label='Quarterly reports',
            description='Track four quarterly reports for each school year.',
            cadence='quarterly',
            required_count=4,
        ),
        DEFAULT_REQUIRED_REPORTS[0],
        DEFAULT_REQUIRED_REPORTS[1],
    ),
    'FL': (
        DEFAULT_REQUIRED_REPORTS[0],
        RequiredReportDefinition(
            report_type=ComplianceReportType.portfolio_review,
            label='Portfolio review',
            description='Maintain a portfolio review summary for evaluator meetings.',
            cadence='annual',
            required_count=1,
        ),
        DEFAULT_REQUIRED_REPORTS[1],
    ),
}


def _report_options():
    return (
        selectinload(ComplianceReport.family),
        selectinload(ComplianceReport.student),
        selectinload(ComplianceReport.school_year),
        selectinload(ComplianceReport.generated_by),
    )


def report_type_label(report_type: ComplianceReportType) -> str:
    return {
        ComplianceReportType.annual_assessment: 'Annual assessment',
        ComplianceReportType.quarterly_report: 'Quarterly progress report',
        ComplianceReportType.notice_of_intent: 'Notice of intent',
        ComplianceReportType.attendance_log: 'Attendance log',
        ComplianceReportType.portfolio_review: 'Portfolio review',
    }[report_type]


def _format_datetime(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).strftime('%Y-%m-%d %H:%M UTC')


def _date_range_for_school_year(school_year: SchoolYear) -> tuple[date, date]:
    return school_year.start_date, school_year.end_date


def _period_range_for_report(data: dict[str, Any], school_year: SchoolYear) -> tuple[date, date]:
    period = data.get('period') or {}
    if period.get('start_date') and period.get('end_date'):
        return date.fromisoformat(period['start_date']), date.fromisoformat(period['end_date'])
    return _date_range_for_school_year(school_year)


async def get_compliance_report(
    db: AsyncSession,
    *,
    family_id: int,
    report_id: int,
) -> ComplianceReport | None:
    result = await db.execute(
        select(ComplianceReport).options(*_report_options()).where(ComplianceReport.id == report_id, ComplianceReport.family_id == family_id)
    )
    return result.scalar_one_or_none()


async def list_compliance_reports(
    db: AsyncSession,
    *,
    family_id: int,
    student_id: int | None = None,
    school_year_id: int | None = None,
    report_type: ComplianceReportType | None = None,
    status: ComplianceReportStatus | None = None,
) -> list[ComplianceReport]:
    stmt: Select[tuple[ComplianceReport]] = select(ComplianceReport).options(*_report_options()).where(
        ComplianceReport.family_id == family_id
    )
    if student_id is not None:
        stmt = stmt.where(ComplianceReport.student_id == student_id)
    if school_year_id is not None:
        stmt = stmt.where(ComplianceReport.school_year_id == school_year_id)
    if report_type is not None:
        stmt = stmt.where(ComplianceReport.report_type == report_type)
    if status is not None:
        stmt = stmt.where(ComplianceReport.status == status)
    stmt = stmt.order_by(ComplianceReport.generated_at.desc(), ComplianceReport.id.desc())
    return list((await db.execute(stmt)).scalars().all())


def report_to_summary(report: ComplianceReport) -> dict[str, Any]:
    period = report.data.get('period') if isinstance(report.data, dict) else None
    period_label = period.get('name') if isinstance(period, dict) else None
    return {
        'id': report.id,
        'family_id': report.family_id,
        'student_id': report.student_id,
        'school_year_id': report.school_year_id,
        'state_code': report.state_code,
        'report_type': report.report_type,
        'generated_at': report.generated_at,
        'generated_by_user_id': report.generated_by_user_id,
        'generated_by_name': report.generated_by.display_name if report.generated_by else None,
        'status': report.status,
        'notes': report.notes,
        'student_name': report.student.name if report.student else '',
        'school_year_name': report.school_year.name if report.school_year else '',
        'period_label': period_label,
        'title': report_type_label(report.report_type),
    }


def report_to_read(report: ComplianceReport) -> dict[str, Any]:
    payload = report_to_summary(report)
    payload['student'] = report.student
    payload['data'] = report.data
    return payload


async def _load_generation_context(
    db: AsyncSession,
    *,
    family_id: int,
    student_id: int,
    school_year_id: int,
    grading_period_id: int | None,
) -> tuple[Student, SchoolYear, GradingPeriod | None]:
    student = (
        await db.execute(select(Student).where(Student.id == student_id, Student.family_id == family_id))
    ).scalar_one_or_none()
    if student is None:
        raise ValueError('Student not found')

    school_year = (
        await db.execute(select(SchoolYear).where(SchoolYear.id == school_year_id, SchoolYear.family_id == family_id))
    ).scalar_one_or_none()
    if school_year is None:
        raise ValueError('School year not found')

    grading_period = None
    if grading_period_id is not None:
        grading_period = (
            await db.execute(
                select(GradingPeriod)
                .where(GradingPeriod.id == grading_period_id, GradingPeriod.family_id == family_id)
                .options(selectinload(GradingPeriod.term))
            )
        ).scalar_one_or_none()
        if grading_period is None:
            raise ValueError('Grading period not found')
        if grading_period.start_date < school_year.start_date or grading_period.end_date > school_year.end_date:
            raise ValueError('Grading period must belong to the selected school year')
    return student, school_year, grading_period


async def _attendance_records_for_range(
    db: AsyncSession,
    *,
    family_id: int,
    student_id: int,
    start_date: date,
    end_date: date,
) -> list[AttendanceRecord]:
    result = await db.execute(
        select(AttendanceRecord)
        .where(
            AttendanceRecord.family_id == family_id,
            AttendanceRecord.student_id == student_id,
            AttendanceRecord.date >= start_date,
            AttendanceRecord.date <= end_date,
        )
        .order_by(AttendanceRecord.date.asc(), AttendanceRecord.id.asc())
    )
    return list(result.scalars().all())


def _summarize_attendance(records: Sequence[AttendanceRecord]) -> dict[str, Any]:
    present = sum(1 for record in records if record.status == AttendanceStatus.present)
    absent = sum(1 for record in records if record.status == AttendanceStatus.absent)
    tardy = sum(1 for record in records if record.status == AttendanceStatus.tardy)
    excused = sum(1 for record in records if record.status == AttendanceStatus.excused)
    total_hours = sum((record.instructional_hours or Decimal('0') for record in records), start=Decimal('0')).quantize(
        Decimal('0.01')
    )
    total_records = len(records)
    attendance_rate = round(((present + tardy + excused) / total_records) * 100, 2) if total_records else 0.0
    return {
        'total_records': total_records,
        'present': present,
        'absent': absent,
        'tardy': tardy,
        'excused': excused,
        'attendance_rate': attendance_rate,
        'total_hours': float(total_hours),
        'recorded_days': total_records,
    }


async def _grade_rows_for_range(
    db: AsyncSession,
    *,
    family_id: int,
    student_id: int,
    start_date: date,
    end_date: date,
) -> list[tuple[Subject, Assignment, Grade]]:
    rows = (
        await db.execute(
            select(Subject, Assignment, Grade)
            .join(Assignment, Assignment.subject_id == Subject.id)
            .join(Submission, Submission.assignment_id == Assignment.id)
            .join(
                Grade,
                and_(
                    Grade.submission_id == Submission.id,
                    Grade.student_id == student_id,
                ),
            )
            .where(
                Subject.family_id == family_id,
                Assignment.family_id == family_id,
                Submission.student_id == student_id,
                Submission.is_current.is_(True),
                Assignment.due_date.is_not(None),
                func.date(Assignment.due_date) >= start_date,
                func.date(Assignment.due_date) <= end_date,
            )
            .order_by(Subject.name.asc(), Assignment.due_date.asc(), Assignment.id.asc())
        )
    ).all()
    return [(subject, assignment, grade) for subject, assignment, grade in rows]


async def _quiz_attempt_rows_for_range(
    db: AsyncSession,
    *,
    family_id: int,
    student_id: int,
    start_date: date,
    end_date: date,
) -> list[tuple[QuizAttempt, Quiz, Subject | None]]:
    rows = (
        await db.execute(
            select(QuizAttempt, Quiz, Subject)
            .join(Quiz, Quiz.id == QuizAttempt.quiz_id)
            .outerjoin(Subject, Subject.id == Quiz.subject_id)
            .where(
                QuizAttempt.family_id == family_id,
                QuizAttempt.student_id == student_id,
                QuizAttempt.completed_at.is_not(None),
                func.date(QuizAttempt.completed_at) >= start_date,
                func.date(QuizAttempt.completed_at) <= end_date,
            )
            .order_by(QuizAttempt.completed_at.asc(), QuizAttempt.id.asc())
        )
    ).all()
    return list(rows)


def _subject_scale(subject: Subject | None, default_scale: GradeScale) -> GradeScale:
    if subject is not None and subject.grade_scale is not None:
        return subject.grade_scale
    return default_scale


async def _build_grade_summary(
    db: AsyncSession,
    *,
    family_id: int,
    student_id: int,
    start_date: date,
    end_date: date,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    default_scale = await ensure_default_grade_scale(db, family_id)
    grade_rows = await _grade_rows_for_range(
        db,
        family_id=family_id,
        student_id=student_id,
        start_date=start_date,
        end_date=end_date,
    )
    grouped: dict[int, dict[str, Any]] = {}
    for subject, assignment, grade in grade_rows:
        percent = round((float(grade.score) / float(grade.max_score) * 100), 2) if grade.max_score else None
        entry = grouped.setdefault(
            subject.id,
            {
                'subject_id': subject.id,
                'subject_name': subject.name,
                'grade_scale_name': _subject_scale(subject, default_scale).name,
                'percentages': [],
                'assignment_count': 0,
                'graded_assignments': 0,
            },
        )
        entry['assignment_count'] += 1
        if percent is not None:
            entry['percentages'].append(percent)
            entry['graded_assignments'] += 1

    subject_grades: list[dict[str, Any]] = []
    test_scores: list[dict[str, Any]] = []
    for subject, assignment, grade in grade_rows:
        subject_entry = grouped[subject.id]
        average_percent = round(sum(subject_entry['percentages']) / len(subject_entry['percentages']), 2) if subject_entry['percentages'] else None
        scale = _subject_scale(subject, default_scale)
        letter_grade, gpa_points = map_percent_to_grade(scale, average_percent)
        subject_entry['overall_percent'] = average_percent
        subject_entry['letter_grade'] = letter_grade
        subject_entry['gpa_points'] = None if gpa_points is None else round(float(gpa_points), 2)
        if assignment.category.value in {'quiz', 'test'}:
            percent = round((float(grade.score) / float(grade.max_score) * 100), 2) if grade.max_score else None
            test_scores.append(
                {
                    'type': assignment.category.value,
                    'title': assignment.title,
                    'subject_name': subject.name,
                    'date': assignment.due_date.date().isoformat() if assignment.due_date else None,
                    'score': float(grade.score),
                    'max_score': float(grade.max_score),
                    'percent': percent,
                    'notes': grade.notes,
                }
            )

    for summary in grouped.values():
        summary.pop('percentages', None)
        subject_grades.append(summary)
    subject_grades.sort(key=lambda item: (item['subject_name'], item['subject_id']))

    quiz_attempts = await _quiz_attempt_rows_for_range(
        db,
        family_id=family_id,
        student_id=student_id,
        start_date=start_date,
        end_date=end_date,
    )
    for attempt, quiz, subject in quiz_attempts:
        percent = round((float(attempt.score) / float(attempt.max_score) * 100), 2) if attempt.max_score else None
        test_scores.append(
            {
                'type': 'quiz_attempt',
                'title': quiz.title,
                'subject_name': subject.name if subject else 'General',
                'date': attempt.completed_at.date().isoformat() if attempt.completed_at else None,
                'score': float(attempt.score),
                'max_score': float(attempt.max_score),
                'percent': percent,
                'notes': None,
            }
        )
    test_scores.sort(key=lambda item: ((item.get('date') or ''), item['title']))
    return subject_grades, test_scores


def _coverage_tokens(subject_names: Sequence[str]) -> list[str]:
    tokens = []
    for name in subject_names:
        normalized = ' '.join(str(name or '').strip().lower().replace('-', ' ').split())
        if normalized:
            tokens.append(normalized)
    return tokens


async def _build_subject_coverage(
    db: AsyncSession,
    *,
    family_id: int,
    state_code: str,
) -> dict[str, Any]:
    subject_names = list((await db.execute(select(Subject.name).where(Subject.family_id == family_id).order_by(Subject.name.asc()))).scalars().all())
    subject_tokens = _coverage_tokens(subject_names)
    rules = await list_rules_for_state(db, family_id=family_id, state_code=state_code)
    required_subjects = next(
        (rule.subjects_list or [] for rule in rules if rule.rule_type == ComplianceRuleType.subjects_required and rule.subjects_list),
        [],
    )
    matched: list[str] = []
    missing: list[str] = []
    for required in required_subjects:
        normalized = ' '.join(required.strip().lower().split())
        if any(normalized in token or token in normalized for token in subject_tokens):
            matched.append(required)
        else:
            missing.append(required)
    return {
        'subjects': subject_names,
        'required_subjects': required_subjects,
        'matched_subjects': matched,
        'missing_subjects': missing,
    }


async def _build_annual_assessment_data(
    db: AsyncSession,
    *,
    family_id: int,
    student: Student,
    school_year: SchoolYear,
    state_code: str,
) -> dict[str, Any]:
    start_date, end_date = _date_range_for_school_year(school_year)
    subject_grades, test_scores = await _build_grade_summary(
        db,
        family_id=family_id,
        student_id=student.id,
        start_date=start_date,
        end_date=end_date,
    )
    coverage = await _build_subject_coverage(db, family_id=family_id, state_code=state_code)
    overall_values = [item['overall_percent'] for item in subject_grades if item['overall_percent'] is not None]
    return {
        'summary': {
            'student_name': student.name,
            'school_year_name': school_year.name,
            'overall_percent': round(sum(overall_values) / len(overall_values), 2) if overall_values else None,
            'subject_count': len(subject_grades),
            'test_count': len(test_scores),
            'state_code': state_code,
        },
        'subject_grades': subject_grades,
        'test_scores': test_scores,
        'subject_coverage': coverage,
    }


async def _build_quarterly_report_data(
    db: AsyncSession,
    *,
    family_id: int,
    student: Student,
    school_year: SchoolYear,
    grading_period: GradingPeriod | None,
) -> dict[str, Any]:
    if grading_period is None:
        raise ValueError('Quarterly reports require a grading period')
    subject_grades, test_scores = await _build_grade_summary(
        db,
        family_id=family_id,
        student_id=student.id,
        start_date=grading_period.start_date,
        end_date=grading_period.end_date,
    )
    attendance_records = await _attendance_records_for_range(
        db,
        family_id=family_id,
        student_id=student.id,
        start_date=grading_period.start_date,
        end_date=grading_period.end_date,
    )
    return {
        'period': {
            'grading_period_id': grading_period.id,
            'name': grading_period.name,
            'term_name': grading_period.term.name if grading_period.term else None,
            'start_date': grading_period.start_date.isoformat(),
            'end_date': grading_period.end_date.isoformat(),
        },
        'school_year_name': school_year.name,
        'subject_grades': subject_grades,
        'attendance_summary': _summarize_attendance(attendance_records),
        'test_scores': test_scores,
        'subjects': [item['subject_name'] for item in subject_grades],
    }


async def _build_attendance_log_data(
    db: AsyncSession,
    *,
    family_id: int,
    student: Student,
    school_year: SchoolYear,
) -> dict[str, Any]:
    start_date, end_date = _date_range_for_school_year(school_year)
    records = await _attendance_records_for_range(
        db,
        family_id=family_id,
        student_id=student.id,
        start_date=start_date,
        end_date=end_date,
    )
    return {
        'summary': {
            'student_name': student.name,
            'school_year_name': school_year.name,
            **_summarize_attendance(records),
        },
        'daily_records': [
            {
                'date': record.date.isoformat(),
                'status': record.status.value,
                'instructional_hours': float(record.instructional_hours or 0),
                'check_in_time': record.check_in_time.isoformat() if record.check_in_time else None,
                'check_out_time': record.check_out_time.isoformat() if record.check_out_time else None,
                'notes': record.notes,
            }
            for record in records
        ],
    }


async def _build_portfolio_review_data(
    db: AsyncSession,
    *,
    family_id: int,
    student: Student,
    school_year: SchoolYear,
) -> dict[str, Any]:
    start_date, end_date = _date_range_for_school_year(school_year)
    entries = (
        await db.execute(
            select(PortfolioEntry)
            .options(selectinload(PortfolioEntry.subject))
            .where(
                PortfolioEntry.family_id == family_id,
                PortfolioEntry.student_id == student.id,
                PortfolioEntry.date >= start_date,
                PortfolioEntry.date <= end_date,
            )
            .order_by(PortfolioEntry.date.asc(), PortfolioEntry.id.asc())
        )
    ).scalars().all()
    counts: dict[str, int] = defaultdict(int)
    for entry in entries:
        counts[entry.entry_type.value] += 1
    return {
        'summary': {
            'student_name': student.name,
            'school_year_name': school_year.name,
            'entry_count': len(entries),
            'counts_by_type': dict(sorted(counts.items())),
        },
        'entries': [
            {
                'id': entry.id,
                'date': entry.date.isoformat(),
                'entry_type': entry.entry_type.value,
                'title': entry.title,
                'subject_name': entry.subject.name if entry.subject else None,
                'tag_count': len(entry.tags or []),
                'attachment_count': len(entry.attachments or []),
                'tags': entry.tags or [],
            }
            for entry in entries
        ],
    }


async def _build_notice_of_intent_data(
    db: AsyncSession,
    *,
    family_id: int,
    student: Student,
    school_year: SchoolYear,
    state_code: str,
) -> dict[str, Any]:
    family = (await db.execute(select(Family).where(Family.id == family_id))).scalar_one_or_none()
    subject_names = list((await db.execute(select(Subject.name).where(Subject.family_id == family_id).order_by(Subject.name.asc()))).scalars().all())
    return {
        'template': {
            'title': f'Notice of Intent to Homeschool — {state_code}',
            'generated_on': datetime.now(UTC).date().isoformat(),
            'state_code': state_code,
            'school_year_name': school_year.name,
            'family_name': family.name if family else 'Family',
            'student_name': student.name,
            'subjects': subject_names,
            'body': [
                f'This notice confirms intent to provide home instruction for {student.name} during {school_year.name}.',
                f'The family will maintain records and coursework aligned with {state_code} homeschool expectations.',
                'Attached summaries may include attendance, portfolio artifacts, and annual assessment documentation.',
            ],
        }
    }


async def generate_compliance_report(
    db: AsyncSession,
    *,
    family_id: int,
    student_id: int,
    school_year_id: int,
    report_type: ComplianceReportType,
    generated_by_user_id: int | None,
    grading_period_id: int | None = None,
    notes: str | None = None,
) -> ComplianceReport:
    student, school_year, grading_period = await _load_generation_context(
        db,
        family_id=family_id,
        student_id=student_id,
        school_year_id=school_year_id,
        grading_period_id=grading_period_id,
    )
    state_code = await get_family_state_code(db, family_id=family_id)
    if report_type == ComplianceReportType.annual_assessment:
        data = await _build_annual_assessment_data(
            db,
            family_id=family_id,
            student=student,
            school_year=school_year,
            state_code=state_code,
        )
    elif report_type == ComplianceReportType.quarterly_report:
        data = await _build_quarterly_report_data(
            db,
            family_id=family_id,
            student=student,
            school_year=school_year,
            grading_period=grading_period,
        )
    elif report_type == ComplianceReportType.attendance_log:
        data = await _build_attendance_log_data(db, family_id=family_id, student=student, school_year=school_year)
    elif report_type == ComplianceReportType.portfolio_review:
        data = await _build_portfolio_review_data(db, family_id=family_id, student=student, school_year=school_year)
    else:
        data = await _build_notice_of_intent_data(
            db,
            family_id=family_id,
            student=student,
            school_year=school_year,
            state_code=state_code,
        )

    report = ComplianceReport(
        family_id=family_id,
        student_id=student.id,
        school_year_id=school_year.id,
        state_code=state_code,
        report_type=report_type,
        generated_at=datetime.now(UTC),
        generated_by_user_id=generated_by_user_id,
        status=ComplianceReportStatus.draft,
        data=data,
        notes=notes,
    )
    db.add(report)
    await db.flush()
    refreshed = await get_compliance_report(db, family_id=family_id, report_id=report.id)
    assert refreshed is not None
    return refreshed


async def finalize_compliance_report(db: AsyncSession, *, report: ComplianceReport) -> ComplianceReport:
    if report.status == ComplianceReportStatus.submitted:
        raise ValueError('Submitted compliance reports cannot be changed')
    if report.status != ComplianceReportStatus.final:
        report.status = ComplianceReportStatus.final
        report.generated_at = datetime.now(UTC)
        await db.flush()
    refreshed = await get_compliance_report(db, family_id=report.family_id, report_id=report.id)
    assert refreshed is not None
    return refreshed


async def list_required_reports(
    db: AsyncSession,
    *,
    family_id: int,
    state_code: str,
    student_id: int | None = None,
    school_year_id: int | None = None,
) -> list[dict[str, Any]]:
    definitions = STATE_REQUIRED_REPORTS.get(state_code.upper(), DEFAULT_REQUIRED_REPORTS)
    stmt = select(ComplianceReport.report_type, ComplianceReport.status, func.count(ComplianceReport.id)).where(
        ComplianceReport.family_id == family_id,
        ComplianceReport.state_code == state_code.upper(),
    )
    if student_id is not None:
        stmt = stmt.where(ComplianceReport.student_id == student_id)
    if school_year_id is not None:
        stmt = stmt.where(ComplianceReport.school_year_id == school_year_id)
    stmt = stmt.group_by(ComplianceReport.report_type, ComplianceReport.status)
    counts = defaultdict(lambda: {'generated': 0, 'completed': 0})
    for report_type, status, total in (await db.execute(stmt)).all():
        counts[report_type]['generated'] += int(total)
        if status in {ComplianceReportStatus.final, ComplianceReportStatus.submitted}:
            counts[report_type]['completed'] += int(total)

    items: list[dict[str, Any]] = []
    for definition in definitions:
        generated = counts[definition.report_type]['generated']
        completed = counts[definition.report_type]['completed']
        outstanding = max(definition.required_count - completed, 0)
        items.append(
            {
                'report_type': definition.report_type,
                'label': definition.label,
                'description': definition.description,
                'cadence': definition.cadence,
                'required_count': definition.required_count,
                'generated_count': generated,
                'completed_count': completed,
                'outstanding_count': outstanding,
                'is_complete': outstanding == 0,
            }
        )
    return items


def _table(data: list[list[Any]], *, widths: Sequence[float], header_color: colors.Color) -> Table:
    table = Table(data, repeatRows=1, colWidths=list(widths))
    table.setStyle(
        TableStyle(
            [
                ('BACKGROUND', (0, 0), (-1, 0), header_color),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')]),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('LEFTPADDING', (0, 0), (-1, -1), 6),
                ('RIGHTPADDING', (0, 0), (-1, -1), 6),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ]
        )
    )
    return table


def build_compliance_report_pdf(report: ComplianceReport) -> bytes:
    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=0.6 * inch,
        leftMargin=0.6 * inch,
        topMargin=0.6 * inch,
        bottomMargin=0.6 * inch,
    )
    styles = getSampleStyleSheet()
    body = styles['BodyText']
    body.spaceAfter = 6
    subtitle = styles['Heading3']
    small = ParagraphStyle('small', parent=styles['BodyText'], fontSize=9, leading=12)

    story: list[Any] = [
        Paragraph(report_type_label(report.report_type), styles['Title']),
        Paragraph(
            f"{report.family.name if report.family else 'Family'} &middot; {report.student.name if report.student else 'Student'}",
            subtitle,
        ),
        Paragraph(
            f"<b>State:</b> {report.state_code} &nbsp;&nbsp; <b>School year:</b> {report.school_year.name if report.school_year else 'School Year'}"
            f" &nbsp;&nbsp; <b>Status:</b> {report.status.value.title()}",
            body,
        ),
        Paragraph(
            f"<b>Generated:</b> {_format_datetime(report.generated_at)}"
            + (f" &nbsp;&nbsp; <b>By:</b> {report.generated_by.display_name}" if report.generated_by else ''),
            small,
        ),
        Spacer(1, 0.15 * inch),
    ]
    data = report.data or {}

    if report.report_type == ComplianceReportType.annual_assessment:
        summary = data.get('summary') or {}
        story.append(
            Paragraph(
                f"<b>Overall average:</b> {summary.get('overall_percent', '—')} &nbsp;&nbsp; "
                f"<b>Subjects:</b> {summary.get('subject_count', 0)} &nbsp;&nbsp; "
                f"<b>Tests:</b> {summary.get('test_count', 0)}",
                body,
            )
        )
        subject_rows = [['Subject', 'Percent', 'Letter', 'GPA', 'Assignments']]
        for item in data.get('subject_grades', []):
            subject_rows.append(
                [
                    item.get('subject_name', 'Subject'),
                    f"{item.get('overall_percent', '—')}%" if item.get('overall_percent') is not None else '—',
                    item.get('letter_grade') or '—',
                    f"{float(item.get('gpa_points')):.2f}" if item.get('gpa_points') is not None else '—',
                    str(item.get('graded_assignments') or item.get('assignment_count') or 0),
                ]
            )
        story.extend(
            [
                Paragraph('Subject grades', subtitle),
                _table(subject_rows, widths=[2.2 * inch, 1.0 * inch, 0.8 * inch, 0.7 * inch, 1.1 * inch], header_color=colors.HexColor('#1d4ed8')),
                Spacer(1, 0.18 * inch),
            ]
        )
        test_rows = [['Assessment', 'Subject', 'Date', 'Score', 'Percent']]
        for item in data.get('test_scores', []):
            test_rows.append(
                [
                    item.get('title', 'Assessment'),
                    item.get('subject_name', 'General'),
                    item.get('date') or '—',
                    f"{item.get('score', 0):.0f}/{item.get('max_score', 0):.0f}",
                    f"{item.get('percent', '—')}%" if item.get('percent') is not None else '—',
                ]
            )
        story.extend(
            [
                Paragraph('Assessment evidence', subtitle),
                _table(test_rows, widths=[2.3 * inch, 1.4 * inch, 1.0 * inch, 0.9 * inch, 0.8 * inch], header_color=colors.HexColor('#0f766e')),
                Spacer(1, 0.18 * inch),
            ]
        )
        coverage = data.get('subject_coverage') or {}
        story.append(
            Paragraph(
                '<b>Subject coverage:</b> '
                + (', '.join(coverage.get('subjects') or []) or 'No subjects recorded')
                + (
                    f"<br/><b>Missing required subjects:</b> {', '.join(coverage.get('missing_subjects') or [])}"
                    if coverage.get('missing_subjects')
                    else ''
                ),
                body,
            )
        )
    elif report.report_type == ComplianceReportType.quarterly_report:
        period = data.get('period') or {}
        story.append(
            Paragraph(
                f"<b>Period:</b> {period.get('term_name') or ''} {period.get('name') or ''} "
                f"({period.get('start_date')} to {period.get('end_date')})",
                body,
            )
        )
        subject_rows = [['Subject', 'Percent', 'Letter', 'GPA']]
        for item in data.get('subject_grades', []):
            subject_rows.append(
                [
                    item.get('subject_name', 'Subject'),
                    f"{item.get('overall_percent', '—')}%" if item.get('overall_percent') is not None else '—',
                    item.get('letter_grade') or '—',
                    f"{float(item.get('gpa_points')):.2f}" if item.get('gpa_points') is not None else '—',
                ]
            )
        story.extend(
            [
                Paragraph('Quarter grades', subtitle),
                _table(subject_rows, widths=[2.8 * inch, 1.0 * inch, 0.9 * inch, 0.7 * inch], header_color=colors.HexColor('#7c3aed')),
                Spacer(1, 0.18 * inch),
            ]
        )
        attendance = data.get('attendance_summary') or {}
        attendance_rows = [
            ['Metric', 'Value'],
            ['Days recorded', str(attendance.get('total_records', 0))],
            ['Attendance rate', f"{float(attendance.get('attendance_rate', 0)):.1f}%"],
            ['Instructional hours', f"{float(attendance.get('total_hours', 0)):.2f}"],
        ]
        story.extend(
            [
                Paragraph('Attendance summary', subtitle),
                _table(attendance_rows, widths=[2.4 * inch, 1.4 * inch], header_color=colors.HexColor('#0f172a')),
            ]
        )
    elif report.report_type == ComplianceReportType.attendance_log:
        summary = data.get('summary') or {}
        story.append(
            Paragraph(
                f"<b>Recorded days:</b> {summary.get('total_records', 0)} &nbsp;&nbsp; "
                f"<b>Total hours:</b> {float(summary.get('total_hours', 0)):.2f} &nbsp;&nbsp; "
                f"<b>Attendance rate:</b> {float(summary.get('attendance_rate', 0)):.1f}%",
                body,
            )
        )
        rows = [['Date', 'Status', 'Hours', 'Check in/out', 'Notes']]
        for record in data.get('daily_records', []):
            rows.append(
                [
                    record.get('date', '—'),
                    str(record.get('status', '—')).replace('_', ' ').title(),
                    f"{float(record.get('instructional_hours', 0)):.2f}",
                    ' / '.join(filter(None, [record.get('check_in_time') or '', record.get('check_out_time') or ''])) or '—',
                    record.get('notes') or '—',
                ]
            )
        story.extend(
            [
                Spacer(1, 0.12 * inch),
                Paragraph('Daily attendance records', subtitle),
                _table(rows, widths=[1.0 * inch, 1.1 * inch, 0.6 * inch, 1.2 * inch, 2.2 * inch], header_color=colors.HexColor('#1d4ed8')),
            ]
        )
    elif report.report_type == ComplianceReportType.portfolio_review:
        summary = data.get('summary') or {}
        counts = summary.get('counts_by_type') or {}
        story.append(
            Paragraph(
                f"<b>Total entries:</b> {summary.get('entry_count', 0)}<br/><b>Counts by type:</b> "
                + ', '.join(f"{key.replace('_', ' ')} {value}" for key, value in counts.items()),
                body,
            )
        )
        rows = [['Date', 'Type', 'Title', 'Subject', 'Attachments']]
        for entry in data.get('entries', []):
            rows.append(
                [
                    entry.get('date', '—'),
                    str(entry.get('entry_type', '—')).replace('_', ' ').title(),
                    entry.get('title', 'Untitled'),
                    entry.get('subject_name') or '—',
                    str(entry.get('attachment_count', 0)),
                ]
            )
        story.extend(
            [
                Paragraph('Portfolio entries', subtitle),
                _table(rows, widths=[1.0 * inch, 1.1 * inch, 2.4 * inch, 1.2 * inch, 0.7 * inch], header_color=colors.HexColor('#0f766e')),
            ]
        )
    else:
        template = data.get('template') or {}
        story.append(Paragraph(template.get('title', 'Notice of intent'), subtitle))
        for paragraph in template.get('body', []):
            story.append(Paragraph(paragraph, body))
        if template.get('subjects'):
            story.append(Paragraph(f"<b>Subjects:</b> {', '.join(template['subjects'])}", body))

    if report.notes:
        story.extend([Spacer(1, 0.1 * inch), Paragraph(f"<b>Notes:</b> {report.notes}", body)])

    document.build(story)
    return buffer.getvalue()
