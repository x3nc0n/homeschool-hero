from __future__ import annotations

import asyncio
import csv
import io
import json
import mimetypes
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from sqlalchemy import Select, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.config import settings
from backend.database import AsyncSessionLocal
from backend.models import (
    Assignment,
    AttendanceRecord,
    AssignmentTarget,
    AuditEvent,
    ComplianceReport,
    Family,
    FamilyMembership,
    Grade,
    PortfolioEntry,
    ReportCard,
    ReportCardEntry,
    Student,
    Subject,
    Submission,
    Transcript,
    TranscriptEntry,
)
from backend.models.export_job import ExportEntityType, ExportFormat, ExportJob, ExportJobStatus, ExportType
from backend.services.compliance_reports import build_compliance_report_pdf, report_to_read
from backend.services.report_cards import build_report_card_pdf, report_card_to_read
from backend.services.transcripts import build_transcript_pdf, transcript_to_read

EXPORT_VERSION = '2026.05.10-dm02'
EXPORT_TTL_DAYS = 7
_EXPORT_TASKS: set[asyncio.Task[object]] = set()

DEFAULT_EXPORT_ENTITIES: list[ExportEntityType] = [
    ExportEntityType.family,
    ExportEntityType.students,
    ExportEntityType.subjects,
    ExportEntityType.assignments,
    ExportEntityType.submissions,
    ExportEntityType.grades,
    ExportEntityType.attendance,
    ExportEntityType.report_cards,
    ExportEntityType.transcripts,
    ExportEntityType.portfolio_entries,
    ExportEntityType.compliance_reports,
    ExportEntityType.audit_events,
]

CSV_HEADERS: dict[str, list[str]] = {
    'family': ['family_id', 'family_name', 'timezone', 'grading_scale', 'state_code', 'created_at', 'updated_at'],
    'users': ['user_id', 'email', 'display_name', 'auth_provider', 'is_active'],
    'family_memberships': ['user_id', 'email', 'role', 'is_owner', 'student_id', 'student_name', 'invited_at', 'accepted_at'],
    'students': ['student_id', 'name', 'created_at', 'updated_at'],
    'subjects': ['subject_id', 'name', 'color', 'grading_mode', 'grade_scale_id', 'created_at', 'updated_at'],
    'assignments': [
        'assignment_id',
        'title',
        'subject_name',
        'category',
        'due_date',
        'status',
        'grading_period_id',
        'weight',
        'max_score',
        'target_student_names',
        'grade_summary',
        'created_at',
        'updated_at',
    ],
    'submissions': [
        'submission_id',
        'assignment_id',
        'assignment_title',
        'student_id',
        'student_name',
        'file_path',
        'original_filename',
        'file_type',
        'file_size_bytes',
        'submission_version',
        'is_current',
        'uploaded_at',
    ],
    'grades': [
        'grade_id',
        'student_name',
        'subject_name',
        'assignment_title',
        'score',
        'max_score',
        'percentage',
        'letter_grade',
        'graded_by',
        'ai_confidence',
        'notes',
        'created_at',
    ],
    'attendance': [
        'attendance_id',
        'student_name',
        'date',
        'status',
        'instructional_hours',
        'check_in_time',
        'check_out_time',
        'notes',
        'excuse_reason',
        'excuse_document_path',
        'created_at',
        'updated_at',
    ],
    'report_cards': [
        'report_card_id',
        'student_name',
        'school_year_name',
        'grading_period_name',
        'status',
        'subject_name',
        'letter_grade',
        'percentage',
        'gpa_points',
        'attendance_rate',
        'teacher_comments',
        'generated_at',
        'notes',
    ],
    'transcripts': [
        'transcript_id',
        'student_name',
        'school_year_name',
        'status',
        'subject_name',
        'credits',
        'letter_grade',
        'gpa_points',
        'weighted_gpa_points',
        'is_honors',
        'is_ap',
        'generated_at',
        'notes',
    ],
    'portfolio_entries': [
        'portfolio_entry_id',
        'student_name',
        'entry_type',
        'title',
        'date',
        'subject_name',
        'assignment_title',
        'submission_id',
        'attachments',
        'tags',
        'created_at',
        'updated_at',
    ],
    'compliance_reports': [
        'compliance_report_id',
        'student_name',
        'school_year_name',
        'state_code',
        'report_type',
        'status',
        'period_label',
        'generated_at',
        'notes',
        'data',
    ],
    'audit_events': [
        'audit_event_id',
        'timestamp',
        'actor_user_id',
        'actor_email',
        'action',
        'target_entity_type',
        'target_entity_id',
        'ip_address',
        'user_agent',
    ],
}


def _track_task(task: asyncio.Task[object]) -> None:
    _EXPORT_TASKS.add(task)
    task.add_done_callback(_EXPORT_TASKS.discard)


def schedule_export_execution(job_id: int) -> None:
    _track_task(asyncio.create_task(_run_export_job(job_id)))


def _now_utc() -> datetime:
    return datetime.now(UTC)


