from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timezone
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import String, and_, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.models import (
    Assignment,
    AssignmentStatus,
    AssignmentTarget,
    AssignmentTargetStatus,
    AuditAction,
    AuditEvent,
    CalendarEvent,
    CurriculumLesson,
    CurriculumPackage,
    CurriculumUnit,
    Grade,
    GradingPeriod,
    Resource,
    ResourceType,
    Student,
    Subject,
    Submission,
    Term,
    User,
)
from backend.schemas.grades import GradeHistoryItem
from backend.schemas.search import SearchEntityType, SearchResponse, SearchResultRead
from backend.security import AuthSession
from backend.services.authorization import Capability, get_student_scope_id, has_capability

_assignment_status_values = {item.value: item for item in AssignmentStatus}
_assignment_target_status_values = {item.value: item for item in AssignmentTargetStatus}


@dataclass(slots=True)
class SearchFilters:
    q: str | None
    entity_type: SearchEntityType | None
    student_id: int | None
    subject_id: int | None
    term_id: int | None
    grading_period_id: int | None
    status: str | None
    date_from: date | None
    date_to: date | None
    score_min: float | None
    score_max: float | None
    page: int
    page_size: int


def _normalize_floor(value: date | None) -> datetime | None:
    if value is None:
        return None
    return datetime.combine(value, time.min, tzinfo=timezone.utc)


def _normalize_ceil(value: date | None) -> datetime | None:
    if value is None:
        return None
    return datetime.combine(value, time.max, tzinfo=timezone.utc)


def _normalize_query(value: str | None) -> str | None:
    if value is None:
        return None
    candidate = value.strip()
    return candidate or None


def _make_snippet(*parts: str | None) -> str:
    for part in parts:
        if part and part.strip():
            return part.strip()[:240]
    return 'No additional details available.'


def _search_clause(db: AsyncSession, q: str | None, *columns: Any):
    normalized = _normalize_query(q)
    if normalized is None:
        return None
    if db.bind is not None and db.bind.dialect.name == 'postgresql':
        document = func.concat_ws(' ', *[func.coalesce(cast(column, String), '') for column in columns])
        return func.to_tsvector('simple', document).op('@@')(func.websearch_to_tsquery('simple', normalized))
    lowered = f'%{normalized.lower()}%'
    return or_(*[func.lower(cast(column, String)).like(lowered) for column in columns])


def _result(
    entity_type: SearchEntityType,
    entity_id: int | str,
    title: str,
    snippet: str,
    link: str,
    *,
    created_at: datetime | None = None,
    student_id: int | None = None,
    subject_id: int | None = None,
    status: str | None = None,
) -> SearchResultRead:
    return SearchResultRead(
        entity_type=entity_type,
        entity_id=str(entity_id),
        title=title,
        snippet=snippet,
        link=link,
        created_at=created_at,
        student_id=student_id,
        subject_id=subject_id,
        status=status,
    )


def _sort_timestamp(value: datetime | None) -> float:
    if value is None:
        return float('-inf')
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.timestamp()


def _apply_assignment_status(stmt, status_value: str):
    lowered = status_value.strip().lower()
    if lowered in _assignment_status_values:
        return stmt.where(Assignment.status == _assignment_status_values[lowered])
    if lowered in _assignment_target_status_values:
        return stmt.where(Assignment.targets.any(AssignmentTarget.status == _assignment_target_status_values[lowered]))
    return stmt


