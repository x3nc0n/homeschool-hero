from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, date, datetime
from decimal import Decimal
from io import BytesIO
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy import and_, delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.models import (
    Assignment,
    AttendanceRecord,
    AttendanceStatus,
    Grade,
    GradingPeriod,
    ReportCard,
    ReportCardEntry,
    ReportCardStatus,
    Student,
    Subject,
    Submission,
)
from backend.models.calendar import SchoolYear, Term
from backend.services.gradebook import calculate_gradebook


def _attendance_rate(*, present: int, tardy: int, excused: int, total_records: int) -> float:
    if total_records <= 0:
        return 0.0
    attended = present + tardy + excused
    return round((attended / total_records) * 100, 2)


def _sum_hours(records: Sequence[AttendanceRecord]) -> Decimal:
    return sum((record.instructional_hours for record in records), Decimal('0')).quantize(Decimal('0.01'))


def summarize_attendance_records(records: Sequence[AttendanceRecord], *, start_date: date, end_date: date) -> dict[str, Any]:
    present = sum(1 for record in records if record.status == AttendanceStatus.present)
    absent = sum(1 for record in records if record.status == AttendanceStatus.absent)
    tardy = sum(1 for record in records if record.status == AttendanceStatus.tardy)
    excused = sum(1 for record in records if record.status == AttendanceStatus.excused)
    total_hours = _sum_hours(records)
    return {
        'start_date': start_date.isoformat(),
        'end_date': end_date.isoformat(),
        'total_records': len(records),
        'present': present,
        'absent': absent,
        'tardy': tardy,
        'excused': excused,
        'attendance_rate': _attendance_rate(
            present=present,
            tardy=tardy,
            excused=excused,
            total_records=len(records),
        ),
        'total_hours': float(total_hours),
    }


def _report_card_options():
    return (
        selectinload(ReportCard.family),
        selectinload(ReportCard.student),
        selectinload(ReportCard.school_year),
        selectinload(ReportCard.grading_period).selectinload(GradingPeriod.term),
        selectinload(ReportCard.generated_by),
        selectinload(ReportCard.entries).selectinload(ReportCardEntry.subject),
    )


def calculate_report_card_metrics(report_card: ReportCard) -> tuple[float | None, float | None]:
    gpa_values = [entry.gpa_points for entry in report_card.entries if entry.gpa_points is not None]
    percentages = [entry.percentage for entry in report_card.entries if entry.percentage is not None]
    gpa = round(sum(gpa_values) / len(gpa_values), 2) if gpa_values else None
    overall_percentage = round(sum(percentages) / len(percentages), 2) if percentages else None
    return gpa, overall_percentage


def overall_standing_for_percentage(value: float | None) -> str:
    if value is None:
        return 'In progress'
    if value >= 90:
        return 'Excellent'
    if value >= 80:
        return 'Good standing'
    if value >= 70:
        return 'Satisfactory'
    if value >= 60:
        return 'Needs support'
    return 'Intervention needed'


def _format_datetime(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).strftime('%Y-%m-%d %H:%M UTC')


def report_card_to_summary(report_card: ReportCard) -> dict[str, Any]:
    gpa, overall_percentage = calculate_report_card_metrics(report_card)
    return {
        'id': report_card.id,
        'family_id': report_card.family_id,
        'student_id': report_card.student_id,
        'school_year_id': report_card.school_year_id,
        'grading_period_id': report_card.grading_period_id,
        'generated_at': report_card.generated_at,
        'generated_by_user_id': report_card.generated_by_user_id,
        'generated_by_name': report_card.generated_by.display_name if report_card.generated_by else None,
        'status': report_card.status,
        'notes': report_card.notes,
        'student_name': report_card.student.name if report_card.student else '',
        'school_year_name': report_card.school_year.name if report_card.school_year else '',
        'grading_period_name': report_card.grading_period.name if report_card.grading_period else '',
        'entry_count': len(report_card.entries),
        'gpa': gpa,
        'overall_percentage': overall_percentage,
    }


def report_card_to_read(report_card: ReportCard) -> dict[str, Any]:
    payload = report_card_to_summary(report_card)
    payload['student'] = report_card.student
    payload['entries'] = report_card.entries
    return payload