def _isoformat(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat()


def _json_default(value: object) -> object:
    if isinstance(value, datetime):
        return _isoformat(value)
    if isinstance(value, Decimal):
        return str(value)
    if hasattr(value, 'value'):
        candidate = getattr(value, 'value')
        if isinstance(candidate, str):
            return candidate
    return str(value)


def _dump_json_bytes(payload: object) -> bytes:
    return json.dumps(payload, indent=2, sort_keys=True, default=_json_default).encode('utf-8')


def _csv_bytes(headers: list[str], rows: Sequence[dict[str, object]]) -> bytes:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=headers, lineterminator='\n')
    writer.writeheader()
    for row in rows:
        writer.writerow({header: _csv_value(row.get(header)) for header in headers})
    return buffer.getvalue().encode('utf-8')


def _csv_value(value: object | None) -> str:
    if value is None:
        return ''
    if isinstance(value, datetime):
        return _isoformat(value) or ''
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, bool):
        return 'true' if value else 'false'
    if isinstance(value, (list, dict)):
        return json.dumps(value, default=_json_default, separators=(',', ':'))
    if hasattr(value, 'value'):
        return str(getattr(value, 'value'))
    return str(value)


def _apply_since(stmt: Select, since: datetime | None, *columns) -> Select:
    if since is None or not columns:
        return stmt
    return stmt.where(or_(*(column >= since for column in columns)))


def _resolve_entities(export_type: ExportType, entity_types: Sequence[ExportEntityType]) -> list[ExportEntityType]:
    if export_type == ExportType.entity:
        return list(dict.fromkeys(entity_types))
    if entity_types:
        return list(dict.fromkeys(entity_types))
    return list(DEFAULT_EXPORT_ENTITIES)


def _job_snapshot(job: ExportJob) -> dict[str, object]:
    return {
        'id': job.id,
        'status': job.status.value,
        'export_type': job.export_type.value,
        'format': job.format.value,
        'entity_types': list(job.entity_types or []),
        'file_size': job.file_size,
        'date_from': _isoformat(job.date_from),
    }


def _file_name_for_job(job: ExportJob, *, single_entity: str | None = None) -> str:
    if job.format == ExportFormat.json:
        return f'family-export-{job.id}.json'
    if job.format == ExportFormat.zip:
        return f'family-export-{job.id}.zip'
    if single_entity is not None:
        return f'{single_entity}-{job.id}.csv'
    return f'family-export-{job.id}-csv.zip'


def get_export_media_type(file_path: str) -> str:
    guessed, _ = mimetypes.guess_type(file_path)
    return guessed or 'application/octet-stream'


def _resolve_upload_reference(path_value: str | None) -> Path | None:
    if not path_value:
        return None
    root = Path(settings.upload_dir).resolve()
    raw_path = Path(path_value)
    candidate = raw_path if raw_path.is_absolute() else root / raw_path
    try:
        resolved = candidate.resolve()
    except FileNotFoundError:
        resolved = candidate.absolute()
    try:
        resolved.relative_to(root)
    except ValueError:
        return None
    if not resolved.exists() or not resolved.is_file():
        return None
    return resolved


async def _collect_family_entity(db: AsyncSession, *, family_id: int) -> tuple[dict[str, object], dict[str, list[dict[str, object]]]]:
    family = (
        await db.execute(
            select(Family)
            .options(
                selectinload(Family.family_settings),
                selectinload(Family.memberships).selectinload(FamilyMembership.user),
                selectinload(Family.memberships).selectinload(FamilyMembership.student),
            )
            .where(Family.id == family_id)
        )
    ).scalar_one()
    family_settings = family.family_settings
    memberships = sorted(list(family.memberships or []), key=lambda item: (item.user_id, item.family_id))
    users = [membership.user for membership in memberships if membership.user is not None]
    family_payload = {
        'id': family.id,
        'name': family.name,
        'settings': family.settings or {},
        'created_at': family.created_at,
        'updated_at': family.updated_at,
        'family_settings': {
            'timezone': family_settings.timezone if family_settings else 'UTC',
            'grading_scale': family_settings.grading_scale if family_settings else 'letter',
            'state_code': family_settings.state_code if family_settings else 'CUSTOM',
        },
        'memberships': [
            {
                'user_id': membership.user_id,
                'email': membership.user.email if membership.user else None,
                'display_name': membership.user.display_name if membership.user else None,
                'role': membership.role.value,
                'is_owner': membership.is_owner,
                'student_id': membership.student_id,
                'student_name': membership.student.name if membership.student else None,
                'invited_at': membership.invited_at,
                'accepted_at': membership.accepted_at,
            }
            for membership in memberships
        ],
        'users': [
            {
                'id': user.id,
                'email': user.email,
                'display_name': user.display_name,
                'auth_provider': user.auth_provider,
                'is_active': user.is_active,
            }
            for user in users
        ],
    }
    csv_rows = {
        'family': [
            {
                'family_id': family.id,
                'family_name': family.name,
                'timezone': family_settings.timezone if family_settings else 'UTC',
                'grading_scale': family_settings.grading_scale if family_settings else 'letter',
                'state_code': family_settings.state_code if family_settings else 'CUSTOM',
                'created_at': family.created_at,
                'updated_at': family.updated_at,
            }
        ],
        'users': [
            {
                'user_id': user.id,
                'email': user.email,
                'display_name': user.display_name,
                'auth_provider': user.auth_provider,
                'is_active': user.is_active,
            }
            for user in users
        ],
        'family_memberships': [
            {
                'user_id': membership.user_id,
                'email': membership.user.email if membership.user else None,
                'role': membership.role.value,
                'is_owner': membership.is_owner,
                'student_id': membership.student_id,
                'student_name': membership.student.name if membership.student else None,
                'invited_at': membership.invited_at,
                'accepted_at': membership.accepted_at,
            }
            for membership in memberships
        ],
    }
    return family_payload, csv_rows