async def _search_assignments(db: AsyncSession, auth: AuthSession, filters: SearchFilters) -> list[SearchResultRead]:
    if not has_capability(auth, Capability.read_curriculum):
        return []
    stmt = (
        select(Assignment)
        .options(
            selectinload(Assignment.subject),
            selectinload(Assignment.grading_period).selectinload(GradingPeriod.term),
            selectinload(Assignment.targets).selectinload(AssignmentTarget.student),
        )
        .join(Subject, Subject.id == Assignment.subject_id)
        .where(Assignment.family_id == auth.family_id)
    )
    scoped_student_id = filters.student_id
    if auth.role == 'student_viewer':
        scoped_student_id = get_student_scope_id(auth)
        if filters.student_id is not None and filters.student_id != scoped_student_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Role 'student_viewer' is not allowed to search another student's assignments.",
            )
    if scoped_student_id is not None:
        stmt = stmt.where(or_(~Assignment.targets.any(), Assignment.targets.any(AssignmentTarget.student_id == scoped_student_id)))
    if filters.subject_id is not None:
        stmt = stmt.where(Assignment.subject_id == filters.subject_id)
    if filters.grading_period_id is not None:
        stmt = stmt.where(Assignment.grading_period_id == filters.grading_period_id)
    if filters.term_id is not None:
        stmt = stmt.join(GradingPeriod, GradingPeriod.id == Assignment.grading_period_id).where(GradingPeriod.term_id == filters.term_id)
    if filters.status:
        stmt = _apply_assignment_status(stmt, filters.status)
    due_from = _normalize_floor(filters.date_from)
    due_to = _normalize_ceil(filters.date_to)
    if due_from is not None:
        stmt = stmt.where(or_(Assignment.due_date >= due_from, Assignment.targets.any(AssignmentTarget.due_date >= due_from)))
    if due_to is not None:
        stmt = stmt.where(or_(Assignment.due_date <= due_to, Assignment.targets.any(AssignmentTarget.due_date <= due_to)))
    search_clause = _search_clause(db, filters.q, Assignment.title, Assignment.description, Assignment.rubric_description, Subject.name)
    if search_clause is not None:
        stmt = stmt.where(search_clause)
    assignments = list((await db.execute(stmt.order_by(Assignment.updated_at.desc(), Assignment.id.desc()))).scalars().unique().all())
    return [
        _result(
            SearchEntityType.assignment,
            assignment.id,
            assignment.title,
            _make_snippet(
                assignment.description,
                assignment.rubric_description,
                f'{assignment.subject.name if assignment.subject else "Unassigned"} · {assignment.status.value}',
            ),
            f'/assignments?search={assignment.title}',
            created_at=assignment.updated_at,
            subject_id=assignment.subject_id,
            status=assignment.status.value,
        )
        for assignment in assignments
    ]


async def _query_grade_history(db: AsyncSession, auth: AuthSession, filters: SearchFilters) -> list[GradeHistoryItem]:
    scoped_student_id = filters.student_id
    if auth.role == 'student_viewer':
        scoped_student_id = get_student_scope_id(auth)
        if filters.student_id is not None and filters.student_id != scoped_student_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Role 'student_viewer' is not allowed to search another student's grades.",
            )
    stmt = (
        select(
            Grade.id,
            Grade.student_id,
            Student.name,
            Subject.id,
            Subject.name,
            Assignment.id,
            Assignment.title,
            Grade.score,
            Grade.max_score,
            Grade.letter_grade,
            Grade.graded_by,
            Grade.created_at,
            Assignment.grading_period_id,
            GradingPeriod.name,
            Grade.notes,
        )
        .join(Student, Student.id == Grade.student_id)
        .join(Submission, Submission.id == Grade.submission_id)
        .join(Assignment, Assignment.id == Submission.assignment_id)
        .join(Subject, Subject.id == Assignment.subject_id)
        .outerjoin(GradingPeriod, GradingPeriod.id == Assignment.grading_period_id)
        .where(Grade.family_id == auth.family_id)
    )
    if scoped_student_id is not None:
        stmt = stmt.where(Grade.student_id == scoped_student_id)
    if filters.subject_id is not None:
        stmt = stmt.where(Subject.id == filters.subject_id)
    if filters.grading_period_id is not None:
        stmt = stmt.where(Assignment.grading_period_id == filters.grading_period_id)
    if filters.term_id is not None:
        stmt = stmt.join(Term, Term.id == GradingPeriod.term_id).where(Term.id == filters.term_id)
    if filters.date_from is not None:
        stmt = stmt.where(Grade.created_at >= _normalize_floor(filters.date_from))
    if filters.date_to is not None:
        stmt = stmt.where(Grade.created_at <= _normalize_ceil(filters.date_to))
    if filters.score_min is not None:
        stmt = stmt.where((Grade.score / Grade.max_score) * 100.0 >= filters.score_min)
    if filters.score_max is not None:
        stmt = stmt.where((Grade.score / Grade.max_score) * 100.0 <= filters.score_max)
    search_clause = _search_clause(db, filters.q, Grade.notes, Assignment.title, Student.name, Subject.name, Grade.letter_grade)
    if search_clause is not None:
        stmt = stmt.where(search_clause)
    rows = (await db.execute(stmt.order_by(Grade.created_at.desc(), Grade.id.desc()))).all()
    return [
        GradeHistoryItem(
            grade_id=row[0],
            student_id=row[1],
            student_name=row[2],
            subject_id=row[3],
            subject_name=row[4],
            assignment_id=row[5],
            assignment_title=row[6],
            score=float(row[7]),
            max_score=float(row[8]),
            percent=round((float(row[7]) / float(row[8])) * 100, 2),
            letter_grade=row[9],
            graded_by=row[10],
            created_at=row[11],
            grading_period_id=row[12],
            grading_period_name=row[13],
            notes=row[14],
        )
        for row in rows
    ]


