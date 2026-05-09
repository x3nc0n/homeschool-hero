from __future__ import annotations

import asyncio
import csv
import io
import json
from datetime import UTC, date, datetime, time
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.config import settings
from backend.database import AsyncSessionLocal
from backend.models import (
    Assignment,
    AssignmentCategory,
    AssignmentRecurrence,
    AssignmentStatus,
    AssignmentTarget,
    AssignmentTargetStatus,
    AttendanceRecord,
    AttendanceStatus,
    AuditAction,
    CurriculumLesson,
    CurriculumPackage,
    CurriculumUnit,
    Grade,
    GradedBy,
    GradingPeriod,
    LessonResource,
    Resource,
    ResourceType,
    SchoolYear,
    Student,
    Subject,
    Submission,
    User,
)
from backend.models.import_job import ImportEntityType, ImportJob, ImportJobStatus
from backend.services.audit import log_event
from backend.validation import HEX_COLOR_RE, normalize_optional_text, normalize_text, sanitize_filename

CSV_HEADERS: dict[ImportEntityType, list[str]] = {
    ImportEntityType.students: ['name'],
    ImportEntityType.subjects: ['name', 'color'],
    ImportEntityType.assignments: [
        'title',
        'subject_name',
        'description',
        'due_date',
        'status',
        'category',
        'grading_period_name',
        'weight',
        'max_score',
        'recurrence',
        'recurrence_end_date',
        'rubric_description',
        'target_student_names',
    ],
    ImportEntityType.grades: [
        'student_name',
        'assignment_title',
        'subject_name',
        'score',
        'max_score',
        'letter_grade',
        'notes',
        'graded_by',
        'ai_confidence',
    ],
    ImportEntityType.attendance: [
        'student_name',
        'date',
        'status',
        'check_in_time',
        'check_out_time',
        'instructional_hours',
        'notes',
    ],
}

CSV_EXAMPLES: dict[ImportEntityType, dict[str, str]] = {
    ImportEntityType.students: {'name': 'Ada Lovelace'},
    ImportEntityType.subjects: {'name': 'Mathematics', 'color': '#2563eb'},
    ImportEntityType.assignments: {
        'title': 'Fractions Worksheet',
        'subject_name': 'Mathematics',
        'description': 'Complete problems 1-10.',
        'due_date': '2026-05-15',
        'status': 'pending',
        'category': 'homework',
        'grading_period_name': 'Quarter 4',
        'weight': '1.0',
        'max_score': '100',
        'recurrence': 'none',
        'recurrence_end_date': '',
        'rubric_description': 'Show your work.',
        'target_student_names': 'Ada Lovelace|Grace Hopper',
    },
    ImportEntityType.grades: {
        'student_name': 'Ada Lovelace',
        'assignment_title': 'Fractions Worksheet',
        'subject_name': 'Mathematics',
        'score': '92',
        'max_score': '100',
        'letter_grade': 'A-',
        'notes': 'Strong work overall.',
        'graded_by': 'human',
        'ai_confidence': '',
    },
    ImportEntityType.attendance: {
        'student_name': 'Ada Lovelace',
        'date': '2026-05-14',
        'status': 'present',
        'check_in_time': '09:00',
        'check_out_time': '13:00',
        'instructional_hours': '4.00',
        'notes': 'Science lab day.',
    },
}

_IMPORT_TASKS: set[asyncio.Task[Any]] = set()


class _ActorRef:
    def __init__(self, actor_id: int) -> None:
        self.id = actor_id


def available_template_entities() -> list[ImportEntityType]:
    return list(CSV_HEADERS)


def render_template_csv(entity_type: ImportEntityType) -> str:
    headers = CSV_HEADERS.get(entity_type)
    example = CSV_EXAMPLES.get(entity_type)
    if headers is None or example is None:
        raise ValueError('Template is only available for CSV import types')
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=headers, lineterminator='\n')
    writer.writeheader()
    writer.writerow(example)
    return buffer.getvalue()


def _track_task(task: asyncio.Task[Any]) -> None:
    _IMPORT_TASKS.add(task)
    task.add_done_callback(_IMPORT_TASKS.discard)


def schedule_import_execution(job_id: int) -> None:
    _track_task(asyncio.create_task(_run_import_job(job_id)))


def _now_utc() -> datetime:
    return datetime.now(UTC)


def _job_snapshot(job: ImportJob) -> dict[str, Any]:
    return {
        'id': job.id,
        'entity_type': job.entity_type.value,
        'status': job.status.value,
        'total_rows': job.total_rows,
        'processed_rows': job.processed_rows,
        'error_count': job.error_count,
    }


def _make_error(*, message: str, row: int | None = None, field: str | None = None, suggestion: str | None = None) -> dict[str, Any]:
    return {'row': row, 'field': field, 'message': message, 'suggestion': suggestion}


def _decode_csv_rows(file_path: str, entity_type: ImportEntityType) -> tuple[list[dict[str, str]], list[dict[str, Any]]]:
    try:
        text = Path(file_path).read_text(encoding='utf-8-sig')
    except UnicodeDecodeError:
        return [], [_make_error(message='CSV files must be UTF-8 encoded.', suggestion='Save the file as UTF-8 and retry.')]
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        return [], [_make_error(message='CSV file must include a header row.', suggestion='Download a template and use its headers.')]
    fieldnames = [(field or '').strip() for field in reader.fieldnames]
    required_headers = CSV_HEADERS[entity_type]
    missing = [header for header in required_headers if header not in fieldnames]
    if missing:
        return [], [
            _make_error(
                message=f"Missing required columns: {', '.join(missing)}.",
                field='header',
                suggestion='Download the template and restore the required columns.',
            )
        ]
    rows: list[dict[str, str]] = []
    for raw_row in reader:
        rows.append({(key or '').strip(): (value or '').strip() for key, value in raw_row.items()})
    return rows, []