async def _collect_students(db: AsyncSession, *, family_id: int, since: datetime | None) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    stmt = _apply_since(
        select(Student).where(Student.family_id == family_id).order_by(Student.name.asc(), Student.id.asc()),
        since,
        Student.created_at,
        Student.updated_at,
    )
    items = list((await db.execute(stmt)).scalars().all())
    payload = [{'id': item.id, 'name': item.name, 'created_at': item.created_at, 'updated_at': item.updated_at} for item in items]
    rows = [{'student_id': item.id, 'name': item.name, 'created_at': item.created_at, 'updated_at': item.updated_at} for item in items]
    return payload, rows


async def _collect_subjects(db: AsyncSession, *, family_id: int, since: datetime | None) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    stmt = _apply_since(
        select(Subject).where(Subject.family_id == family_id).order_by(Subject.name.asc(), Subject.id.asc()),
        since,
        Subject.created_at,
        Subject.updated_at,
    )
    items = list((await db.execute(stmt)).scalars().all())
    payload = [
        {
            'id': item.id,
            'name': item.name,
            'color': item.color,
            'grading_mode': item.grading_mode,
            'grade_scale_id': item.grade_scale_id,
            'created_at': item.created_at,
            'updated_at': item.updated_at,
        }
        for item in items
    ]
    rows = [
        {
            'subject_id': item.id,
            'name': item.name,
            'color': item.color,
            'grading_mode': item.grading_mode,
            'grade_scale_id': item.grade_scale_id,
            'created_at': item.created_at,
            'updated_at': item.updated_at,
        }
        for item in items
    ]
    return payload, rows


async def _collect_assignments(
    db: AsyncSession,
    *,
    family_id: int,
    since: datetime | None,
) -> tuple[list[dict[str, object]], list[dict[str, object]], set[str]]:
    stmt = (
        select(Assignment)
        .options(
            selectinload(Assignment.subject),
            selectinload(Assignment.targets).selectinload(AssignmentTarget.student),
            selectinload(Assignment.submissions).selectinload(Submission.student),
            selectinload(Assignment.submissions).selectinload(Submission.grade),
        )
        .where(Assignment.family_id == family_id)
        .order_by(Assignment.due_date.asc(), Assignment.id.asc())
    )
    stmt = _apply_since(stmt, since, Assignment.created_at, Assignment.updated_at)
    items = list((await db.execute(stmt)).scalars().all())
    file_refs: set[str] = set()
    payload: list[dict[str, object]] = []
    rows: list[dict[str, object]] = []
    for item in items:
        for attachment in item.attachments or []:
            if attachment:
                file_refs.add(str(attachment))
        current_grades: list[str] = []
        for submission in item.submissions or []:
            if not submission.is_current or submission.grade is None:
                continue
            current_grades.append(
                f"{submission.student.name if submission.student else submission.student_id}:{submission.grade.letter_grade or ''} "
                f"({submission.grade.score}/{submission.grade.max_score})"
            )
        serialized = {
            'id': item.id,
            'title': item.title,
            'subject_id': item.subject_id,
            'subject_name': item.subject.name if item.subject else None,
            'description': item.description,
            'due_date': item.due_date,
            'status': item.status,
            'category': item.category,
            'grading_period_id': item.grading_period_id,
            'weight': item.weight,
            'max_score': item.max_score,
            'recurrence': item.recurrence,
            'recurrence_end_date': item.recurrence_end_date,
            'rubric_description': item.rubric_description,
            'attachments': list(item.attachments or []),
            'status_history': list(item.status_history or []),
            'targets': [
                {
                    'id': target.id,
                    'student_id': target.student_id,
                    'student_name': target.student.name if target.student else None,
                    'due_date': target.due_date,
                    'status': target.status,
                    'completed_at': target.completed_at,
                }
                for target in item.targets or []
            ],
            'created_at': item.created_at,
            'updated_at': item.updated_at,
        }
        payload.append(serialized)
        rows.append(
            {
                'assignment_id': item.id,
                'title': item.title,
                'subject_name': item.subject.name if item.subject else None,
                'category': item.category,
                'due_date': item.due_date,
                'status': item.status,
                'grading_period_id': item.grading_period_id,
                'weight': item.weight,
                'max_score': item.max_score,
                'target_student_names': ' | '.join(target.student.name for target in item.targets or [] if target.student),
                'grade_summary': ' | '.join(current_grades),
                'created_at': item.created_at,
                'updated_at': item.updated_at,
            }
        )
    return payload, rows, file_refs