async def _search_grades(db: AsyncSession, auth: AuthSession, filters: SearchFilters) -> list[SearchResultRead]:
    if not has_capability(auth, Capability.read_grades):
        return []
    return [
        _result(
            SearchEntityType.grade,
            item.grade_id,
            f'{item.student_name} · {item.assignment_title}',
            _make_snippet(item.notes, f'{item.subject_name} · {item.score}/{item.max_score} ({item.percent:.1f}%)'),
            f'/grades?search={item.assignment_title}',
            created_at=item.created_at,
            student_id=item.student_id,
            subject_id=item.subject_id,
            status=item.letter_grade or item.graded_by.value,
        )
        for item in await _query_grade_history(db, auth, filters)
    ]


async def _search_students(db: AsyncSession, auth: AuthSession, filters: SearchFilters) -> list[SearchResultRead]:
    if not has_capability(auth, Capability.read_students):
        return []
    stmt = select(Student).where(Student.family_id == auth.family_id)
    scoped_student_id = filters.student_id
    if auth.role == 'student_viewer':
        scoped_student_id = get_student_scope_id(auth)
        if filters.student_id is not None and filters.student_id != scoped_student_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Role 'student_viewer' is not allowed to search another student's record.",
            )
    if scoped_student_id is not None:
        stmt = stmt.where(Student.id == scoped_student_id)
    if filters.date_from is not None:
        stmt = stmt.where(Student.created_at >= _normalize_floor(filters.date_from))
    if filters.date_to is not None:
        stmt = stmt.where(Student.created_at <= _normalize_ceil(filters.date_to))
    search_clause = _search_clause(db, filters.q, Student.name)
    if search_clause is not None:
        stmt = stmt.where(search_clause)
    students = list((await db.execute(stmt.order_by(Student.name))).scalars().all())
    return [
        _result(
            SearchEntityType.student,
            student.id,
            student.name,
            f'Student record · ID {student.id}',
            f'/students?search={student.name}',
            created_at=student.created_at,
            student_id=student.id,
        )
        for student in students
    ]


