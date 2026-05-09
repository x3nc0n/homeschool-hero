from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Sequence
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import and_, delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.models import (
    Assignment,
    Grade,
    GradeCategory,
    GradeScale,
    Student,
    Subject,
    SubjectGradingMode,
    Submission,
)

DEFAULT_GRADE_SCALE_NAME = 'Default 4.0 Scale'
DEFAULT_GRADE_SCALE_RANGES = [
    {'letter': 'A', 'min': 90, 'max': 100, 'gpa_points': 4.0},
    {'letter': 'B', 'min': 80, 'max': 89.99, 'gpa_points': 3.0},
    {'letter': 'C', 'min': 70, 'max': 79.99, 'gpa_points': 2.0},
    {'letter': 'D', 'min': 60, 'max': 69.99, 'gpa_points': 1.0},
    {'letter': 'F', 'min': 0, 'max': 59.99, 'gpa_points': 0.0},
]
DEFAULT_CATEGORY_ORDER = ['homework', 'quiz', 'test', 'project', 'participation', 'extra_credit', 'other']


def _round_percent(value: float | None) -> float | None:
    return None if value is None else round(float(value), 2)


def _normalize_range_entry(entry: dict[str, Any]) -> dict[str, Any]:
    return {
        'letter': str(entry.get('letter', '')).strip().upper(),
        'min': round(float(entry.get('min', 0)), 2),
        'max': round(float(entry.get('max', 0)), 2),
        'gpa_points': round(float(entry.get('gpa_points', 0)), 2),
    }