async def _collect_submissions(
    db: AsyncSession,
    *,
    family_id: int,
    since: datetime | None,
) -> tuple[list[dict[str, object]], list[dict[str, object]], set[str]]:
    stmt = (
        select(Submission)
        .options(selectinload(Submission.student), selectinload(Submission.assignment))
        .where(Submission.family_id == family_id)
        .order_by(Submission.uploaded_at.asc(), Submission.id.asc())
    )
    stmt = _apply_since(stmt, since, Submission.created_at, Submission.updated_at, Submission.uploaded_at)
    items = list((await db.execute(stmt)).scalars().all())
    file_refs: set[str] = set()
    payload: list[dict[str, object]] = []
    rows: list[dict[str, object]] = []
    for item in items:
        file_refs.add(item.file_path)
        payload.append(
            {
                'id': item.id,
                'assignment_id': item.assignment_id,
                'assignment_title': item.assignment.title if item.assignment else None,
                'student_id': item.student_id,
                'student_name': item.student.name if item.student else None,
                'file_path': item.file_path,
                'original_filename': item.original_filename,
                'file_name': item.file_name,
                'file_type': item.file_type,
                'file_size_bytes': item.file_size_bytes,
                'image_width': item.image_width,
                'image_height': item.image_height,
                'page_count': item.page_count,
                'submission_version': item.submission_version,
                'parent_submission_id': item.parent_submission_id,
                'is_current': item.is_current,
                'ocr_text': item.ocr_text,
                'uploaded_at': item.uploaded_at,
                'created_at': item.created_at,
                'updated_at': item.updated_at,
            }
        )
        rows.append(
            {
                'submission_id': item.id,
                'assignment_id': item.assignment_id,
                'assignment_title': item.assignment.title if item.assignment else None,
                'student_id': item.student_id,
                'student_name': item.student.name if item.student else None,
                'file_path': item.file_path,
                'original_filename': item.original_filename,
                'file_type': item.file_type,
                'file_size_bytes': item.file_size_bytes,
                'submission_version': item.submission_version,
                'is_current': item.is_current,
                'uploaded_at': item.uploaded_at,
            }
        )
    return payload, rows, file_refs


async def _collect_grades(db: AsyncSession, *, family_id: int, since: datetime | None) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    stmt = (
        select(Grade)
        .options(
            selectinload(Grade.student),
            selectinload(Grade.submission).selectinload(Submission.assignment).selectinload(Assignment.subject),
        )
        .where(Grade.family_id == family_id)
        .order_by(Grade.created_at.asc(), Grade.id.asc())
    )
    stmt = _apply_since(stmt, since, Grade.created_at, Grade.updated_at)
    items = list((await db.execute(stmt)).scalars().all())
    payload: list[dict[str, object]] = []
    rows: list[dict[str, object]] = []
    for item in items:
        assignment = item.submission.assignment if item.submission and item.submission.assignment else None
        subject = assignment.subject if assignment and assignment.subject else None
        percentage = round((float(item.score) / float(item.max_score)) * 100, 2) if item.max_score else None
        serialized = {
            'id': item.id,
            'submission_id': item.submission_id,
            'student_id': item.student_id,
            'student_name': item.student.name if item.student else None,
            'assignment_id': assignment.id if assignment else None,
            'assignment_title': assignment.title if assignment else None,
            'subject_id': subject.id if subject else None,
            'subject_name': subject.name if subject else None,
            'score': item.score,
            'max_score': item.max_score,
            'percentage': percentage,
            'letter_grade': item.letter_grade,
            'notes': item.notes,
            'graded_by': item.graded_by,
            'ai_confidence': item.ai_confidence,
            'created_at': item.created_at,
            'updated_at': item.updated_at,
        }
        payload.append(serialized)
        rows.append(
            {
                'grade_id': item.id,
                'student_name': item.student.name if item.student else None,
                'subject_name': subject.name if subject else None,
                'assignment_title': assignment.title if assignment else None,
                'score': item.score,
                'max_score': item.max_score,
                'percentage': percentage,
                'letter_grade': item.letter_grade,
                'graded_by': item.graded_by,
                'ai_confidence': item.ai_confidence,
                'notes': item.notes,
                'created_at': item.created_at,
            }
        )
    return payload, rows