async def _search_subjects(db: AsyncSession, auth: AuthSession, filters: SearchFilters) -> list[SearchResultRead]:
    if not has_capability(auth, Capability.read_curriculum):
        return []
    stmt = select(Subject).where(Subject.family_id == auth.family_id)
    if filters.subject_id is not None:
        stmt = stmt.where(Subject.id == filters.subject_id)
    if filters.date_from is not None:
        stmt = stmt.where(Subject.created_at >= _normalize_floor(filters.date_from))
    if filters.date_to is not None:
        stmt = stmt.where(Subject.created_at <= _normalize_ceil(filters.date_to))
    search_clause = _search_clause(db, filters.q, Subject.name)
    if search_clause is not None:
        stmt = stmt.where(search_clause)
    subjects = list((await db.execute(stmt.order_by(Subject.name))).scalars().all())
    return [
        _result(
            SearchEntityType.subject,
            subject.id,
            subject.name,
            f'Subject · {subject.color}',
            f'/subjects?search={subject.name}',
            created_at=subject.created_at,
            subject_id=subject.id,
        )
        for subject in subjects
    ]


async def _search_audit_logs(db: AsyncSession, auth: AuthSession, filters: SearchFilters) -> list[SearchResultRead]:
    if not has_capability(auth, Capability.manage_family):
        return []
    stmt = (
        select(AuditEvent, User.display_name)
        .join(User, User.id == AuditEvent.actor_user_id)
        .where(AuditEvent.family_id == auth.family_id)
    )
    if filters.date_from is not None:
        stmt = stmt.where(AuditEvent.timestamp >= _normalize_floor(filters.date_from))
    if filters.date_to is not None:
        stmt = stmt.where(AuditEvent.timestamp <= _normalize_ceil(filters.date_to))
    if filters.status and filters.status in {action.value for action in AuditAction}:
        stmt = stmt.where(AuditEvent.action == AuditAction(filters.status))
    search_clause = _search_clause(
        db,
        filters.q,
        AuditEvent.action,
        AuditEvent.target_entity_type,
        AuditEvent.target_entity_id,
        AuditEvent.before_snapshot,
        AuditEvent.after_snapshot,
        User.display_name,
        User.email,
    )
    if search_clause is not None:
        stmt = stmt.where(search_clause)
    rows = (await db.execute(stmt.order_by(AuditEvent.timestamp.desc(), AuditEvent.id.desc()))).all()
    return [
        _result(
            SearchEntityType.audit_log,
            event.id,
            f'{event.action.value.replace("_", " ").title()} · {event.target_entity_type}',
            _make_snippet(display_name, event.target_entity_id, str(event.after_snapshot or event.before_snapshot or '')),
            f'/audit?entity_type={event.target_entity_type}',
            created_at=event.timestamp,
            status=event.action.value,
        )
        for event, display_name in rows
    ]