def _parse_json_payload(file_path: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    try:
        payload = json.loads(Path(file_path).read_text(encoding='utf-8'))
    except UnicodeDecodeError:
        return [], [_make_error(message='JSON files must be UTF-8 encoded.', suggestion='Save the file as UTF-8 and retry.')]
    except json.JSONDecodeError as exc:
        return [], [_make_error(message=f'Invalid JSON: {exc.msg}.', suggestion='Validate the JSON syntax and retry.')]
    if isinstance(payload, dict) and isinstance(payload.get('packages'), list):
        packages = payload['packages']
    elif isinstance(payload, list):
        packages = payload
    elif isinstance(payload, dict):
        packages = [payload]
    else:
        return [], [_make_error(message='Curriculum import must be a JSON object or array.', suggestion='Wrap packages in a JSON object or array.')]
    normalized = [item for item in packages if isinstance(item, dict)]
    if len(normalized) != len(packages):
        return [], [_make_error(message='Each curriculum package entry must be a JSON object.', suggestion='Fix malformed package entries and retry.')]
    return normalized, []


def _parse_optional_date(value: str, *, row: int, field: str, errors: list[dict[str, Any]]) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        errors.append(_make_error(row=row, field=field, message=f'{field} must be an ISO date (YYYY-MM-DD).', suggestion='Use the format YYYY-MM-DD.'))
        return None


def _parse_optional_time(value: str, *, row: int, field: str, errors: list[dict[str, Any]]) -> time | None:
    if not value:
        return None
    try:
        return time.fromisoformat(value)
    except ValueError:
        errors.append(_make_error(row=row, field=field, message=f'{field} must be a valid time.', suggestion='Use 24-hour time like 09:00.'))
        return None


def _parse_assignment_due_date(value: str, *, row: int, field: str, errors: list[dict[str, Any]]) -> datetime | None:
    if not value:
        return None
    try:
        if 'T' in value:
            parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
            if parsed.tzinfo is None:
                return parsed.replace(tzinfo=UTC)
            return parsed.astimezone(UTC)
        return datetime.combine(date.fromisoformat(value), time.min, tzinfo=UTC)
    except ValueError:
        errors.append(
            _make_error(
                row=row,
                field=field,
                message='due_date must be an ISO date or datetime.',
                suggestion='Use YYYY-MM-DD or YYYY-MM-DDTHH:MM:SSZ.',
            )
        )
        return None


def _parse_float(value: str, *, row: int, field: str, errors: list[dict[str, Any]], minimum: float | None = None) -> float | None:
    if value == '':
        return None
    try:
        parsed = float(value)
    except ValueError:
        errors.append(_make_error(row=row, field=field, message=f'{field} must be a number.', suggestion='Enter a numeric value.'))
        return None
    if minimum is not None and parsed < minimum:
        errors.append(_make_error(row=row, field=field, message=f'{field} must be at least {minimum}.', suggestion=f'Use a value of {minimum} or greater.'))
        return None
    return parsed


def _parse_decimal(value: str, *, row: int, field: str, errors: list[dict[str, Any]]) -> Decimal | None:
    if value == '':
        return None
    try:
        return Decimal(value)
    except InvalidOperation:
        errors.append(_make_error(row=row, field=field, message=f'{field} must be a decimal number.', suggestion='Enter a decimal value like 4.00.'))
        return None


def _split_names(value: str) -> list[str]:
    return [item.strip() for item in value.split('|') if item.strip()]


async def _validate_students_csv(db: AsyncSession, family_id: int, rows: list[dict[str, str]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    errors: list[dict[str, Any]] = []
    existing_names = {
        student.name.strip().lower()
        for student in (
            await db.execute(select(Student).where(Student.family_id == family_id))
        ).scalars()
    }
    seen: set[str] = set()
    normalized: list[dict[str, Any]] = []
    for index, row in enumerate(rows, start=2):
        raw_name = row.get('name', '')
        try:
            name = normalize_text(raw_name, field_name='Student name')
        except ValueError as exc:
            errors.append(_make_error(row=index, field='name', message=str(exc), suggestion='Provide the student name.'))
            continue
        lowered = name.lower()
        if lowered in seen:
            errors.append(_make_error(row=index, field='name', message='Student appears more than once in this file.', suggestion='Remove duplicate student rows.'))
            continue
        if lowered in existing_names:
            errors.append(_make_error(row=index, field='name', message='Student already exists for this family.', suggestion='Rename the student or remove the duplicate import row.'))
            continue
        seen.add(lowered)
        normalized.append({'name': name})
    return normalized, errors


async def _validate_subjects_csv(db: AsyncSession, family_id: int, rows: list[dict[str, str]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    errors: list[dict[str, Any]] = []
    existing_names = {
        subject.name.strip().lower()
        for subject in (
            await db.execute(select(Subject).where(Subject.family_id == family_id))
        ).scalars()
    }
    seen: set[str] = set()
    normalized: list[dict[str, Any]] = []
    for index, row in enumerate(rows, start=2):
        try:
            name = normalize_text(row.get('name', ''), field_name='Subject name')
        except ValueError as exc:
            errors.append(_make_error(row=index, field='name', message=str(exc), suggestion='Provide the subject name.'))
            continue
        color = row.get('color', '') or '#4f46e5'
        if not HEX_COLOR_RE.match(color):
            errors.append(_make_error(row=index, field='color', message='Subject color must be a hex code.', suggestion='Use a color like #2563eb.'))
            continue
        lowered = name.lower()
        if lowered in seen:
            errors.append(_make_error(row=index, field='name', message='Subject appears more than once in this file.', suggestion='Remove duplicate subject rows.'))
            continue
        if lowered in existing_names:
            errors.append(_make_error(row=index, field='name', message='Subject already exists for this family.', suggestion='Rename the subject or remove the duplicate row.'))
            continue
        seen.add(lowered)
        normalized.append({'name': name, 'color': color})
    return normalized, errors


async def _validate_assignments_csv(db: AsyncSession, family_id: int, rows: list[dict[str, str]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    errors: list[dict[str, Any]] = []
    subjects = {
        subject.name.strip().lower(): subject
        for subject in (
            await db.execute(select(Subject).where(Subject.family_id == family_id))
        ).scalars()
    }
    students = {
        student.name.strip().lower(): student
        for student in (
            await db.execute(select(Student).where(Student.family_id == family_id))
        ).scalars()
    }
    grading_periods = {
        period.name.strip().lower(): period
        for period in (
            await db.execute(select(GradingPeriod).where(GradingPeriod.family_id == family_id))
        ).scalars()
    }
    normalized: list[dict[str, Any]] = []
    for index, row in enumerate(rows, start=2):
        row_errors_before = len(errors)
        try:
            title = normalize_text(row.get('title', ''), field_name='Assignment title')
        except ValueError as exc:
            errors.append(_make_error(row=index, field='title', message=str(exc), suggestion='Provide the assignment title.'))
            continue
        subject_name = row.get('subject_name', '')
        if not subject_name.strip():
            errors.append(_make_error(row=index, field='subject_name', message='subject_name is required.', suggestion='Use an existing subject name.'))
            continue
        subject = subjects.get(subject_name.strip().lower())
        if subject is None:
            errors.append(_make_error(row=index, field='subject_name', message='Subject not found for this family.', suggestion='Import the subject first or fix the name.'))
        due_date = _parse_assignment_due_date(row.get('due_date', ''), row=index, field='due_date', errors=errors)
        recurrence_end_date = _parse_optional_date(row.get('recurrence_end_date', ''), row=index, field='recurrence_end_date', errors=errors)
        weight = _parse_float(row.get('weight', '1.0') or '1.0', row=index, field='weight', errors=errors, minimum=0)
        max_score = _parse_float(row.get('max_score', '100') or '100', row=index, field='max_score', errors=errors, minimum=0.01)
        try:
            status_value = AssignmentStatus((row.get('status') or AssignmentStatus.pending.value).strip() or AssignmentStatus.pending.value)
        except ValueError:
            errors.append(_make_error(row=index, field='status', message='status is invalid.', suggestion='Use pending, complete, or graded.'))
            status_value = AssignmentStatus.pending
        try:
            category_value = AssignmentCategory((row.get('category') or AssignmentCategory.homework.value).strip() or AssignmentCategory.homework.value)
        except ValueError:
            errors.append(_make_error(row=index, field='category', message='category is invalid.', suggestion='Use homework, quiz, test, project, or other.'))
            category_value = AssignmentCategory.homework
        try:
            recurrence_value = AssignmentRecurrence((row.get('recurrence') or AssignmentRecurrence.none.value).strip() or AssignmentRecurrence.none.value)
        except ValueError:
            errors.append(_make_error(row=index, field='recurrence', message='recurrence is invalid.', suggestion='Use none, daily, or weekly.'))
            recurrence_value = AssignmentRecurrence.none
        grading_period = None
        grading_period_name = row.get('grading_period_name', '').strip()
        if grading_period_name:
            grading_period = grading_periods.get(grading_period_name.lower())
            if grading_period is None:
                errors.append(_make_error(row=index, field='grading_period_name', message='Grading period not found for this family.', suggestion='Create the grading period first or leave this column blank.'))
        target_names = _split_names(row.get('target_student_names', ''))
        target_ids: list[int] = []
        seen_target_ids: set[int] = set()
        for target_name in target_names:
            student = students.get(target_name.lower())
            if student is None:
                errors.append(_make_error(row=index, field='target_student_names', message=f"Student '{target_name}' was not found.", suggestion='Import the student first or fix the name.'))
                continue
            if student.id not in seen_target_ids:
                seen_target_ids.add(student.id)
                target_ids.append(student.id)
        try:
            description = normalize_optional_text(row.get('description', ''), field_name='Assignment description', max_length=4000)
            rubric_description = normalize_optional_text(row.get('rubric_description', ''), field_name='Assignment rubric description', max_length=4000)
        except ValueError as exc:
            errors.append(_make_error(row=index, field='description', message=str(exc), suggestion='Remove unsupported characters or shorten the text.'))
            continue
        if recurrence_value != AssignmentRecurrence.none:
            if due_date is None:
                errors.append(_make_error(row=index, field='due_date', message='due_date is required when recurrence is enabled.', suggestion='Add a due date or set recurrence to none.'))
            if recurrence_end_date is None:
                errors.append(_make_error(row=index, field='recurrence_end_date', message='recurrence_end_date is required when recurrence is enabled.', suggestion='Add an end date or set recurrence to none.'))
            if due_date is not None and recurrence_end_date is not None and recurrence_end_date < due_date.date():
                errors.append(_make_error(row=index, field='recurrence_end_date', message='recurrence_end_date must be on or after due_date.', suggestion='Use an end date on or after the due date.'))
        if len(errors) != row_errors_before:
            continue
        normalized.append(
            {
                'title': title,
                'subject_id': subject.id,
                'description': description,
                'due_date': due_date,
                'status': status_value,
                'category': category_value,
                'grading_period_id': grading_period.id if grading_period else None,
                'weight': weight if weight is not None else 1.0,
                'max_score': max_score if max_score is not None else 100.0,
                'recurrence': recurrence_value,
                'recurrence_end_date': recurrence_end_date,
                'rubric_description': rubric_description,
                'target_student_ids': target_ids,
            }
        )
    return normalized, errors


async def _validate_grades_csv(db: AsyncSession, family_id: int, rows: list[dict[str, str]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    errors: list[dict[str, Any]] = []
    students = {
        student.name.strip().lower(): student
        for student in (
            await db.execute(select(Student).where(Student.family_id == family_id))
        ).scalars()
    }
    assignments = (
        await db.execute(
            select(Assignment)
            .options(selectinload(Assignment.targets), selectinload(Assignment.subject))
            .where(Assignment.family_id == family_id)
        )
    ).scalars().all()
    submissions = (
        await db.execute(
            select(Submission).options(selectinload(Submission.grade)).where(
                Submission.family_id == family_id,
                Submission.is_current.is_(True),
            )
        )
    ).scalars().all()
    graded_pairs = {
        (submission.assignment_id, submission.student_id)
        for submission in submissions
        if submission.grade is not None
    }
    seen_pairs: set[tuple[int, int]] = set()
    normalized: list[dict[str, Any]] = []
    for index, row in enumerate(rows, start=2):
        row_errors_before = len(errors)
        student_name = row.get('student_name', '').strip()
        assignment_title = row.get('assignment_title', '').strip()
        if not student_name:
            errors.append(_make_error(row=index, field='student_name', message='student_name is required.', suggestion='Use an existing student name.'))
            continue
        if not assignment_title:
            errors.append(_make_error(row=index, field='assignment_title', message='assignment_title is required.', suggestion='Use an existing assignment title.'))
            continue
        student = students.get(student_name.lower())
        if student is None:
            errors.append(_make_error(row=index, field='student_name', message='Student not found for this family.', suggestion='Import the student first or fix the name.'))
            continue
        subject_name = row.get('subject_name', '').strip().lower()
        matched_assignments = [
            assignment
            for assignment in assignments
            if assignment.title.strip().lower() == assignment_title.lower()
            and (not subject_name or (assignment.subject and assignment.subject.name.strip().lower() == subject_name))
        ]
        if not matched_assignments:
            errors.append(_make_error(row=index, field='assignment_title', message='Assignment not found for this family.', suggestion='Import the assignment first or include the correct subject_name.'))
            continue
        if len(matched_assignments) > 1:
            errors.append(_make_error(row=index, field='assignment_title', message='Assignment title is ambiguous for this family.', suggestion='Provide subject_name or use a unique assignment title.'))
            continue
        assignment = matched_assignments[0]
        pair = (assignment.id, student.id)
        if pair in seen_pairs:
            errors.append(_make_error(row=index, field='assignment_title', message='A grade for this student and assignment appears more than once in the file.', suggestion='Keep only one grade row per student and assignment.'))
        if pair in graded_pairs:
            errors.append(_make_error(row=index, field='assignment_title', message='A grade already exists for this student and assignment.', suggestion='Remove the row or delete the existing grade first.'))
        if assignment.targets and student.id not in {target.student_id for target in assignment.targets}:
            errors.append(_make_error(row=index, field='student_name', message='Student is not assigned to this assignment.', suggestion='Assign the student to the assignment before importing the grade.'))
        score = _parse_float(row.get('score', ''), row=index, field='score', errors=errors, minimum=0)
        max_score = _parse_float(row.get('max_score', ''), row=index, field='max_score', errors=errors, minimum=0.01)
        if score is not None and max_score is not None and score > max_score:
            errors.append(_make_error(row=index, field='score', message='score cannot be greater than max_score.', suggestion='Lower the score or raise the max_score.'))
        try:
            letter_grade = normalize_optional_text(row.get('letter_grade', ''), field_name='Letter grade', max_length=4)
            notes = normalize_optional_text(row.get('notes', ''), field_name='Grade notes', max_length=4000)
        except ValueError as exc:
            errors.append(_make_error(row=index, field='notes', message=str(exc), suggestion='Remove unsupported characters or shorten the text.'))
            continue
        graded_by_raw = (row.get('graded_by') or GradedBy.human.value).strip() or GradedBy.human.value
        try:
            graded_by = GradedBy(graded_by_raw)
        except ValueError:
            errors.append(_make_error(row=index, field='graded_by', message='graded_by is invalid.', suggestion='Use human, ai, or ai+human.'))
            graded_by = GradedBy.human
        ai_confidence = _parse_float(row.get('ai_confidence', ''), row=index, field='ai_confidence', errors=errors, minimum=0)
        if ai_confidence is not None and ai_confidence > 1:
            errors.append(_make_error(row=index, field='ai_confidence', message='ai_confidence must be between 0 and 1.', suggestion='Use a decimal between 0 and 1.'))
        if len(errors) != row_errors_before:
            continue
        seen_pairs.add(pair)
        normalized.append(
            {
                'assignment_id': assignment.id,
                'student_id': student.id,
                'score': score,
                'max_score': max_score,
                'letter_grade': letter_grade.upper() if letter_grade else None,
                'notes': notes,
                'graded_by': graded_by,
                'ai_confidence': ai_confidence,
            }
        )
    return normalized, errors


async def _validate_attendance_csv(db: AsyncSession, family_id: int, rows: list[dict[str, str]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    errors: list[dict[str, Any]] = []
    students = {
        student.name.strip().lower(): student
        for student in (
            await db.execute(select(Student).where(Student.family_id == family_id))
        ).scalars()
    }
    existing_pairs = {
        (record.student_id, record.date.isoformat())
        for record in (
            await db.execute(select(AttendanceRecord).where(AttendanceRecord.family_id == family_id))
        ).scalars()
    }
    seen_pairs: set[tuple[int, str]] = set()
    normalized: list[dict[str, Any]] = []
    for index, row in enumerate(rows, start=2):
        row_errors_before = len(errors)
        student_name = row.get('student_name', '').strip()
        if not student_name:
            errors.append(_make_error(row=index, field='student_name', message='student_name is required.', suggestion='Use an existing student name.'))
            continue
        student = students.get(student_name.lower())
        if student is None:
            errors.append(_make_error(row=index, field='student_name', message='Student not found for this family.', suggestion='Import the student first or fix the name.'))
            continue
        record_date = _parse_optional_date(row.get('date', ''), row=index, field='date', errors=errors)
        try:
            status_value = AttendanceStatus((row.get('status') or AttendanceStatus.present.value).strip() or AttendanceStatus.present.value)
        except ValueError:
            errors.append(_make_error(row=index, field='status', message='status is invalid.', suggestion='Use present, absent, tardy, or excused.'))
            status_value = AttendanceStatus.present
        check_in_time = _parse_optional_time(row.get('check_in_time', ''), row=index, field='check_in_time', errors=errors)
        check_out_time = _parse_optional_time(row.get('check_out_time', ''), row=index, field='check_out_time', errors=errors)
        instructional_hours = _parse_decimal(row.get('instructional_hours', '') or '0', row=index, field='instructional_hours', errors=errors)
        try:
            notes = normalize_optional_text(row.get('notes', ''), field_name='Attendance notes', max_length=1000)
        except ValueError as exc:
            errors.append(_make_error(row=index, field='notes', message=str(exc), suggestion='Remove unsupported characters or shorten the text.'))
            continue
        if check_in_time and check_out_time and check_out_time < check_in_time:
            errors.append(_make_error(row=index, field='check_out_time', message='check_out_time must be on or after check_in_time.', suggestion='Adjust the times so checkout is later than checkin.'))
        if instructional_hours is not None and instructional_hours < 0:
            errors.append(_make_error(row=index, field='instructional_hours', message='instructional_hours must be zero or greater.', suggestion='Use a positive number of hours.'))
        if record_date is not None:
            pair = (student.id, record_date.isoformat())
            if pair in seen_pairs:
                errors.append(_make_error(row=index, field='date', message='Attendance appears more than once in this file for the same student and date.', suggestion='Keep only one attendance row per student and date.'))
            if pair in existing_pairs:
                errors.append(_make_error(row=index, field='date', message='Attendance already exists for this student and date.', suggestion='Delete the existing record first or remove the duplicate row.'))
        if len(errors) != row_errors_before:
            continue
        seen_pairs.add((student.id, record_date.isoformat()))
        normalized.append(
            {
                'student_id': student.id,
                'date': record_date,
                'status': status_value,
                'check_in_time': check_in_time,
                'check_out_time': check_out_time,
                'instructional_hours': instructional_hours or Decimal('0'),
                'notes': notes,
            }
        )
    return normalized, errors


async def _validate_curriculum_packages_json(db: AsyncSession, family_id: int, packages: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    errors: list[dict[str, Any]] = []
    school_years = {
        school_year.name.strip().lower(): school_year
        for school_year in (
            await db.execute(select(SchoolYear).where(SchoolYear.family_id == family_id))
        ).scalars()
    }
    subjects = {
        subject.name.strip().lower(): subject
        for subject in (
            await db.execute(select(Subject).where(Subject.family_id == family_id))
        ).scalars()
    }
    existing_packages = {
        (package.school_year_id, package.name.strip().lower())
        for package in (
            await db.execute(select(CurriculumPackage).where(CurriculumPackage.family_id == family_id))
        ).scalars()
    }
    normalized: list[dict[str, Any]] = []
    for index, package in enumerate(packages, start=1):
        row_errors_before = len(errors)
        try:
            package_name = normalize_text(str(package.get('name', '')), field_name='Curriculum package name')
        except ValueError as exc:
            errors.append(_make_error(row=index, field='name', message=str(exc), suggestion='Provide the package name.'))
            continue
        school_year_name = str(package.get('school_year_name', '')).strip()
        subject_name = str(package.get('subject_name', '')).strip()
        if not school_year_name:
            errors.append(_make_error(row=index, field='school_year_name', message='school_year_name is required.', suggestion='Use an existing school year name.'))
        if not subject_name:
            errors.append(_make_error(row=index, field='subject_name', message='subject_name is required.', suggestion='Use an existing subject name.'))
        school_year = school_years.get(school_year_name.lower())
        subject = subjects.get(subject_name.lower())
        if school_year_name and school_year is None:
            errors.append(_make_error(row=index, field='school_year_name', message='School year not found for this family.', suggestion='Create the school year first or fix the name.'))
        if subject_name and subject is None:
            errors.append(_make_error(row=index, field='subject_name', message='Subject not found for this family.', suggestion='Import the subject first or fix the name.'))
        if school_year and (school_year.id, package_name.lower()) in existing_packages:
            errors.append(_make_error(row=index, field='name', message='Curriculum package already exists for this school year.', suggestion='Rename the package or remove the duplicate import entry.'))
        units_payload = package.get('units') or []
        if not isinstance(units_payload, list):
            errors.append(_make_error(row=index, field='units', message='units must be a list.', suggestion='Wrap units in a JSON array.'))
            units_payload = []
        normalized_units: list[dict[str, Any]] = []
        for unit_index, unit in enumerate(units_payload, start=1):
            if not isinstance(unit, dict):
                errors.append(_make_error(row=index, field='units', message=f'Unit #{unit_index} must be an object.', suggestion='Fix malformed unit entries.'))
                continue
            try:
                unit_name = normalize_text(str(unit.get('name', '')), field_name='Unit name')
            except ValueError as exc:
                errors.append(_make_error(row=index, field=f'units[{unit_index}].name', message=str(exc), suggestion='Provide the unit name.'))
                continue
            lessons_payload = unit.get('lessons') or []
            if not isinstance(lessons_payload, list):
                errors.append(_make_error(row=index, field=f'units[{unit_index}].lessons', message='lessons must be a list.', suggestion='Wrap lessons in a JSON array.'))
                lessons_payload = []
            normalized_lessons: list[dict[str, Any]] = []
            for lesson_index, lesson in enumerate(lessons_payload, start=1):
                if not isinstance(lesson, dict):
                    errors.append(_make_error(row=index, field=f'units[{unit_index}].lessons', message=f'Lesson #{lesson_index} must be an object.', suggestion='Fix malformed lesson entries.'))
                    continue
                try:
                    lesson_name = normalize_text(str(lesson.get('name', '')), field_name='Lesson name')
                except ValueError as exc:
                    errors.append(_make_error(row=index, field=f'units[{unit_index}].lessons[{lesson_index}].name', message=str(exc), suggestion='Provide the lesson name.'))
                    continue
                resources_payload = lesson.get('resources') or []
                if not isinstance(resources_payload, list):
                    errors.append(_make_error(row=index, field=f'units[{unit_index}].lessons[{lesson_index}].resources', message='resources must be a list.', suggestion='Wrap resources in a JSON array.'))
                    resources_payload = []
                normalized_resources: list[dict[str, Any]] = []
                for resource_index, resource in enumerate(resources_payload, start=1):
                    if not isinstance(resource, dict):
                        errors.append(_make_error(row=index, field=f'units[{unit_index}].lessons[{lesson_index}].resources', message=f'Resource #{resource_index} must be an object.', suggestion='Fix malformed resource entries.'))
                        continue
                    try:
                        resource_name = normalize_text(str(resource.get('name', '')), field_name='Resource name')
                    except ValueError as exc:
                        errors.append(_make_error(row=index, field=f'units[{unit_index}].lessons[{lesson_index}].resources[{resource_index}].name', message=str(exc), suggestion='Provide the resource name.'))
                        continue
                    resource_type_raw = str(resource.get('resource_type', ResourceType.note.value)).strip() or ResourceType.note.value
                    try:
                        resource_type = ResourceType(resource_type_raw)
                    except ValueError:
                        errors.append(_make_error(row=index, field=f'units[{unit_index}].lessons[{lesson_index}].resources[{resource_index}].resource_type', message='resource_type is invalid.', suggestion='Use file, link, or note.'))
                        continue
                    normalized_resources.append(
                        {
                            'name': resource_name,
                            'description': normalize_optional_text(
                                str(resource.get('description', '')),
                                field_name='Resource description',
                                max_length=4000,
                            ),
                            'resource_type': resource_type,
                            'url': normalize_optional_text(str(resource.get('url', '')), field_name='Resource URL', max_length=1000),
                            'tags': [str(tag).strip() for tag in (resource.get('tags') or []) if str(tag).strip()],
                            'metadata': resource.get('metadata') if isinstance(resource.get('metadata'), dict) else {},
                        }
                    )
                normalized_lessons.append(
                    {
                        'name': lesson_name,
                        'description': normalize_optional_text(
                            str(lesson.get('description', '')),
                            field_name='Lesson description',
                            max_length=4000,
                        ),
                        'sequence_order': int(lesson.get('sequence_order') or lesson_index),
                        'estimated_duration_minutes': lesson.get('estimated_duration_minutes'),
                        'standards_tags': [str(tag).strip() for tag in (lesson.get('standards_tags') or []) if str(tag).strip()],
                        'resources': normalized_resources,
                    }
                )
            normalized_units.append(
                {
                    'name': unit_name,
                    'description': normalize_optional_text(
                        str(unit.get('description', '')),
                        field_name='Unit description',
                        max_length=4000,
                    ),
                    'sequence_order': int(unit.get('sequence_order') or unit_index),
                    'standards_tags': [str(tag).strip() for tag in (unit.get('standards_tags') or []) if str(tag).strip()],
                    'lessons': normalized_lessons,
                }
            )
        if len(errors) != row_errors_before:
            continue
        normalized.append(
            {
                'name': package_name,
                'description': normalize_optional_text(
                    str(package.get('description', '')),
                    field_name='Curriculum package description',
                    max_length=4000,
                ),
                'school_year_id': school_year.id,
                'subject_id': subject.id,
                'units': normalized_units,
            }
        )
    return normalized, errors


async def _validate_payload(db: AsyncSession, job: ImportJob) -> tuple[list[dict[str, Any]], list[dict[str, Any]], int]:
    if job.entity_type == ImportEntityType.curriculum_packages:
        packages, errors = _parse_json_payload(job.file_path)
        if errors:
            return [], errors, 0
        normalized, validation_errors = await _validate_curriculum_packages_json(db, job.family_id, packages)
        return normalized, validation_errors, len(packages)
    rows, errors = _decode_csv_rows(job.file_path, job.entity_type)
    if errors:
        return [], errors, 0
    validators = {
        ImportEntityType.students: _validate_students_csv,
        ImportEntityType.subjects: _validate_subjects_csv,
        ImportEntityType.assignments: _validate_assignments_csv,
        ImportEntityType.grades: _validate_grades_csv,
        ImportEntityType.attendance: _validate_attendance_csv,
    }
    normalized, validation_errors = await validators[job.entity_type](db, job.family_id, rows)
    return normalized, validation_errors, len(rows)


async def validate_import_job(db: AsyncSession, job: ImportJob) -> ImportJob:
    job.status = ImportJobStatus.validating
    job.completed_at = None
    await db.commit()
    await db.refresh(job)
    rows, errors, total_rows = await _validate_payload(db, job)
    job.total_rows = total_rows
    job.processed_rows = total_rows
    job.errors = errors
    job.error_count = len(errors)
    job.status = ImportJobStatus.failed if errors else ImportJobStatus.pending
    job.completed_at = _now_utc()
    await db.commit()
    await db.refresh(job)
    return job


async def _apply_students(db: AsyncSession, job: ImportJob, rows: list[dict[str, Any]]) -> None:
    for row in rows:
        db.add(Student(family_id=job.family_id, name=row['name']))


async def _apply_subjects(db: AsyncSession, job: ImportJob, rows: list[dict[str, Any]]) -> None:
    for row in rows:
        db.add(Subject(family_id=job.family_id, name=row['name'], color=row['color']))


async def _apply_assignments(db: AsyncSession, job: ImportJob, rows: list[dict[str, Any]]) -> None:
    for row in rows:
        assignment = Assignment(
            family_id=job.family_id,
            title=row['title'],
            subject_id=row['subject_id'],
            description=row['description'],
            due_date=row['due_date'],
            status=row['status'],
            category=row['category'],
            grading_period_id=row['grading_period_id'],
            weight=row['weight'],
            max_score=row['max_score'],
            recurrence=row['recurrence'],
            recurrence_end_date=row['recurrence_end_date'],
            rubric_description=row['rubric_description'],
            attachments=[],
            status_history=[],
        )
        for student_id in row['target_student_ids']:
            assignment.targets.append(AssignmentTarget(student_id=student_id, due_date=row['due_date'], status=AssignmentTargetStatus.assigned))
        db.add(assignment)


def _placeholder_submission_path(*, family_id: int, job_id: int, row_index: int) -> tuple[str, bytes, str]:
    relative_path = Path('imports') / f'family-{family_id}' / 'grades' / f'grade-import-{job_id}-{row_index}.txt'
    contents = f'Imported grade placeholder for job {job_id}, row {row_index}.'.encode('utf-8')
    absolute_path = Path(settings.upload_dir) / relative_path
    absolute_path.parent.mkdir(parents=True, exist_ok=True)
    absolute_path.write_bytes(contents)
    return str(relative_path).replace('\\', '/'), contents, absolute_path.name


async def _apply_grades(db: AsyncSession, job: ImportJob, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    current_submissions = (
        await db.execute(
            select(Submission).options(selectinload(Submission.grade)).where(
                Submission.family_id == job.family_id,
                Submission.is_current.is_(True),
            )
        )
    ).scalars().all()
    submissions_by_pair: dict[tuple[int, int], list[Submission]] = {}
    for submission in current_submissions:
        submissions_by_pair.setdefault((submission.assignment_id, submission.student_id), []).append(submission)
    targets = (
        await db.execute(
            select(AssignmentTarget).where(
                AssignmentTarget.assignment_id.in_([row['assignment_id'] for row in rows]) if rows else False
            )
        )
    ).scalars().all()
    targets_by_pair = {(target.assignment_id, target.student_id): target for target in targets}
    for row_index, row in enumerate(rows, start=1):
        pair = (row['assignment_id'], row['student_id'])
        submission = next((candidate for candidate in submissions_by_pair.get(pair, []) if candidate.grade is None), None)
        if submission is None:
            relative_path, contents, file_name = _placeholder_submission_path(
                family_id=job.family_id,
                job_id=job.id,
                row_index=row_index,
            )
            submission = Submission(
                family_id=job.family_id,
                assignment_id=row['assignment_id'],
                student_id=row['student_id'],
                file_path=relative_path,
                original_filename=file_name,
                file_name=file_name,
                file_type='text/plain',
                file_size_bytes=len(contents),
                submission_version=1,
                is_current=True,
                ocr_text=row['notes'] or 'Imported from CSV',
            )
            db.add(submission)
            await db.flush()
            submissions_by_pair.setdefault(pair, []).append(submission)
        grade = Grade(
            family_id=job.family_id,
            submission_id=submission.id,
            student_id=row['student_id'],
            score=row['score'],
            max_score=row['max_score'],
            letter_grade=row['letter_grade'],
            notes=row['notes'],
            graded_by=row['graded_by'],
            ai_confidence=row['ai_confidence'],
        )
        db.add(grade)
        target = targets_by_pair.get(pair)
        if target:
            target.status = AssignmentTargetStatus.graded


async def _apply_attendance(db: AsyncSession, job: ImportJob, rows: list[dict[str, Any]]) -> None:
    for row in rows:
        db.add(
            AttendanceRecord(
                family_id=job.family_id,
                student_id=row['student_id'],
                date=row['date'],
                status=row['status'],
                check_in_time=row['check_in_time'],
                check_out_time=row['check_out_time'],
                instructional_hours=row['instructional_hours'],
                notes=row['notes'],
            )
        )


async def _resolve_or_create_resource(
    db: AsyncSession,
    *,
    family_id: int,
    user_id: int,
    payload: dict[str, Any],
    existing_resources: dict[str, Resource],
) -> Resource:
    resource = existing_resources.get(payload['name'].lower())
    if resource is not None:
        return resource
    resource = Resource(
        family_id=family_id,
        name=payload['name'],
        description=payload['description'],
        resource_type=payload['resource_type'],
        url=payload['url'],
        tags=payload['tags'],
        resource_metadata=payload['metadata'],
        created_by_user_id=user_id,
    )
    db.add(resource)
    await db.flush()
    existing_resources[payload['name'].lower()] = resource
    return resource


async def _apply_curriculum_packages(db: AsyncSession, job: ImportJob, rows: list[dict[str, Any]]) -> None:
    existing_resources = {
        resource.name.strip().lower(): resource
        for resource in (
            await db.execute(select(Resource).where(Resource.family_id == job.family_id))
        ).scalars()
    }
    for row in rows:
        package = CurriculumPackage(
            family_id=job.family_id,
            school_year_id=row['school_year_id'],
            subject_id=row['subject_id'],
            created_by_user_id=job.user_id,
            name=row['name'],
            description=row['description'],
        )
        db.add(package)
        await db.flush()
        for unit_payload in row['units']:
            unit = CurriculumUnit(
                package_id=package.id,
                name=unit_payload['name'],
                description=unit_payload['description'],
                sequence_order=unit_payload['sequence_order'],
                standards_tags=unit_payload['standards_tags'],
            )
            db.add(unit)
            await db.flush()
            for lesson_payload in unit_payload['lessons']:
                lesson = CurriculumLesson(
                    unit_id=unit.id,
                    name=lesson_payload['name'],
                    description=lesson_payload['description'],
                    sequence_order=lesson_payload['sequence_order'],
                    estimated_duration_minutes=lesson_payload['estimated_duration_minutes'],
                    standards_tags=lesson_payload['standards_tags'],
                )
                db.add(lesson)
                await db.flush()
                for resource_payload in lesson_payload['resources']:
                    resource = await _resolve_or_create_resource(
                        db,
                        family_id=job.family_id,
                        user_id=job.user_id,
                        payload=resource_payload,
                        existing_resources=existing_resources,
                    )
                    db.add(LessonResource(lesson_id=lesson.id, resource_id=resource.id))


async def _apply_rows(db: AsyncSession, job: ImportJob, rows: list[dict[str, Any]]) -> None:
    appliers = {
        ImportEntityType.students: _apply_students,
        ImportEntityType.subjects: _apply_subjects,
        ImportEntityType.assignments: _apply_assignments,
        ImportEntityType.grades: _apply_grades,
        ImportEntityType.attendance: _apply_attendance,
        ImportEntityType.curriculum_packages: _apply_curriculum_packages,
    }
    await appliers[job.entity_type](db, job, rows)


async def _finalize_job(
    db: AsyncSession,
    job: ImportJob,
    *,
    status: ImportJobStatus,
    errors: list[dict[str, Any]] | None = None,
) -> None:
    job.status = status
    if errors is not None:
        job.errors = errors
        job.error_count = len(errors)
    job.completed_at = _now_utc()
    await db.commit()


async def _run_import_job(job_id: int) -> None:
    async with AsyncSessionLocal() as db:
        job = await db.get(ImportJob, job_id)
        if not job:
            return
        actor = await db.get(User, job.user_id)
        audit_actor = actor or _ActorRef(job.user_id)
        before_snapshot = _job_snapshot(job)
        rows, errors, total_rows = await _validate_payload(db, job)
        job.total_rows = total_rows
        job.processed_rows = 0
        job.errors = errors
        job.error_count = len(errors)
        if errors:
            await _finalize_job(db, job, status=ImportJobStatus.failed, errors=errors)
            await log_event(
                db,
                action=AuditAction.config_change,
                actor=audit_actor,
                family_id=job.family_id,
                target_type='import_job',
                target_id=job.id,
                before=before_snapshot,
                after=_job_snapshot(job),
                request=None,
            )
            await db.commit()
            return
        await db.commit()
        batch_size = 25
        for start in range(0, len(rows), batch_size):
            batch = rows[start : start + batch_size]
            await _apply_rows(db, job, batch)
            job.processed_rows = min(start + len(batch), len(rows))
            await db.commit()
        await _finalize_job(db, job, status=ImportJobStatus.complete, errors=[])
        await log_event(
            db,
            action=AuditAction.config_change,
            actor=audit_actor,
            family_id=job.family_id,
            target_type='import_job',
            target_id=job.id,
            before=before_snapshot,
            after=_job_snapshot(job),
            request=None,
        )
        await db.commit()


async def list_import_jobs(db: AsyncSession, *, family_id: int) -> list[ImportJob]:
    return list(
        (
            await db.execute(
                select(ImportJob).where(ImportJob.family_id == family_id).order_by(ImportJob.created_at.desc(), ImportJob.id.desc())
            )
        ).scalars()
    )


async def create_import_job(
    db: AsyncSession,
    *,
    family_id: int,
    user_id: int,
    entity_type: ImportEntityType,
    upload_filename: str,
    contents: bytes,
) -> ImportJob:
    if not contents:
        raise ValueError('Uploaded file is empty')
    safe_name = sanitize_filename(upload_filename)
    suffix = Path(safe_name).suffix.lower()
    if entity_type == ImportEntityType.curriculum_packages and suffix != '.json':
        raise ValueError('Curriculum packages must be uploaded as JSON files')
    if entity_type != ImportEntityType.curriculum_packages and suffix != '.csv':
        raise ValueError('This import type requires a CSV file')
    import_dir = Path(settings.upload_dir) / 'imports' / f'family-{family_id}'
    import_dir.mkdir(parents=True, exist_ok=True)
    destination = import_dir / f'{uuid4().hex}-{safe_name}'
    destination.write_bytes(contents)
    job = ImportJob(
        family_id=family_id,
        user_id=user_id,
        file_path=str(destination),
        entity_type=entity_type,
        status=ImportJobStatus.pending,
        total_rows=0,
        processed_rows=0,
        error_count=0,
        errors=[],
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)
    return job