async def _collect_attendance(
    db: AsyncSession,
    *,
    family_id: int,
    since: datetime | None,
) -> tuple[list[dict[str, object]], list[dict[str, object]], set[str]]:
    stmt = (
        select(AttendanceRecord)
        .options(selectinload(AttendanceRecord.student), selectinload(AttendanceRecord.excuse))
        .where(AttendanceRecord.family_id == family_id)
        .order_by(AttendanceRecord.date.asc(), AttendanceRecord.id.asc())
    )
    stmt = _apply_since(stmt, since, AttendanceRecord.created_at, AttendanceRecord.updated_at)
    items = list((await db.execute(stmt)).scalars().all())
    file_refs: set[str] = set()
    payload: list[dict[str, object]] = []
    rows: list[dict[str, object]] = []
    for item in items:
        excuse = item.excuse
        if excuse and excuse.document_path:
            file_refs.add(excuse.document_path)
        serialized = {
            'id': item.id,
            'student_id': item.student_id,
            'student_name': item.student.name if item.student else None,
            'date': item.date.isoformat(),
            'status': item.status,
            'check_in_time': item.check_in_time.isoformat() if item.check_in_time else None,
            'check_out_time': item.check_out_time.isoformat() if item.check_out_time else None,
            'instructional_hours': item.instructional_hours,
            'notes': item.notes,
            'excuse': (
                {
                    'id': excuse.id,
                    'reason': excuse.reason,
                    'document_path': excuse.document_path,
                    'approved_by_user_id': excuse.approved_by_user_id,
                    'approved_at': excuse.approved_at,
                }
                if excuse
                else None
            ),
            'created_at': item.created_at,
            'updated_at': item.updated_at,
        }
        payload.append(serialized)
        rows.append(
            {
                'attendance_id': item.id,
                'student_name': item.student.name if item.student else None,
                'date': item.date.isoformat(),
                'status': item.status,
                'instructional_hours': item.instructional_hours,
                'check_in_time': item.check_in_time.isoformat() if item.check_in_time else None,
                'check_out_time': item.check_out_time.isoformat() if item.check_out_time else None,
                'notes': item.notes,
                'excuse_reason': excuse.reason if excuse else None,
                'excuse_document_path': excuse.document_path if excuse else None,
                'created_at': item.created_at,
                'updated_at': item.updated_at,
            }
        )
    return payload, rows, file_refs


async def _collect_report_cards(
    db: AsyncSession,
    *,
    family_id: int,
    since: datetime | None,
) -> tuple[list[dict[str, object]], list[dict[str, object]], dict[str, bytes]]:
    stmt = (
        select(ReportCard)
        .options(
            selectinload(ReportCard.family),
            selectinload(ReportCard.student),
            selectinload(ReportCard.school_year),
            selectinload(ReportCard.grading_period),
            selectinload(ReportCard.generated_by),
            selectinload(ReportCard.entries).selectinload(ReportCardEntry.subject),
        )
        .where(ReportCard.family_id == family_id)
        .order_by(ReportCard.generated_at.desc(), ReportCard.id.desc())
    )
    stmt = _apply_since(stmt, since, ReportCard.generated_at)
    items = list((await db.execute(stmt)).scalars().all())
    payload = [report_card_to_read(item) for item in items]
    rows: list[dict[str, object]] = []
    pdfs: dict[str, bytes] = {}
    for item in items:
        base_row = {
            'report_card_id': item.id,
            'student_name': item.student.name if item.student else None,
            'school_year_name': item.school_year.name if item.school_year else None,
            'grading_period_name': item.grading_period.name if item.grading_period else None,
            'status': item.status,
            'generated_at': item.generated_at,
            'notes': item.notes,
        }
        if item.entries:
            for entry in item.entries:
                rows.append(
                    {
                        **base_row,
                        'subject_name': entry.subject.name if entry.subject else None,
                        'letter_grade': entry.letter_grade,
                        'percentage': entry.percentage,
                        'gpa_points': entry.gpa_points,
                        'attendance_rate': (entry.attendance_summary or {}).get('attendance_rate'),
                        'teacher_comments': entry.teacher_comments,
                    }
                )
        else:
            rows.append({**base_row, 'subject_name': None, 'letter_grade': None, 'percentage': None, 'gpa_points': None, 'attendance_rate': None, 'teacher_comments': None})
        pdfs[f'pdf/report-cards/report-card-{item.student_id}-{item.grading_period_id}-{item.id}.pdf'] = build_report_card_pdf(item)
    return payload, rows, pdfs


async def _collect_transcripts(
    db: AsyncSession,
    *,
    family_id: int,
    since: datetime | None,
) -> tuple[list[dict[str, object]], list[dict[str, object]], dict[str, bytes]]:
    stmt = (
        select(Transcript)
        .options(
            selectinload(Transcript.family),
            selectinload(Transcript.student),
            selectinload(Transcript.generated_by),
            selectinload(Transcript.entries).selectinload(TranscriptEntry.school_year),
            selectinload(Transcript.entries).selectinload(TranscriptEntry.subject),
        )
        .where(Transcript.family_id == family_id)
        .order_by(Transcript.generated_at.desc(), Transcript.id.desc())
    )
    stmt = _apply_since(stmt, since, Transcript.generated_at)
    items = list((await db.execute(stmt)).scalars().all())
    payload = [transcript_to_read(item) for item in items]
    rows: list[dict[str, object]] = []
    pdfs: dict[str, bytes] = {}
    for item in items:
        base_row = {
            'transcript_id': item.id,
            'student_name': item.student.name if item.student else None,
            'status': item.status,
            'generated_at': item.generated_at,
            'notes': item.notes,
        }
        if item.entries:
            for entry in item.entries:
                rows.append(
                    {
                        **base_row,
                        'school_year_name': entry.school_year.name if entry.school_year else None,
                        'subject_name': entry.subject_name,
                        'credits': entry.credits,
                        'letter_grade': entry.letter_grade,
                        'gpa_points': entry.gpa_points,
                        'weighted_gpa_points': (
                            next(
                                (serialized['weighted_gpa_points'] for serialized in transcript_to_read(item)['entries'] if serialized['id'] == entry.id),
                                None,
                            )
                        ),
                        'is_honors': entry.is_honors,
                        'is_ap': entry.is_ap,
                    }
                )
        else:
            rows.append(
                {
                    **base_row,
                    'school_year_name': None,
                    'subject_name': None,
                    'credits': None,
                    'letter_grade': None,
                    'gpa_points': None,
                    'weighted_gpa_points': None,
                    'is_honors': None,
                    'is_ap': None,
                }
            )
        pdfs[f'pdf/transcripts/transcript-{item.student_id}-{item.id}.pdf'] = build_transcript_pdf(item)
    return payload, rows, pdfs