async def get_report_card(
    db: AsyncSession,
    *,
    family_id: int,
    report_card_id: int,
) -> ReportCard | None:
    result = await db.execute(
        select(ReportCard)
        .options(*_report_card_options())
        .where(ReportCard.id == report_card_id, ReportCard.family_id == family_id)
    )
    return result.scalar_one_or_none()


async def list_report_cards(
    db: AsyncSession,
    *,
    family_id: int,
    student_id: int | None = None,
    grading_period_id: int | None = None,
    status: ReportCardStatus | None = None,
) -> list[ReportCard]:
    stmt = select(ReportCard).options(*_report_card_options()).where(ReportCard.family_id == family_id)
    if student_id is not None:
        stmt = stmt.where(ReportCard.student_id == student_id)
    if grading_period_id is not None:
        stmt = stmt.where(ReportCard.grading_period_id == grading_period_id)
    if status is not None:
        stmt = stmt.where(ReportCard.status == status)
    stmt = stmt.order_by(ReportCard.generated_at.desc(), ReportCard.id.desc())
    return list((await db.execute(stmt)).scalars().all())


async def _get_attendance_records_for_period(
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


async def _load_generation_context(
    db: AsyncSession,
    *,
    family_id: int,
    student_id: int,
    grading_period_id: int,
) -> tuple[Student, GradingPeriod, SchoolYear]:
    student = (
        await db.execute(select(Student).where(Student.id == student_id, Student.family_id == family_id))
    ).scalar_one_or_none()
    if student is None:
        raise ValueError('Student not found')

    grading_period = (
        await db.execute(
            select(GradingPeriod)
            .options(selectinload(GradingPeriod.term).selectinload(Term.school_year))
            .where(GradingPeriod.id == grading_period_id, GradingPeriod.family_id == family_id)
        )
    ).scalar_one_or_none()
    if grading_period is None:
        raise ValueError('Grading period not found')
    if grading_period.term is None or grading_period.term.school_year is None:
        raise ValueError('Grading period is missing school year context')
    return student, grading_period, grading_period.term.school_year


async def _teacher_comments_by_subject(
    db: AsyncSession,
    *,
    family_id: int,
    student_id: int,
    grading_period_id: int,
) -> dict[int, str]:
    rows = (
        await db.execute(
            select(Subject.id, Grade.notes)
            .join(Assignment, Assignment.subject_id == Subject.id)
            .join(
                Submission,
                and_(
                    Submission.assignment_id == Assignment.id,
                    Submission.student_id == student_id,
                    Submission.is_current.is_(True),
                ),
            )
            .join(Grade, Grade.submission_id == Submission.id)
            .where(
                Subject.family_id == family_id,
                Assignment.grading_period_id == grading_period_id,
                Grade.notes.is_not(None),
            )
            .order_by(Subject.id, Grade.created_at.desc())
        )
    ).all()
    comments: dict[int, list[str]] = {}
    for subject_id, note in rows:
        normalized = str(note or '').strip()
        if not normalized:
            continue
        comments.setdefault(subject_id, [])
        if normalized not in comments[subject_id]:
            comments[subject_id].append(normalized)
    return {subject_id: ' | '.join(values[:3]) for subject_id, values in comments.items()}


async def generate_report_card(
    db: AsyncSession,
    *,
    family_id: int,
    student_id: int,
    grading_period_id: int,
    generated_by_user_id: int | None,
    notes: str | None = None,
) -> ReportCard:
    student, grading_period, school_year = await _load_generation_context(
        db,
        family_id=family_id,
        student_id=student_id,
        grading_period_id=grading_period_id,
    )

    existing_final = (
        await db.execute(
            select(ReportCard).where(
                ReportCard.family_id == family_id,
                ReportCard.student_id == student_id,
                ReportCard.grading_period_id == grading_period_id,
                ReportCard.status == ReportCardStatus.final,
            )
        )
    ).scalar_one_or_none()
    if existing_final is not None:
        raise ValueError('A final report card already exists for this grading period')

    report_card = (
        await db.execute(
            select(ReportCard)
            .options(selectinload(ReportCard.entries))
            .where(
                ReportCard.family_id == family_id,
                ReportCard.student_id == student_id,
                ReportCard.grading_period_id == grading_period_id,
                ReportCard.status == ReportCardStatus.draft,
            )
            .order_by(ReportCard.id.desc())
        )
    ).scalars().first()
    if report_card is None:
        report_card = ReportCard(
            family_id=family_id,
            student_id=student.id,
            school_year_id=school_year.id,
            grading_period_id=grading_period.id,
        )
        db.add(report_card)

    gradebook = await calculate_gradebook(
        db,
        family_id=family_id,
        student_id=student_id,
        grading_period_id=grading_period_id,
    )
    attendance_records = await _get_attendance_records_for_period(
        db,
        family_id=family_id,
        student_id=student_id,
        start_date=grading_period.start_date,
        end_date=grading_period.end_date,
    )
    attendance_summary = summarize_attendance_records(
        attendance_records,
        start_date=grading_period.start_date,
        end_date=grading_period.end_date,
    )
    comment_map = await _teacher_comments_by_subject(
        db,
        family_id=family_id,
        student_id=student_id,
        grading_period_id=grading_period_id,
    )

    report_card.school_year_id = school_year.id
    report_card.generated_by_user_id = generated_by_user_id
    report_card.generated_at = datetime.now(UTC)
    report_card.status = ReportCardStatus.draft
    report_card.notes = notes if notes is not None else report_card.notes
    await db.flush()

    preserved_comments: dict[int, str | None] = {}
    if report_card.id is not None:
        existing_entries = (
            await db.execute(select(ReportCardEntry).where(ReportCardEntry.report_card_id == report_card.id))
        ).scalars().all()
        preserved_comments = {entry.subject_id: entry.teacher_comments for entry in existing_entries}
        await db.execute(delete(ReportCardEntry).where(ReportCardEntry.report_card_id == report_card.id))
    await db.flush()

    subject_ids = [subject['subject_id'] for subject in gradebook['subjects']]
    new_entries: list[ReportCardEntry] = []
    for subject in gradebook['subjects']:
        category_breakdown = {
            category['name']: round(float(category['average_percent']), 2)
            for category in subject['categories']
            if category['average_percent'] is not None
        }
        new_entries.append(
            ReportCardEntry(
                report_card_id=report_card.id,
                subject_id=subject['subject_id'],
                letter_grade=subject['letter_grade'],
                percentage=subject['overall_percent'],
                gpa_points=subject['gpa_points'],
                attendance_summary=dict(attendance_summary),
                teacher_comments=preserved_comments.get(subject['subject_id']) or comment_map.get(subject['subject_id']),
                category_breakdown=category_breakdown,
            )
        )
    db.add_all(new_entries)

    await db.flush()
    refreshed = await get_report_card(db, family_id=family_id, report_card_id=report_card.id)
    assert refreshed is not None
    return refreshed


async def update_report_card(
    db: AsyncSession,
    *,
    report_card: ReportCard,
    notes: str | None | object = ...,
    status: ReportCardStatus | None = None,
    entry_comments: dict[int, str | None] | None = None,
) -> ReportCard:
    if report_card.status == ReportCardStatus.final:
        if status == ReportCardStatus.archived and notes is ... and not entry_comments:
            report_card.status = ReportCardStatus.archived
        else:
            raise ValueError('Final report cards are immutable')
    elif report_card.status == ReportCardStatus.archived:
        raise ValueError('Archived report cards cannot be changed')
    else:
        if notes is not ...:
            report_card.notes = notes
        if status is not None:
            report_card.status = status
        if entry_comments:
            entries_by_id = {entry.id: entry for entry in report_card.entries}
            for entry_id, teacher_comments in entry_comments.items():
                entry = entries_by_id.get(entry_id)
                if entry is None:
                    raise ValueError('Report card entry not found')
                entry.teacher_comments = teacher_comments
    await db.flush()
    refreshed = await get_report_card(db, family_id=report_card.family_id, report_card_id=report_card.id)
    assert refreshed is not None
    return refreshed


async def finalize_report_card(db: AsyncSession, *, report_card: ReportCard) -> ReportCard:
    if report_card.status == ReportCardStatus.final:
        return report_card
    if report_card.status == ReportCardStatus.archived:
        raise ValueError('Archived report cards cannot be finalized')
    report_card.status = ReportCardStatus.final
    report_card.generated_at = datetime.now(UTC)
    await db.flush()
    refreshed = await get_report_card(db, family_id=report_card.family_id, report_card_id=report_card.id)
    assert refreshed is not None
    return refreshed


def build_report_card_pdf(report_card: ReportCard) -> bytes:
    gpa, overall_percentage = calculate_report_card_metrics(report_card)
    family_name = report_card.family.name if report_card.family else 'Family'
    student_name = report_card.student.name if report_card.student else 'Student'
    school_year_name = report_card.school_year.name if report_card.school_year else 'School Year'
    grading_period_name = report_card.grading_period.name if report_card.grading_period else 'Grading Period'
    attendance = report_card.entries[0].attendance_summary if report_card.entries else {}

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
    title_style = styles['Title']
    subtitle_style = styles['Heading3']
    body_style = styles['BodyText']
    body_style.spaceAfter = 6
    small_style = ParagraphStyle('small', parent=styles['BodyText'], fontSize=9, leading=12)

    story: list[Any] = [
        Paragraph('Report Card', title_style),
        Paragraph(f'{family_name} &middot; {student_name}', subtitle_style),
        Paragraph(
            f'<b>School year:</b> {school_year_name} &nbsp;&nbsp; <b>Grading period:</b> {grading_period_name}'
            f' &nbsp;&nbsp; <b>Status:</b> {report_card.status.value.title()}',
            body_style,
        ),
        Paragraph(
            f'<b>Generated:</b> {_format_datetime(report_card.generated_at)}'
            + (
                f' &nbsp;&nbsp; <b>By:</b> {report_card.generated_by.display_name}'
                if report_card.generated_by is not None
                else ''
            ),
            small_style,
        ),
        Spacer(1, 0.15 * inch),
    ]

    table_rows = [['Subject', 'Grade', 'Percent', 'GPA', 'Categories', 'Comments']]
    for entry in report_card.entries:
        categories = ', '.join(
            f'{name.replace("_", " ").title()}: {value:.1f}%'
            for name, value in sorted((entry.category_breakdown or {}).items())
        ) or '—'
        table_rows.append(
            [
                entry.subject.name if entry.subject else f'Subject {entry.subject_id}',
                entry.letter_grade or '—',
                f'{entry.percentage:.1f}%' if entry.percentage is not None else '—',
                f'{entry.gpa_points:.2f}' if entry.gpa_points is not None else '—',
                categories,
                entry.teacher_comments or '—',
            ]
        )

    grade_table = Table(table_rows, repeatRows=1, colWidths=[1.2 * inch, 0.65 * inch, 0.8 * inch, 0.55 * inch, 2.0 * inch, 1.5 * inch])
    grade_table.setStyle(
        TableStyle(
            [
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1d4ed8')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')]),
                ('LEFTPADDING', (0, 0), (-1, -1), 6),
                ('RIGHTPADDING', (0, 0), (-1, -1), 6),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.extend([grade_table, Spacer(1, 0.2 * inch)])

    attendance_rows = [
        ['Attendance summary', 'Value'],
        ['Days recorded', str(attendance.get('total_records', 0))],
        ['Present', str(attendance.get('present', 0))],
        ['Absent', str(attendance.get('absent', 0))],
        ['Tardy', str(attendance.get('tardy', 0))],
        ['Excused', str(attendance.get('excused', 0))],
        ['Attendance rate', f"{float(attendance.get('attendance_rate', 0)):.1f}%"],
        ['Instructional hours', f"{float(attendance.get('total_hours', 0)):.2f}"],
    ]
    attendance_table = Table(attendance_rows, colWidths=[2.2 * inch, 1.4 * inch])
    attendance_table.setStyle(
        TableStyle(
            [
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0f172a')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')]),
                ('LEFTPADDING', (0, 0), (-1, -1), 6),
                ('RIGHTPADDING', (0, 0), (-1, -1), 6),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.extend(
        [
            Paragraph('Attendance and standing', subtitle_style),
            attendance_table,
            Spacer(1, 0.15 * inch),
            Paragraph(
                f'<b>Overall GPA:</b> {gpa:.2f}' if gpa is not None else '<b>Overall GPA:</b> —',
                body_style,
            ),
            Paragraph(
                f'<b>Overall standing:</b> {overall_standing_for_percentage(overall_percentage)}',
                body_style,
            ),
        ]
    )
    if report_card.notes:
        story.extend([Spacer(1, 0.1 * inch), Paragraph(f'<b>Notes:</b> {report_card.notes}', body_style)])

    document.build(story)
    return buffer.getvalue()
