from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from datetime import UTC, datetime
from decimal import Decimal, ROUND_HALF_UP
from io import BytesIO
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy import and_, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.models import (
    Assignment,
    Family,
    Grade,
    GradeScale,
    GradingPeriod,
    SchoolYear,
    Student,
    Subject,
    Submission,
    Transcript,
    TranscriptEntry,
    TranscriptStatus,
)
from backend.models.calendar import Term
from backend.services.gradebook import (
    _build_subject_view,
    build_default_grade_categories,
    ensure_default_grade_scale,
    map_percent_to_grade,
)

_ZERO = Decimal('0.00')


def _to_decimal(value: Decimal | float | int | None, *, default: str = '0.00') -> Decimal:
    if value is None:
        return Decimal(default)
    if isinstance(value, Decimal):
        return value.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    return Decimal(str(value)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def _float_or_none(value: Decimal | float | None) -> float | None:
    if value is None:
        return None
    return float(_to_decimal(value))


def transcript_weight_config(family: Family | None) -> tuple[float, float, Decimal]:
    settings = family.settings if family and isinstance(family.settings, dict) else {}
    honors_bonus = round(float(settings.get('transcript_honors_weight_bonus', 0.5)), 2)
    ap_bonus = round(float(settings.get('transcript_ap_weight_bonus', 1.0)), 2)
    default_credits = _to_decimal(settings.get('transcript_default_credits', 1.0), default='1.00')
    return honors_bonus, ap_bonus, default_credits


def transcript_entry_weighted_points(entry: TranscriptEntry, *, honors_bonus: float, ap_bonus: float) -> float | None:
    if entry.gpa_points is None:
        return None
    bonus = 0.0
    if entry.is_honors:
        bonus += honors_bonus
    if entry.is_ap:
        bonus += ap_bonus
    return round(float(entry.gpa_points) + bonus, 2)


def calculate_transcript_metrics(
    entries: Sequence[TranscriptEntry],
    *,
    honors_bonus: float,
    ap_bonus: float,
) -> tuple[float | None, float | None, Decimal]:
    total_credits = sum((_to_decimal(entry.credits) for entry in entries), _ZERO)
    cumulative_points = Decimal('0')
    weighted_points = Decimal('0')
    graded_credits = Decimal('0')
    weighted_graded_credits = Decimal('0')
    for entry in entries:
        credits = _to_decimal(entry.credits)
        if credits <= 0 or entry.gpa_points is None:
            continue
        cumulative_points += Decimal(str(entry.gpa_points)) * credits
        graded_credits += credits
        weighted_value = transcript_entry_weighted_points(entry, honors_bonus=honors_bonus, ap_bonus=ap_bonus)
        if weighted_value is not None:
            weighted_points += Decimal(str(weighted_value)) * credits
            weighted_graded_credits += credits

    cumulative_gpa = round(float(cumulative_points / graded_credits), 2) if graded_credits > 0 else None
    weighted_gpa = round(float(weighted_points / weighted_graded_credits), 2) if weighted_graded_credits > 0 else None
    return cumulative_gpa, weighted_gpa, total_credits.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def _transcript_options():
    return (
        selectinload(Transcript.family),
        selectinload(Transcript.student),
        selectinload(Transcript.generated_by),
        selectinload(Transcript.entries).selectinload(TranscriptEntry.school_year),
        selectinload(Transcript.entries).selectinload(TranscriptEntry.subject),
    )


def _format_datetime(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).strftime('%Y-%m-%d %H:%M UTC')


def transcript_to_summary(transcript: Transcript) -> dict[str, Any]:
    return {
        'id': transcript.id,
        'family_id': transcript.family_id,
        'student_id': transcript.student_id,
        'generated_at': transcript.generated_at,
        'generated_by_user_id': transcript.generated_by_user_id,
        'generated_by_name': transcript.generated_by.display_name if transcript.generated_by else None,
        'status': transcript.status,
        'cumulative_gpa': transcript.cumulative_gpa,
        'weighted_gpa': transcript.weighted_gpa,
        'total_credits': _float_or_none(transcript.total_credits) or 0.0,
        'notes': transcript.notes,
        'student_name': transcript.student.name if transcript.student else '',
        'entry_count': len(transcript.entries),
    }


def transcript_to_read(
    transcript: Transcript,
    *,
    class_rank: int | None = None,
    class_size: int | None = None,
) -> dict[str, Any]:
    honors_bonus, ap_bonus, _ = transcript_weight_config(transcript.family)
    payload = transcript_to_summary(transcript)
    payload.update(
        {
            'student': transcript.student,
            'class_rank': class_rank,
            'class_size': class_size,
            'honors_weight_bonus': honors_bonus,
            'ap_weight_bonus': ap_bonus,
            'entries': [
                {
                    'id': entry.id,
                    'transcript_id': entry.transcript_id,
                    'school_year_id': entry.school_year_id,
                    'school_year_name': entry.school_year.name if entry.school_year else f'School Year {entry.school_year_id}',
                    'subject_id': entry.subject_id,
                    'subject_name': entry.subject_name,
                    'credits': _float_or_none(entry.credits) or 0.0,
                    'letter_grade': entry.letter_grade,
                    'gpa_points': entry.gpa_points,
                    'weighted_gpa_points': transcript_entry_weighted_points(entry, honors_bonus=honors_bonus, ap_bonus=ap_bonus),
                    'is_honors': entry.is_honors,
                    'is_ap': entry.is_ap,
                    'notes': entry.notes,
                }
                for entry in transcript.entries
            ],
        }
    )
    return payload


async def get_transcript(
    db: AsyncSession,
    *,
    family_id: int,
    transcript_id: int,
) -> Transcript | None:
    result = await db.execute(
        select(Transcript)
        .options(*_transcript_options())
        .where(Transcript.id == transcript_id, Transcript.family_id == family_id)
    )
    return result.scalar_one_or_none()


async def list_transcripts(
    db: AsyncSession,
    *,
    family_id: int,
    student_id: int | None = None,
    status: TranscriptStatus | None = None,
) -> list[Transcript]:
    stmt = select(Transcript).options(*_transcript_options()).where(Transcript.family_id == family_id)
    if student_id is not None:
        stmt = stmt.where(Transcript.student_id == student_id)
    if status is not None:
        stmt = stmt.where(Transcript.status == status)
    stmt = stmt.order_by(Transcript.generated_at.desc(), Transcript.id.desc())
    return list((await db.execute(stmt)).scalars().all())


async def _load_generation_context(db: AsyncSession, *, family_id: int, student_id: int) -> tuple[Family, Student]:
    family = (await db.execute(select(Family).where(Family.id == family_id))).scalar_one_or_none()
    if family is None:
        raise ValueError('Family not found')
    student = (await db.execute(select(Student).where(Student.id == student_id, Student.family_id == family_id))).scalar_one_or_none()
    if student is None:
        raise ValueError('Student not found')
    return family, student


async def _load_transcript_rows(
    db: AsyncSession,
    *,
    family_id: int,
    student_id: int,
) -> list[tuple[Assignment, Subject, Submission, Grade, GradingPeriod, Term, SchoolYear]]:
    stmt = (
        select(Assignment, Subject, Submission, Grade, GradingPeriod, Term, SchoolYear)
        .join(Subject, Subject.id == Assignment.subject_id)
        .join(GradingPeriod, GradingPeriod.id == Assignment.grading_period_id)
        .join(Term, Term.id == GradingPeriod.term_id)
        .join(SchoolYear, SchoolYear.id == Term.school_year_id)
        .join(
            Submission,
            and_(
                Submission.assignment_id == Assignment.id,
                Submission.student_id == student_id,
                Submission.is_current.is_(True),
            ),
        )
        .join(Grade, Grade.submission_id == Submission.id)
        .where(Assignment.family_id == family_id)
        .order_by(SchoolYear.start_date, Subject.name, Assignment.due_date, Assignment.id)
    )
    return list((await db.execute(stmt)).all())


async def generate_transcript(
    db: AsyncSession,
    *,
    family_id: int,
    student_id: int,
    generated_by_user_id: int | None,
    notes: str | None = None,
) -> Transcript:
    family, student = await _load_generation_context(db, family_id=family_id, student_id=student_id)
    honors_bonus, ap_bonus, default_credits = transcript_weight_config(family)
    default_scale = await ensure_default_grade_scale(db, family_id)
    rows = await _load_transcript_rows(db, family_id=family_id, student_id=student_id)
    if not rows:
        raise ValueError('No graded coursework found for this student')

    subject_ids = sorted({row[1].id for row in rows})
    subject_result = await db.execute(
        select(Subject)
        .options(selectinload(Subject.grade_categories), selectinload(Subject.grade_scale))
        .where(Subject.id.in_(subject_ids))
    )
    subjects = {subject.id: subject for subject in subject_result.scalars().all()}

    transcript = (
        await db.execute(
            select(Transcript)
            .options(selectinload(Transcript.entries))
            .where(
                Transcript.family_id == family_id,
                Transcript.student_id == student_id,
                Transcript.status == TranscriptStatus.draft,
            )
            .order_by(Transcript.id.desc())
        )
    ).scalars().first()
    if transcript is None:
        transcript = Transcript(family_id=family_id, student_id=student.id)
        db.add(transcript)

    transcript.generated_by_user_id = generated_by_user_id
    transcript.generated_at = datetime.now(UTC)
    transcript.status = TranscriptStatus.draft
    transcript.notes = notes if notes is not None else transcript.notes
    await db.flush()

    preserved: dict[tuple[int, int], dict[str, Any]] = {}
    if transcript.id is not None:
        existing_entries = (
            await db.execute(select(TranscriptEntry).where(TranscriptEntry.transcript_id == transcript.id))
        ).scalars().all()
        preserved = {
            (entry.school_year_id, entry.subject_id): {
                'credits': entry.credits,
                'is_honors': entry.is_honors,
                'is_ap': entry.is_ap,
                'notes': entry.notes,
                'subject_name': entry.subject_name,
            }
            for entry in existing_entries
        }
        await db.execute(delete(TranscriptEntry).where(TranscriptEntry.transcript_id == transcript.id))
        await db.flush()

    items_by_year_subject: dict[tuple[int, int], list[dict[str, Any]]] = defaultdict(list)
    school_years: dict[int, SchoolYear] = {}
    for assignment, subject, submission, grade, grading_period, term, school_year in rows:
        school_years[school_year.id] = school_year
        percent = (float(grade.score) / float(grade.max_score)) * 100 if grade.max_score else None
        items_by_year_subject[(school_year.id, subject.id)].append(
            {
                'assignment_id': assignment.id,
                'assignment_title': assignment.title,
                'category': assignment.category.value,
                'grading_period_id': grading_period.id,
                'due_date': assignment.due_date,
                'status': assignment.status.value,
                'score': float(grade.score),
                'max_score': float(grade.max_score),
                'percent': percent,
                'letter_grade': grade.letter_grade,
                'submission_id': submission.id,
                'grade_id': grade.id,
                'graded_at': grade.created_at,
                'created_at': assignment.created_at,
                'is_dropped': False,
            }
        )

    new_entries: list[TranscriptEntry] = []
    for school_year_id, subject_id in sorted(
        items_by_year_subject,
        key=lambda key: (school_years[key[0]].start_date, subjects[key[1]].name.lower(), key[1]),
    ):
        current_subject = subjects[subject_id]
        subject_items = [dict(item) for item in items_by_year_subject[(school_year_id, subject_id)]]
        scale = current_subject.grade_scale or default_scale
        category_configs = (
            [
                {
                    'id': category.id,
                    'name': category.name,
                    'weight': category.weight,
                    'drop_lowest': category.drop_lowest or 0,
                }
                for category in current_subject.grade_categories
            ]
            if current_subject.grade_categories
            else build_default_grade_categories(item['category'] for item in subject_items)
        )
        view = _build_subject_view(
            subject=current_subject,
            scale=scale,
            category_configs=category_configs,
            items=subject_items,
        )
        override = preserved.get((school_year_id, subject_id), {})
        new_entries.append(
            TranscriptEntry(
                transcript_id=transcript.id,
                school_year_id=school_year_id,
                subject_id=subject_id,
                subject_name=str(override.get('subject_name') or current_subject.name),
                credits=_to_decimal(override.get('credits', default_credits), default='1.00'),
                letter_grade=view['letter_grade'],
                gpa_points=view['gpa_points'],
                is_honors=bool(override.get('is_honors', False)),
                is_ap=bool(override.get('is_ap', False)),
                notes=override.get('notes'),
            )
        )
    db.add_all(new_entries)
    await db.flush()

    cumulative_gpa, weighted_gpa, total_credits = calculate_transcript_metrics(
        new_entries,
        honors_bonus=honors_bonus,
        ap_bonus=ap_bonus,
    )
    transcript.cumulative_gpa = cumulative_gpa
    transcript.weighted_gpa = weighted_gpa
    transcript.total_credits = total_credits
    await db.flush()

    refreshed = await get_transcript(db, family_id=family_id, transcript_id=transcript.id)
    assert refreshed is not None
    return refreshed


async def update_transcript(
    db: AsyncSession,
    *,
    transcript: Transcript,
    notes: str | None | object = ...,
    status: TranscriptStatus | None = None,
    entry_updates: dict[int, dict[str, Any]] | None = None,
) -> Transcript:
    if transcript.status == TranscriptStatus.final:
        if status == TranscriptStatus.archived and notes is ... and not entry_updates:
            transcript.status = TranscriptStatus.archived
        else:
            raise ValueError('Final transcripts are immutable')
    elif transcript.status == TranscriptStatus.archived:
        raise ValueError('Archived transcripts cannot be changed')
    else:
        if notes is not ...:
            transcript.notes = notes
        if status is not None:
            transcript.status = status
        if entry_updates:
            entries_by_id = {entry.id: entry for entry in transcript.entries}
            for entry_id, update in entry_updates.items():
                entry = entries_by_id.get(entry_id)
                if entry is None:
                    raise ValueError('Transcript entry not found')
                if 'credits' in update and update['credits'] is not None:
                    entry.credits = _to_decimal(update['credits'], default='0.00')
                if 'is_honors' in update and update['is_honors'] is not None:
                    entry.is_honors = bool(update['is_honors'])
                if 'is_ap' in update and update['is_ap'] is not None:
                    entry.is_ap = bool(update['is_ap'])
                if 'notes' in update:
                    entry.notes = update['notes']
                if 'subject_name' in update and update['subject_name']:
                    entry.subject_name = str(update['subject_name'])

    honors_bonus, ap_bonus, _ = transcript_weight_config(transcript.family)
    cumulative_gpa, weighted_gpa, total_credits = calculate_transcript_metrics(
        transcript.entries,
        honors_bonus=honors_bonus,
        ap_bonus=ap_bonus,
    )
    transcript.cumulative_gpa = cumulative_gpa
    transcript.weighted_gpa = weighted_gpa
    transcript.total_credits = total_credits
    await db.flush()

    refreshed = await get_transcript(db, family_id=transcript.family_id, transcript_id=transcript.id)
    assert refreshed is not None
    return refreshed


async def finalize_transcript(db: AsyncSession, *, transcript: Transcript) -> Transcript:
    if transcript.status == TranscriptStatus.final:
        return transcript
    if transcript.status == TranscriptStatus.archived:
        raise ValueError('Archived transcripts cannot be finalized')
    transcript.status = TranscriptStatus.final
    transcript.generated_at = datetime.now(UTC)
    await db.flush()
    refreshed = await get_transcript(db, family_id=transcript.family_id, transcript_id=transcript.id)
    assert refreshed is not None
    return refreshed


async def get_transcript_rank(
    db: AsyncSession,
    *,
    family_id: int,
    student_id: int,
) -> tuple[int | None, int | None]:
    student_rows = (
        await db.execute(
            select(Student.id, Student.name).where(Student.family_id == family_id).order_by(Student.name.asc(), Student.id.asc())
        )
    ).all()
    if len(student_rows) <= 1:
        return None, None

    rows = (
        await db.execute(
            select(Grade.student_id, Subject.id, Grade.score, Grade.max_score, Subject.grade_scale_id)
            .join(Submission, Submission.id == Grade.submission_id)
            .join(Assignment, Assignment.id == Submission.assignment_id)
            .join(Subject, Subject.id == Assignment.subject_id)
            .where(Grade.family_id == family_id, Assignment.grading_period_id.is_not(None))
        )
    ).all()
    if not rows:
        return None, None

    default_scale = await ensure_default_grade_scale(db, family_id)
    scale_ids = {row[4] for row in rows if row[4] is not None}

    scales = {default_scale.id: default_scale}
    if scale_ids:
        scale_result = await db.execute(select(GradeScale).where(GradeScale.id.in_(scale_ids)))
        scales.update({scale.id: scale for scale in scale_result.scalars().all()})

    grouped: dict[tuple[int, int], list[float]] = defaultdict(list)
    subject_scale_ids: dict[tuple[int, int], int | None] = {}
    for current_student_id, subject_id, score, max_score, scale_id in rows:
        if not max_score:
            continue
        grouped[(current_student_id, subject_id)].append((float(score) / float(max_score)) * 100)
        subject_scale_ids[(current_student_id, subject_id)] = scale_id

    student_gpas: list[tuple[int, str, float]] = []
    for current_student_id, student_name in student_rows:
        subject_points: list[float] = []
        for (group_student_id, subject_id), percents in grouped.items():
            if group_student_id != current_student_id or not percents:
                continue
            average_percent = sum(percents) / len(percents)
            subject_scale_id = subject_scale_ids.get((current_student_id, subject_id))
            scale = scales.get(subject_scale_id) if subject_scale_id is not None else default_scale
            _, gpa_points = map_percent_to_grade(scale, average_percent)
            if gpa_points is not None:
                subject_points.append(float(gpa_points))
        if subject_points:
            student_gpas.append((current_student_id, student_name, round(sum(subject_points) / len(subject_points), 2)))

    if len(student_gpas) <= 1:
        return None, None

    ordered = sorted(student_gpas, key=lambda item: (-item[2], item[1].lower(), item[0]))
    for index, (current_student_id, _, _) in enumerate(ordered, start=1):
        if current_student_id == student_id:
            return index, len(ordered)
    return None, len(ordered)


def build_transcript_pdf(
    transcript: Transcript,
    *,
    class_rank: int | None = None,
    class_size: int | None = None,
) -> bytes:
    honors_bonus, ap_bonus, _ = transcript_weight_config(transcript.family)
    family_name = transcript.family.name if transcript.family else 'Family'
    student_name = transcript.student.name if transcript.student else 'Student'

    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=0.6 * inch,
        leftMargin=0.6 * inch,
        topMargin=0.5 * inch,
        bottomMargin=0.5 * inch,
    )
    styles = getSampleStyleSheet()
    title_style = styles['Title']
    subtitle_style = styles['Heading3']
    body_style = styles['BodyText']
    body_style.spaceAfter = 6
    small_style = ParagraphStyle('small', parent=styles['BodyText'], fontSize=9, leading=12)

    summary_rows = [
        ['Cumulative GPA', f'{transcript.cumulative_gpa:.2f}' if transcript.cumulative_gpa is not None else '—'],
        ['Weighted GPA', f'{transcript.weighted_gpa:.2f}' if transcript.weighted_gpa is not None else '—'],
        ['Total credits', f'{_float_or_none(transcript.total_credits) or 0.0:.2f}'],
        ['Class rank', f'{class_rank} / {class_size}' if class_rank is not None and class_size is not None else 'N/A'],
    ]

    story: list[Any] = [
        Paragraph('Official Transcript', title_style),
        Paragraph(f'{family_name} &middot; {student_name}', subtitle_style),
        Paragraph(
            f'<b>Status:</b> {transcript.status.value.title()} &nbsp;&nbsp;'
            f'<b>Generated:</b> {_format_datetime(transcript.generated_at)}'
            + (
                f' &nbsp;&nbsp; <b>By:</b> {transcript.generated_by.display_name}'
                if transcript.generated_by is not None
                else ''
            ),
            body_style,
        ),
        Paragraph(
            f'<b>Weighting:</b> Honors +{honors_bonus:.2f} &nbsp;&nbsp; <b>AP:</b> +{ap_bonus:.2f}',
            small_style,
        ),
        Spacer(1, 0.12 * inch),
    ]

    summary_table = Table(summary_rows, colWidths=[1.8 * inch, 1.4 * inch])
    summary_table.setStyle(
        TableStyle(
            [
                ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#0f172a')),
                ('TEXTCOLOR', (0, 0), (0, -1), colors.white),
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
                ('ROWBACKGROUNDS', (1, 0), (-1, -1), [colors.white, colors.HexColor('#f8fafc')]),
                ('LEFTPADDING', (0, 0), (-1, -1), 6),
                ('RIGHTPADDING', (0, 0), (-1, -1), 6),
                ('TOPPADDING', (0, 0), (-1, -1), 5),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ]
        )
    )
    story.extend([summary_table, Spacer(1, 0.18 * inch)])

    entries_by_year: dict[str, list[TranscriptEntry]] = defaultdict(list)
    for entry in transcript.entries:
        year_name = entry.school_year.name if entry.school_year else f'School Year {entry.school_year_id}'
        entries_by_year[year_name].append(entry)

    for year_name, year_entries in entries_by_year.items():
        story.append(Paragraph(year_name, styles['Heading4']))
        rows = [['Course', 'Credits', 'Grade', 'GPA', 'Weighted', 'Level', 'Notes']]
        for entry in year_entries:
            weighted_points = transcript_entry_weighted_points(entry, honors_bonus=honors_bonus, ap_bonus=ap_bonus)
            level = 'AP' if entry.is_ap else 'Honors' if entry.is_honors else 'Standard'
            rows.append(
                [
                    entry.subject_name,
                    f'{_float_or_none(entry.credits) or 0.0:.2f}',
                    entry.letter_grade or '—',
                    f'{entry.gpa_points:.2f}' if entry.gpa_points is not None else '—',
                    f'{weighted_points:.2f}' if weighted_points is not None else '—',
                    level,
                    entry.notes or '—',
                ]
            )
        table = Table(rows, repeatRows=1, colWidths=[1.7 * inch, 0.7 * inch, 0.7 * inch, 0.7 * inch, 0.8 * inch, 0.9 * inch, 1.8 * inch])
        table.setStyle(
            TableStyle(
                [
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1d4ed8')),
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
        story.extend([table, Spacer(1, 0.14 * inch)])

    if transcript.notes:
        story.extend([Paragraph('Registrar notes', styles['Heading4']), Paragraph(transcript.notes.replace('\n', '<br/>'), body_style)])

    document.build(story)
    return buffer.getvalue()