async def _collect_portfolio_entries(
    db: AsyncSession,
    *,
    family_id: int,
    since: datetime | None,
) -> tuple[list[dict[str, object]], list[dict[str, object]], set[str]]:
    stmt = (
        select(PortfolioEntry)
        .options(
            selectinload(PortfolioEntry.student),
            selectinload(PortfolioEntry.subject),
            selectinload(PortfolioEntry.assignment),
            selectinload(PortfolioEntry.submission),
        )
        .where(PortfolioEntry.family_id == family_id)
        .order_by(PortfolioEntry.date.asc(), PortfolioEntry.id.asc())
    )
    stmt = _apply_since(stmt, since, PortfolioEntry.created_at, PortfolioEntry.updated_at)
    items = list((await db.execute(stmt)).scalars().all())
    file_refs: set[str] = set()
    payload: list[dict[str, object]] = []
    rows: list[dict[str, object]] = []
    for item in items:
        for attachment in item.attachments or []:
            if attachment:
                file_refs.add(str(attachment))
        serialized = {
            'id': item.id,
            'student_id': item.student_id,
            'student_name': item.student.name if item.student else None,
            'entry_type': item.entry_type,
            'title': item.title,
            'description': item.description,
            'date': item.date.isoformat(),
            'subject_id': item.subject_id,
            'subject_name': item.subject.name if item.subject else None,
            'assignment_id': item.assignment_id,
            'assignment_title': item.assignment.title if item.assignment else None,
            'submission_id': item.submission_id,
            'attachments': list(item.attachments or []),
            'tags': list(item.tags or []),
            'created_by_user_id': item.created_by_user_id,
            'created_at': item.created_at,
            'updated_at': item.updated_at,
        }
        payload.append(serialized)
        rows.append(
            {
                'portfolio_entry_id': item.id,
                'student_name': item.student.name if item.student else None,
                'entry_type': item.entry_type,
                'title': item.title,
                'date': item.date.isoformat(),
                'subject_name': item.subject.name if item.subject else None,
                'assignment_title': item.assignment.title if item.assignment else None,
                'submission_id': item.submission_id,
                'attachments': list(item.attachments or []),
                'tags': list(item.tags or []),
                'created_at': item.created_at,
                'updated_at': item.updated_at,
            }
        )
    return payload, rows, file_refs


async def _collect_compliance_reports(
    db: AsyncSession,
    *,
    family_id: int,
    since: datetime | None,
) -> tuple[list[dict[str, object]], list[dict[str, object]], dict[str, bytes]]:
    stmt = (
        select(ComplianceReport)
        .options(
            selectinload(ComplianceReport.family),
            selectinload(ComplianceReport.student),
            selectinload(ComplianceReport.school_year),
            selectinload(ComplianceReport.generated_by),
        )
        .where(ComplianceReport.family_id == family_id)
        .order_by(ComplianceReport.generated_at.desc(), ComplianceReport.id.desc())
    )
    stmt = _apply_since(stmt, since, ComplianceReport.generated_at)
    items = list((await db.execute(stmt)).scalars().all())
    payload = [report_to_read(item) for item in items]
    rows: list[dict[str, object]] = []
    pdfs: dict[str, bytes] = {}
    for item in items:
        period = item.data.get('period') if isinstance(item.data, dict) else None
        rows.append(
            {
                'compliance_report_id': item.id,
                'student_name': item.student.name if item.student else None,
                'school_year_name': item.school_year.name if item.school_year else None,
                'state_code': item.state_code,
                'report_type': item.report_type,
                'status': item.status,
                'period_label': period.get('name') if isinstance(period, dict) else None,
                'generated_at': item.generated_at,
                'notes': item.notes,
                'data': item.data,
            }
        )
        pdfs[f'pdf/compliance/compliance-report-{item.student_id}-{item.report_type.value}-{item.id}.pdf'] = build_compliance_report_pdf(item)
    return payload, rows, pdfs