def normalize_grade_scale_ranges(ranges: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted((_normalize_range_entry(entry) for entry in ranges), key=lambda entry: (-entry['min'], entry['letter']))


def map_percent_to_grade(scale: GradeScale | dict[str, Any] | None, percent: float | None) -> tuple[str | None, float | None]:
    if percent is None or scale is None:
        return None, None
    ranges = scale.ranges if isinstance(scale, GradeScale) else scale.get('ranges', [])
    for entry in normalize_grade_scale_ranges(ranges):
        if entry['min'] <= percent <= entry['max']:
            return entry['letter'], entry['gpa_points']
    return None, None


async def ensure_default_grade_scale(db: AsyncSession, family_id: int) -> GradeScale:
    existing = (
        await db.execute(
            select(GradeScale)
            .where(GradeScale.family_id == family_id, GradeScale.is_default.is_(True))
            .order_by(GradeScale.id)
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing

    fallback = (
        await db.execute(select(GradeScale).where(GradeScale.family_id == family_id).order_by(GradeScale.id))
    ).scalars().first()
    if fallback is not None:
        fallback.is_default = True
        await db.flush()
        return fallback

    scale = GradeScale(
        family_id=family_id,
        name=DEFAULT_GRADE_SCALE_NAME,
        ranges=list(DEFAULT_GRADE_SCALE_RANGES),
        is_default=True,
    )
    db.add(scale)
    await db.flush()
    return scale


async def list_grade_scales(db: AsyncSession, family_id: int) -> list[GradeScale]:
    await ensure_default_grade_scale(db, family_id)
    result = await db.execute(
        select(GradeScale).where(GradeScale.family_id == family_id).order_by(GradeScale.is_default.desc(), GradeScale.name, GradeScale.id)
    )
    return list(result.scalars().all())


async def save_grade_scales(db: AsyncSession, family_id: int, scales: Sequence[dict[str, Any]]) -> list[GradeScale]:
    if not scales:
        raise ValueError('At least one grade scale is required')
    if sum(1 for scale in scales if scale.get('is_default')) != 1:
        raise ValueError('Exactly one grade scale must be marked as default')

    existing = {
        scale.id: scale
        for scale in (
            await db.execute(select(GradeScale).where(GradeScale.family_id == family_id))
        ).scalars().all()
    }
    keep_ids: set[int] = set()
    for payload in scales:
        scale_id = payload.get('id')
        if scale_id is not None:
            scale = existing.get(scale_id)
            if scale is None:
                raise ValueError('Grade scale does not belong to this family')
        else:
            scale = GradeScale(family_id=family_id)
            db.add(scale)
        scale.name = str(payload['name']).strip()
        scale.ranges = normalize_grade_scale_ranges(payload['ranges'])
        scale.is_default = bool(payload.get('is_default'))
        await db.flush()
        keep_ids.add(scale.id)

    for scale_id, scale in existing.items():
        if scale_id in keep_ids:
            continue
        subject_rows = await db.execute(select(Subject).where(Subject.grade_scale_id == scale_id))
        for subject in subject_rows.scalars().all():
            subject.grade_scale_id = None
        await db.delete(scale)

    await db.flush()
    return await list_grade_scales(db, family_id)


def build_default_grade_categories(category_names: Iterable[str]) -> list[dict[str, Any]]:
    names = []
    for name in DEFAULT_CATEGORY_ORDER:
        if name in category_names and name != 'extra_credit':
            names.append(name)
    if not names:
        names = ['homework']
    weight = round(1 / len(names), 4)
    categories = []
    running_total = 0.0
    for index, name in enumerate(names):
        category_weight = weight if index < len(names) - 1 else round(1.0 - running_total, 4)
        running_total = round(running_total + category_weight, 4)
        categories.append({'id': None, 'name': name, 'weight': category_weight, 'drop_lowest': 0})
    if 'extra_credit' in category_names:
        categories.append({'id': None, 'name': 'extra_credit', 'weight': 0.0, 'drop_lowest': 0})
    return categories


async def list_or_build_grade_categories(db: AsyncSession, family_id: int, subject_id: int) -> list[dict[str, Any]]:
    categories = (
        await db.execute(
            select(GradeCategory)
            .where(GradeCategory.family_id == family_id, GradeCategory.subject_id == subject_id)
            .order_by(GradeCategory.name, GradeCategory.id)
        )
    ).scalars().all()
    if categories:
        return [
            {'id': category.id, 'name': category.name, 'weight': round(category.weight, 4), 'drop_lowest': category.drop_lowest or 0}
            for category in categories
        ]

    assignment_rows = await db.execute(
        select(Assignment.category).where(Assignment.family_id == family_id, Assignment.subject_id == subject_id)
    )
    names = [row[0].value if hasattr(row[0], 'value') else str(row[0]) for row in assignment_rows.all()]
    return build_default_grade_categories(names)


async def save_grade_categories(
    db: AsyncSession,
    *,
    family_id: int,
    subject_id: int,
    categories: Sequence[dict[str, Any]],
) -> list[GradeCategory]:
    if not categories:
        raise ValueError('At least one grade category is required')
    total_weight = round(sum(float(category['weight']) for category in categories), 4)
    if total_weight != 1.0:
        raise ValueError('Grade category weights must add up to 1.0')

    subject = (
        await db.execute(select(Subject).where(Subject.id == subject_id, Subject.family_id == family_id))
    ).scalar_one_or_none()
    if subject is None:
        raise ValueError('Subject not found')

    existing = {
        category.id: category
        for category in (
            await db.execute(
                select(GradeCategory).where(GradeCategory.family_id == family_id, GradeCategory.subject_id == subject_id)
            )
        ).scalars().all()
    }
    keep_ids: set[int] = set()
    for payload in categories:
        category_id = payload.get('id')
        if category_id is not None:
            category = existing.get(category_id)
            if category is None:
                raise ValueError('Grade category does not belong to this subject')
        else:
            category = GradeCategory(family_id=family_id, subject_id=subject_id)
            db.add(category)
        category.name = str(payload['name']).strip().lower()
        category.weight = float(payload['weight'])
        category.drop_lowest = int(payload.get('drop_lowest') or 0)
        await db.flush()
        keep_ids.add(category.id)

    for category_id, category in existing.items():
        if category_id not in keep_ids:
            await db.delete(category)

    await db.flush()
    result = await db.execute(
        select(GradeCategory)
        .where(GradeCategory.family_id == family_id, GradeCategory.subject_id == subject_id)
        .order_by(GradeCategory.name, GradeCategory.id)
    )
    return list(result.scalars().all())


def _category_sort_key(name: str) -> tuple[int, str]:
    try:
        return DEFAULT_CATEGORY_ORDER.index(name), name
    except ValueError:
        return len(DEFAULT_CATEGORY_ORDER), name


def _build_category_summary(
    category: dict[str, Any],
    items: list[dict[str, Any]],
    grading_mode: SubjectGradingMode,
) -> dict[str, Any]:
    graded_items = [item for item in items if item['percent'] is not None]
    dropped_keys: set[int] = set()
    if graded_items and category.get('drop_lowest'):
        drop_count = min(int(category['drop_lowest']), len(graded_items))
        for item in sorted(graded_items, key=lambda row: (row['percent'], row['assignment_id']))[:drop_count]:
            dropped_keys.add(item['assignment_id'])

    for item in items:
        item['is_dropped'] = item['assignment_id'] in dropped_keys

    counted_items = [item for item in graded_items if item['assignment_id'] not in dropped_keys]
    average_percent = None
    if counted_items:
        if grading_mode == SubjectGradingMode.points:
            earned = sum(float(item['score'] or 0) for item in counted_items)
            possible = sum(float(item['max_score'] or 0) for item in counted_items)
            average_percent = (earned / possible) * 100 if possible else None
        else:
            average_percent = sum(float(item['percent']) for item in counted_items) / len(counted_items)

    weighted_percent = None if average_percent is None else average_percent * float(category['weight'])
    return {
        'id': category.get('id'),
        'name': category['name'],
        'weight': round(float(category['weight']), 4),
        'drop_lowest': int(category.get('drop_lowest') or 0),
        'average_percent': _round_percent(average_percent),
        'weighted_percent': _round_percent(weighted_percent),
        'assignment_count': len(items),
        'graded_count': len(graded_items),
        'items': items,
    }


def _build_subject_view(
    *,
    subject: Subject,
    scale: GradeScale,
    category_configs: list[dict[str, Any]],
    items: list[dict[str, Any]],
) -> dict[str, Any]:
    grouped_items: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in items:
        grouped_items[item['category']].append(item)

    categories = []
    weighted_total = 0.0
    active_weight = 0.0
    for category in sorted(category_configs, key=lambda item: _category_sort_key(item['name'])):
        category_items = sorted(
            grouped_items.get(category['name'], []),
            key=lambda row: (
                row['due_date'] or row['graded_at'] or row['created_at'],
                row['assignment_title'],
                row['assignment_id'],
            ),
        )
        summary = _build_category_summary(category, category_items, subject.grading_mode)
        categories.append(summary)
        if summary['average_percent'] is not None and summary['weight'] > 0:
            weighted_total += float(summary['average_percent']) * float(summary['weight'])
            active_weight += float(summary['weight'])

    overall_percent = weighted_total / active_weight if active_weight else None
    letter_grade, gpa_points = map_percent_to_grade(scale, overall_percent)
    return {
        'subject_id': subject.id,
        'subject_name': subject.name,
        'subject_color': subject.color,
        'grading_mode': subject.grading_mode.value,
        'grade_scale_id': scale.id,
        'overall_percent': _round_percent(overall_percent),
        'letter_grade': letter_grade,
        'gpa_points': None if gpa_points is None else round(float(gpa_points), 2),
        'categories': categories,
        'assignments': sum(len(category['items']) for category in categories),
        'graded_assignments': sum(category['graded_count'] for category in categories),
        'scale': {
            'id': scale.id,
            'name': scale.name,
            'ranges': normalize_grade_scale_ranges(scale.ranges),
            'is_default': scale.is_default,
        },
    }


def _running_progress(subject: Subject, scale: GradeScale, category_configs: list[dict[str, Any]], items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    graded_items = sorted(
        [item for item in items if item['percent'] is not None],
        key=lambda row: (row['graded_at'] or row['due_date'] or row['created_at'], row['assignment_id']),
    )
    seen_ids: set[int] = set()
    trends: list[dict[str, Any]] = []
    for item in graded_items:
        seen_ids.add(item['assignment_id'])
        scoped_items = []
        for source in items:
            clone = dict(source)
            if clone['assignment_id'] not in seen_ids:
                clone['score'] = None
                clone['max_score'] = clone['max_score']
                clone['percent'] = None
                clone['letter_grade'] = None
                clone['graded_at'] = None
            scoped_items.append(clone)
        aggregate = _build_subject_view(subject=subject, scale=scale, category_configs=category_configs, items=scoped_items)
        trends.append(
            {
                'assignment_id': item['assignment_id'],
                'date': (item['graded_at'] or item['due_date'] or item['created_at']).isoformat(),
                'overall_percent': aggregate['overall_percent'],
                'letter_grade': aggregate['letter_grade'],
                'gpa_points': aggregate['gpa_points'],
            }
        )
    return trends


async def calculate_gradebook(
    db: AsyncSession,
    *,
    family_id: int,
    student_id: int,
    subject_id: int | None = None,
    grading_period_id: int | None = None,
) -> dict[str, Any]:
    student = (
        await db.execute(select(Student).where(Student.id == student_id, Student.family_id == family_id))
    ).scalar_one_or_none()
    if student is None:
        raise ValueError('Student not found')

    default_scale = await ensure_default_grade_scale(db, family_id)
    await db.flush()

    stmt = (
        select(Assignment, Subject, Submission, Grade)
        .join(Subject, Subject.id == Assignment.subject_id)
        .outerjoin(
            Submission,
            and_(
                Submission.assignment_id == Assignment.id,
                Submission.student_id == student_id,
                Submission.is_current.is_(True),
            ),
        )
        .outerjoin(Grade, Grade.submission_id == Submission.id)
        .where(Assignment.family_id == family_id)
    )
    if subject_id is not None:
        stmt = stmt.where(Assignment.subject_id == subject_id)
    if grading_period_id is not None:
        stmt = stmt.where(Assignment.grading_period_id == grading_period_id)
    stmt = stmt.where(
        or_(
            Submission.id.is_not(None),
            Assignment.targets.any(student_id=student_id),
        )
    ).order_by(Subject.name, Assignment.due_date, Assignment.id)

    rows = (await db.execute(stmt)).all()
    if not rows:
        return {
            'student_id': student.id,
            'student_name': student.name,
            'subject_id': subject_id,
            'grading_period_id': grading_period_id,
            'generated_at': datetime.now(UTC).isoformat(),
            'subjects': [],
            'gpa': None,
        }

    subject_ids = sorted({row[1].id for row in rows})
    subject_result = await db.execute(
        select(Subject)
        .options(selectinload(Subject.grade_categories), selectinload(Subject.grade_scale))
        .where(Subject.id.in_(subject_ids))
    )
    subjects = {subject.id: subject for subject in subject_result.scalars().all()}

    items_by_subject: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for assignment, subject, submission, grade in rows:
        percent = None if grade is None else (float(grade.score) / float(grade.max_score)) * 100
        items_by_subject[subject.id].append(
            {
                'assignment_id': assignment.id,
                'assignment_title': assignment.title,
                'category': assignment.category.value,
                'grading_period_id': assignment.grading_period_id,
                'due_date': assignment.due_date,
                'status': assignment.status.value,
                'score': None if grade is None else float(grade.score),
                'max_score': float(grade.max_score if grade is not None else assignment.max_score),
                'percent': percent,
                'letter_grade': grade.letter_grade if grade is not None else None,
                'submission_id': submission.id if submission is not None else None,
                'grade_id': grade.id if grade is not None else None,
                'graded_at': grade.created_at if grade is not None else None,
                'created_at': assignment.created_at,
                'is_dropped': False,
            }
        )

    subject_views = []
    for current_subject_id in subject_ids:
        current_subject = subjects[current_subject_id]
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
            else build_default_grade_categories(item['category'] for item in items_by_subject[current_subject_id])
        )
        view = _build_subject_view(
            subject=current_subject,
            scale=scale,
            category_configs=category_configs,
            items=[dict(item) for item in items_by_subject[current_subject_id]],
        )
        running = {
            entry['assignment_id']: entry
            for entry in _running_progress(current_subject, scale, category_configs, [dict(item) for item in items_by_subject[current_subject_id]])
        }
        for category in view['categories']:
            for item in category['items']:
                progress = running.get(item['assignment_id'])
                item['running_overall_percent'] = progress['overall_percent'] if progress else None
        subject_views.append(view)

    gpa_values = [subject['gpa_points'] for subject in subject_views if subject['gpa_points'] is not None]
    return {
        'student_id': student.id,
        'student_name': student.name,
        'subject_id': subject_id,
        'grading_period_id': grading_period_id,
        'generated_at': datetime.now(UTC).isoformat(),
        'subjects': subject_views,
        'gpa': round(sum(float(value) for value in gpa_values) / len(gpa_values), 2) if gpa_values else None,
    }


async def calculate_gradebook_trends(
    db: AsyncSession,
    *,
    family_id: int,
    student_id: int,
    subject_id: int | None = None,
    grading_period_id: int | None = None,
) -> dict[str, Any]:
    gradebook = await calculate_gradebook(
        db,
        family_id=family_id,
        student_id=student_id,
        subject_id=subject_id,
        grading_period_id=grading_period_id,
    )
    trends = []
    for subject in gradebook['subjects']:
        points = []
        for category in subject['categories']:
            for item in category['items']:
                if item.get('graded_at') and item.get('running_overall_percent') is not None:
                    points.append(
                        {
                            'assignment_id': item['assignment_id'],
                            'assignment_title': item['assignment_title'],
                            'date': item['graded_at'].isoformat(),
                            'overall_percent': item['running_overall_percent'],
                            'letter_grade': subject['letter_grade'],
                        }
                    )
        points.sort(key=lambda row: (row['date'], row['assignment_id']))
        trends.append(
            {
                'subject_id': subject['subject_id'],
                'subject_name': subject['subject_name'],
                'subject_color': subject['subject_color'],
                'points': points,
            }
        )
    return {
        'student_id': gradebook['student_id'],
        'student_name': gradebook['student_name'],
        'subject_id': subject_id,
        'grading_period_id': grading_period_id,
        'series': trends,
    }


async def calculate_gradebook_summary(
    db: AsyncSession,
    *,
    family_id: int,
    student_id: int,
) -> dict[str, Any]:
    gradebook = await calculate_gradebook(db, family_id=family_id, student_id=student_id)
    return {
        'student_id': gradebook['student_id'],
        'student_name': gradebook['student_name'],
        'gpa': gradebook['gpa'],
        'subjects': [
            {
                'subject_id': subject['subject_id'],
                'subject_name': subject['subject_name'],
                'subject_color': subject['subject_color'],
                'overall_percent': subject['overall_percent'],
                'letter_grade': subject['letter_grade'],
                'gpa_points': subject['gpa_points'],
                'assignments': subject['assignments'],
                'graded_assignments': subject['graded_assignments'],
            }
            for subject in gradebook['subjects']
        ],
    }