async def _search_curriculum(db: AsyncSession, auth: AuthSession, filters: SearchFilters) -> list[SearchResultRead]:
    if not has_capability(auth, Capability.read_curriculum):
        return []
    package_stmt = (
        select(CurriculumPackage, Subject.name)
        .join(Subject, Subject.id == CurriculumPackage.subject_id)
        .where(CurriculumPackage.family_id == auth.family_id)
    )
    if filters.subject_id is not None:
        package_stmt = package_stmt.where(CurriculumPackage.subject_id == filters.subject_id)
    if filters.date_from is not None:
        package_stmt = package_stmt.where(CurriculumPackage.created_at >= _normalize_floor(filters.date_from))
    if filters.date_to is not None:
        package_stmt = package_stmt.where(CurriculumPackage.created_at <= _normalize_ceil(filters.date_to))
    package_search = _search_clause(
        db,
        filters.q,
        CurriculumPackage.name,
        CurriculumPackage.description,
        Subject.name,
    )
    if package_search is not None:
        package_stmt = package_stmt.where(package_search)

    unit_stmt = (
        select(CurriculumUnit, CurriculumPackage, Subject.name)
        .join(CurriculumPackage, CurriculumPackage.id == CurriculumUnit.package_id)
        .join(Subject, Subject.id == CurriculumPackage.subject_id)
        .where(CurriculumPackage.family_id == auth.family_id)
    )
    if filters.subject_id is not None:
        unit_stmt = unit_stmt.where(CurriculumPackage.subject_id == filters.subject_id)
    unit_search = _search_clause(db, filters.q, CurriculumUnit.name, CurriculumUnit.description, Subject.name)
    if unit_search is not None:
        unit_stmt = unit_stmt.where(unit_search)

    lesson_stmt = (
        select(CurriculumLesson, CurriculumUnit, CurriculumPackage, Subject.name)
        .join(CurriculumUnit, CurriculumUnit.id == CurriculumLesson.unit_id)
        .join(CurriculumPackage, CurriculumPackage.id == CurriculumUnit.package_id)
        .join(Subject, Subject.id == CurriculumPackage.subject_id)
        .where(CurriculumPackage.family_id == auth.family_id)
    )
    if filters.subject_id is not None:
        lesson_stmt = lesson_stmt.where(CurriculumPackage.subject_id == filters.subject_id)
    lesson_search = _search_clause(db, filters.q, CurriculumLesson.name, CurriculumLesson.description, Subject.name)
    if lesson_search is not None:
        lesson_stmt = lesson_stmt.where(lesson_search)

    package_rows = (await db.execute(package_stmt.order_by(CurriculumPackage.updated_at.desc()))).all()
    unit_rows = (await db.execute(unit_stmt.order_by(CurriculumUnit.updated_at.desc()))).all()
    lesson_rows = (await db.execute(lesson_stmt.order_by(CurriculumLesson.updated_at.desc()))).all()

    results = [
        _result(
            SearchEntityType.curriculum,
            package.id,
            package.name,
            _make_snippet(package.description, f'{subject_name} package'),
            f'/curriculum?search={package.name}',
            created_at=package.updated_at,
            subject_id=package.subject_id,
        )
        for package, subject_name in package_rows
    ]
    results.extend(
        _result(
            SearchEntityType.curriculum,
            unit.id,
            f'{package.name} · {unit.name}',
            _make_snippet(unit.description, f'{subject_name} unit'),
            f'/curriculum?search={unit.name}',
            created_at=unit.updated_at,
            subject_id=package.subject_id,
        )
        for unit, package, subject_name in unit_rows
    )
    results.extend(
        _result(
            SearchEntityType.curriculum,
            lesson.id,
            f'{package.name} · {unit.name} · {lesson.name}',
            _make_snippet(lesson.description, f'{subject_name} lesson'),
            f'/curriculum?search={lesson.name}',
            created_at=lesson.updated_at,
            subject_id=package.subject_id,
        )
        for lesson, unit, package, subject_name in lesson_rows
    )
    return results


async def _search_resources(db: AsyncSession, auth: AuthSession, filters: SearchFilters) -> list[SearchResultRead]:
    if not has_capability(auth, Capability.read_curriculum):
        return []
    stmt = select(Resource).options(
        selectinload(Resource.lessons).selectinload(CurriculumLesson.unit).selectinload(CurriculumUnit.package)
    ).where(Resource.family_id == auth.family_id)
    if filters.date_from is not None:
        stmt = stmt.where(Resource.created_at >= _normalize_floor(filters.date_from))
    if filters.date_to is not None:
        stmt = stmt.where(Resource.created_at <= _normalize_ceil(filters.date_to))
    if filters.status and filters.status in {item.value for item in ResourceType}:
        stmt = stmt.where(Resource.resource_type == ResourceType(filters.status))
    search_clause = _search_clause(db, filters.q, Resource.name, Resource.description, Resource.url)
    if search_clause is not None:
        stmt = stmt.where(search_clause)
    resources = list((await db.execute(stmt.order_by(Resource.updated_at.desc(), Resource.id.desc()))).scalars().all())
    results: list[SearchResultRead] = []
    for resource in resources:
        lesson_subject_ids = {
            lesson.unit.package.subject_id
            for lesson in resource.lessons
            if lesson.unit is not None and lesson.unit.package is not None
        }
        if filters.subject_id is not None and filters.subject_id not in lesson_subject_ids:
            continue
        entity_type = SearchEntityType.note if resource.resource_type == ResourceType.note else SearchEntityType.resource
        results.append(
            _result(
                entity_type,
                resource.id,
                resource.name,
                _make_snippet(resource.description, ', '.join(resource.tags), resource.url),
                f'/resources?search={resource.name}',
                created_at=resource.updated_at,
                subject_id=next(iter(lesson_subject_ids), None),
                status=resource.resource_type.value,
            )
        )
    return results