async def _collect_audit_events(
    db: AsyncSession,
    *,
    family_id: int,
    since: datetime | None,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    stmt = (
        select(AuditEvent)
        .options(selectinload(AuditEvent.actor))
        .where(AuditEvent.family_id == family_id)
        .order_by(AuditEvent.timestamp.asc(), AuditEvent.id.asc())
    )
    stmt = _apply_since(stmt, since, AuditEvent.timestamp)
    items = list((await db.execute(stmt)).scalars().all())
    payload = [
        {
            'id': item.id,
            'actor_user_id': item.actor_user_id,
            'actor_email': item.actor.email if item.actor else None,
            'action': item.action,
            'target_entity_type': item.target_entity_type,
            'target_entity_id': item.target_entity_id,
            'before_snapshot': item.before_snapshot,
            'after_snapshot': item.after_snapshot,
            'ip_address': item.ip_address,
            'user_agent': item.user_agent,
            'timestamp': item.timestamp,
        }
        for item in items
    ]
    rows = [
        {
            'audit_event_id': item.id,
            'timestamp': item.timestamp,
            'actor_user_id': item.actor_user_id,
            'actor_email': item.actor.email if item.actor else None,
            'action': item.action,
            'target_entity_type': item.target_entity_type,
            'target_entity_id': item.target_entity_id,
            'ip_address': item.ip_address,
            'user_agent': item.user_agent,
        }
        for item in items
    ]
    return payload, rows


async def _collect_export_bundle(
    db: AsyncSession,
    *,
    family_id: int,
    export_type: ExportType,
    entity_types: Sequence[str],
    date_from: datetime | None,
) -> tuple[dict[str, object], dict[str, list[dict[str, object]]], dict[str, bytes]]:
    selected = [ExportEntityType(value) for value in entity_types]
    data: dict[str, object] = {}
    csv_files: dict[str, list[dict[str, object]]] = {}
    binary_files: dict[str, bytes] = {}
    file_refs: set[str] = set()

    if ExportEntityType.family in selected:
        family_payload, family_csv = await _collect_family_entity(db, family_id=family_id)
        data['family'] = family_payload
        csv_files.update(family_csv)
    if ExportEntityType.students in selected:
        data['students'], csv_files['students'] = await _collect_students(db, family_id=family_id, since=date_from)
    if ExportEntityType.subjects in selected:
        data['subjects'], csv_files['subjects'] = await _collect_subjects(db, family_id=family_id, since=date_from)
    if ExportEntityType.assignments in selected:
        assignments_payload, assignments_rows, assignment_files = await _collect_assignments(db, family_id=family_id, since=date_from)
        data['assignments'] = assignments_payload
        csv_files['assignments'] = assignments_rows
        file_refs.update(assignment_files)
    if ExportEntityType.submissions in selected:
        submissions_payload, submissions_rows, submission_files = await _collect_submissions(db, family_id=family_id, since=date_from)
        data['submissions'] = submissions_payload
        csv_files['submissions'] = submissions_rows
        file_refs.update(submission_files)
    if ExportEntityType.grades in selected:
        data['grades'], csv_files['grades'] = await _collect_grades(db, family_id=family_id, since=date_from)
    if ExportEntityType.attendance in selected:
        attendance_payload, attendance_rows, attendance_files = await _collect_attendance(db, family_id=family_id, since=date_from)
        data['attendance'] = attendance_payload
        csv_files['attendance'] = attendance_rows
        file_refs.update(attendance_files)
    if ExportEntityType.report_cards in selected:
        report_payload, report_rows, report_pdfs = await _collect_report_cards(db, family_id=family_id, since=date_from)
        data['report_cards'] = report_payload
        csv_files['report_cards'] = report_rows
        binary_files.update(report_pdfs)
    if ExportEntityType.transcripts in selected:
        transcript_payload, transcript_rows, transcript_pdfs = await _collect_transcripts(db, family_id=family_id, since=date_from)
        data['transcripts'] = transcript_payload
        csv_files['transcripts'] = transcript_rows
        binary_files.update(transcript_pdfs)
    if ExportEntityType.portfolio_entries in selected:
        portfolio_payload, portfolio_rows, portfolio_files = await _collect_portfolio_entries(db, family_id=family_id, since=date_from)
        data['portfolio_entries'] = portfolio_payload
        csv_files['portfolio_entries'] = portfolio_rows
        file_refs.update(portfolio_files)
    if ExportEntityType.compliance_reports in selected:
        compliance_payload, compliance_rows, compliance_pdfs = await _collect_compliance_reports(db, family_id=family_id, since=date_from)
        data['compliance_reports'] = compliance_payload
        csv_files['compliance_reports'] = compliance_rows
        binary_files.update(compliance_pdfs)
    if ExportEntityType.audit_events in selected:
        data['audit_events'], csv_files['audit_events'] = await _collect_audit_events(db, family_id=family_id, since=date_from)

    attached_files: dict[str, bytes] = {}
    for ref in sorted(file_refs):
        resolved = _resolve_upload_reference(ref)
        if resolved is None:
            continue
        root = Path(settings.upload_dir).resolve()
        relative = resolved.relative_to(root)
        attached_files[str(Path('attachments') / relative)] = resolved.read_bytes()

    metadata = {
        'export_version': EXPORT_VERSION,
        'created_at': _isoformat(_now_utc()),
        'family_id': family_id,
        'export_type': export_type.value,
        'date_from': _isoformat(date_from),
        'entity_types': [entity.value for entity in selected],
        'entity_counts': {
            key: (len(value) if isinstance(value, list) else (1 if value else 0))
            for key, value in data.items()
        },
        'file_manifest': sorted([*binary_files.keys(), *attached_files.keys()]),
        'portable': {
            'self_contained': True,
            'compatible_with': 'DM-01 import ecosystem',
        },
    }
    return {'metadata': metadata, **data}, csv_files, {**binary_files, **attached_files}


def _build_csv_export(job: ExportJob, csv_rows: dict[str, list[dict[str, object]]]) -> tuple[bytes, str]:
    populated = [(name, rows) for name, rows in csv_rows.items() if name in CSV_HEADERS]
    if len(populated) == 1:
        name, rows = populated[0]
        return _csv_bytes(CSV_HEADERS[name], rows), _file_name_for_job(job, single_entity=name)
    buffer = io.BytesIO()
    with ZipFile(buffer, 'w', compression=ZIP_DEFLATED) as zip_file:
        for name, rows in populated:
            zip_file.writestr(f'csv/{name}.csv', _csv_bytes(CSV_HEADERS[name], rows))
    return buffer.getvalue(), _file_name_for_job(job)


def _build_zip_export(
    job: ExportJob,
    *,
    package: dict[str, object],
    csv_rows: dict[str, list[dict[str, object]]],
    binary_files: dict[str, bytes],
) -> tuple[bytes, str]:
    buffer = io.BytesIO()
    with ZipFile(buffer, 'w', compression=ZIP_DEFLATED) as zip_file:
        zip_file.writestr('metadata.json', _dump_json_bytes(package['metadata']))
        zip_file.writestr('family-export.json', _dump_json_bytes(package))
        for name, rows in csv_rows.items():
            headers = CSV_HEADERS.get(name)
            if headers is None:
                continue
            zip_file.writestr(f'csv/{name}.csv', _csv_bytes(headers, rows))
        for archive_path, content in binary_files.items():
            zip_file.writestr(archive_path.replace('\\', '/'), content)
    return buffer.getvalue(), _file_name_for_job(job)


async def _run_export_job(job_id: int) -> None:
    async with AsyncSessionLocal() as db:
        job = await db.get(ExportJob, job_id)
        if job is None:
            return
        before = _job_snapshot(job)
        job.status = ExportJobStatus.processing
        job.completed_at = None
        await db.commit()
        try:
            package, csv_rows, binary_files = await _collect_export_bundle(
                db,
                family_id=job.family_id,
                export_type=job.export_type,
                entity_types=list(job.entity_types or []),
                date_from=job.date_from,
            )
            if job.format == ExportFormat.json:
                content = _dump_json_bytes(package)
                file_name = _file_name_for_job(job)
            elif job.format == ExportFormat.csv:
                content, file_name = _build_csv_export(job, csv_rows)
            else:
                content, file_name = _build_zip_export(job, package=package, csv_rows=csv_rows, binary_files=binary_files)

            export_dir = Path(settings.upload_dir) / 'exports' / f'family-{job.family_id}'
            export_dir.mkdir(parents=True, exist_ok=True)
            destination = export_dir / file_name
            destination.write_bytes(content)

            job.file_path = str(destination)
            job.file_size = destination.stat().st_size
            job.status = ExportJobStatus.complete
            job.completed_at = _now_utc()
            await db.commit()
        except Exception:
            job.status = ExportJobStatus.failed
            job.file_size = 0
            job.completed_at = _now_utc()
            await db.commit()
            raise
        finally:
            _ = before


async def list_export_jobs(db: AsyncSession, *, family_id: int) -> list[ExportJob]:
    return list(
        (
            await db.execute(
                select(ExportJob).where(ExportJob.family_id == family_id).order_by(ExportJob.created_at.desc(), ExportJob.id.desc())
            )
        ).scalars()
    )


async def create_export_job(
    db: AsyncSession,
    *,
    family_id: int,
    user_id: int,
    export_type: ExportType,
    format: ExportFormat,
    entity_types: Sequence[ExportEntityType],
    date_from: datetime | None,
) -> ExportJob:
    resolved_entities = _resolve_entities(export_type, entity_types)
    export_dir = Path(settings.upload_dir) / 'exports' / f'family-{family_id}'
    export_dir.mkdir(parents=True, exist_ok=True)
    placeholder = export_dir / f'pending-{user_id}-{int(_now_utc().timestamp())}.tmp'
    job = ExportJob(
        family_id=family_id,
        user_id=user_id,
        export_type=export_type,
        format=format,
        status=ExportJobStatus.pending,
        file_path=str(placeholder),
        file_size=0,
        entity_types=[entity.value for entity in resolved_entities],
        date_from=date_from,
        expires_at=_now_utc() + timedelta(days=EXPORT_TTL_DAYS),
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)
    return job


async def delete_export_job(db: AsyncSession, job: ExportJob) -> None:
    if job.file_path:
        path = Path(job.file_path)
        if path.exists() and path.is_file():
            path.unlink()
    await db.delete(job)
    await db.flush()