async def _search_calendar_items(db: AsyncSession, auth: AuthSession, filters: SearchFilters) -> list[SearchResultRead]:
    if not has_capability(auth, Capability.read_curriculum):
        return []
    stmt = select(CalendarEvent).where(CalendarEvent.family_id == auth.family_id)
    if filters.date_from is not None:
        stmt = stmt.where(CalendarEvent.date >= filters.date_from)
    if filters.date_to is not None:
        stmt = stmt.where(CalendarEvent.date <= filters.date_to)
    search_clause = _search_clause(db, filters.q, CalendarEvent.name, CalendarEvent.notes, CalendarEvent.event_type)
    if search_clause is not None:
        stmt = stmt.where(search_clause)
    items = list((await db.execute(stmt.order_by(CalendarEvent.date.desc(), CalendarEvent.id.desc()))).scalars().all())
    results: list[SearchResultRead] = []
    for item in items:
        entity_type = SearchEntityType.attendance_note if item.notes else SearchEntityType.notification
        results.append(
            _result(
                entity_type,
                item.id,
                item.name,
                _make_snippet(item.notes, f'{item.event_type.value} on {item.date.isoformat()}'),
                '/calendar',
                created_at=datetime.combine(item.date, time.min, tzinfo=timezone.utc),
                status=item.event_type.value,
            )
        )
    return results


async def search_entities(
    db: AsyncSession,
    auth: AuthSession,
    *,
    q: str | None,
    entity_type: SearchEntityType | None,
    student_id: int | None,
    subject_id: int | None,
    term_id: int | None,
    grading_period_id: int | None,
    status: str | None,
    date_from: date | None,
    date_to: date | None,
    score_min: float | None,
    score_max: float | None,
    page: int,
    page_size: int,
) -> SearchResponse:
    filters = SearchFilters(
        q=_normalize_query(q),
        entity_type=entity_type,
        student_id=student_id,
        subject_id=subject_id,
        term_id=term_id,
        grading_period_id=grading_period_id,
        status=_normalize_query(status),
        date_from=date_from,
        date_to=date_to,
        score_min=score_min,
        score_max=score_max,
        page=page,
        page_size=page_size,
    )

    searchers = {
        SearchEntityType.assignment: _search_assignments,
        SearchEntityType.grade: _search_grades,
        SearchEntityType.student: _search_students,
        SearchEntityType.subject: _search_subjects,
        SearchEntityType.audit_log: _search_audit_logs,
        SearchEntityType.curriculum: _search_curriculum,
        SearchEntityType.resource: _search_resources,
        SearchEntityType.note: _search_resources,
        SearchEntityType.attendance_note: _search_calendar_items,
        SearchEntityType.notification: _search_calendar_items,
    }

    if filters.entity_type is not None:
        combined = await searchers[filters.entity_type](db, auth, filters)
        combined = [item for item in combined if item.entity_type == filters.entity_type]
    else:
        combined = []
        for searcher in (
            _search_assignments,
            _search_grades,
            _search_students,
            _search_subjects,
            _search_calendar_items,
            _search_audit_logs,
            _search_curriculum,
            _search_resources,
        ):
            combined.extend(await searcher(db, auth, filters))

    combined.sort(key=lambda item: (_sort_timestamp(item.created_at), item.title.lower()), reverse=True)
    facets: dict[str, int] = {}
    for item in combined:
        facets[item.entity_type.value] = facets.get(item.entity_type.value, 0) + 1
    total = len(combined)
    total_pages = (total + page_size - 1) // page_size if total else 0
    start = (page - 1) * page_size
    return SearchResponse(
        items=combined[start : start + page_size],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        facets=facets,
    )
