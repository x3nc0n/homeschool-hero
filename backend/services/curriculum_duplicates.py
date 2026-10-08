"""Family-scoped duplicate detection for imported curricula.

Comparison is structural: curriculum titles, filenames, and import sources are ignored.
Names are normalized (NFKC, casefold, cosmetic punctuation/whitespace) before comparing
subject, unit, and lesson structure. Grade levels, explicit editions, and standards
alignment act as discriminators so different editions or grade bands are not flagged.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
import re
import unicodedata
from typing import Any, Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import ImportedCurriculum, ImportedCurriculumLesson, ImportedCurriculumSubject, ImportedCurriculumUnit
from backend.schemas.curriculum import CurriculumImportDocument

REASON_EXACT = 'exact_curriculum'
REASON_PARTIAL = 'partial_overlap'
MIN_PARTIAL_LESSONS = 2
MAX_EVIDENCE_ITEMS = 50

_APOSTROPHES = str.maketrans('', '', "'\u2018\u2019\u02bc\u0060\u00b4")
_GRADE_NOISE_WORDS = {'grade', 'grades', 'gr', 'level', 'levels', 'year', 'years'}
_GRADE_ALIASES = {
    'kindergarten': 'k',
    'kinder': 'k',
    'pre k': 'prek',
    'pk': 'prek',
    'prekindergarten': 'prek',
    'pre kindergarten': 'prek',
}
_ORDINAL = re.compile(r'^(\d+)(st|nd|rd|th)$')
_GENERIC_LESSON_PATTERN = re.compile(
    r'^(lesson|day|week|chapter|session|class|part|section|module|unit|topic|activity|worksheet|quiz|test|exam|review)'
    r'( ?(\d+|[ivxlc]+|[a-z]))?$'
)
_GENERIC_LESSON_NAMES = frozenset(
    {
        'introduction',
        'intro',
        'overview',
        'review',
        'unit review',
        'chapter review',
        'test',
        'unit test',
        'chapter test',
        'quiz',
        'assessment',
        'final exam',
        'midterm',
        'exam',
        'practice',
        'conclusion',
        'wrap up',
        'project',
        'final project',
        'summary',
        'vocabulary',
        'warm up',
    }
)


def normalize_name(value: str | None) -> str:
    """Normalize a display name for structural comparison."""
    if not value:
        return ''
    text = unicodedata.normalize('NFKC', value).casefold()
    text = unicodedata.normalize('NFKC', text).translate(_APOSTROPHES)
    text = ''.join(' ' if unicodedata.category(char).startswith('P') else char for char in text)
    return ' '.join(text.split())


def _normalize_grade(value: str) -> str:
    text = normalize_name(value)
    if text in _GRADE_ALIASES:
        return _GRADE_ALIASES[text]
    tokens = [token for token in text.split() if token not in _GRADE_NOISE_WORDS]
    normalized: list[str] = []
    for token in tokens:
        ordinal = _ORDINAL.match(token)
        token = ordinal.group(1) if ordinal else token
        normalized.append(_GRADE_ALIASES.get(token, token))
    joined = ' '.join(normalized)
    return _GRADE_ALIASES.get(joined, joined)


def normalize_grades(values: Iterable[str] | None) -> frozenset[str]:
    return frozenset(grade for grade in (_normalize_grade(str(value)) for value in (values or [])) if grade)


def _normalize_tags(values: Iterable[str] | None) -> frozenset[str]:
    return frozenset(tag for tag in (normalize_name(str(value)) for value in (values or [])) if tag)


def is_generic_lesson(normalized_name: str) -> bool:
    return normalized_name in _GENERIC_LESSON_NAMES or bool(_GENERIC_LESSON_PATTERN.match(normalized_name))


def _edition_from_metadata(metadata: Any) -> str | None:
    if not isinstance(metadata, dict):
        return None
    edition = metadata.get('edition')
    if not edition:
        extensions = metadata.get('extensions')
        if isinstance(extensions, dict):
            edition = extensions.get('edition')
    if isinstance(edition, (str, int, float)) and str(edition).strip():
        return str(edition).strip()
    return None


@dataclass
class _Unit:
    key: str
    name: str
    lessons: dict[str, str] = field(default_factory=dict)


@dataclass
class _Subject:
    key: str
    name: str
    grades: frozenset[str]
    edition: str | None
    units: list[_Unit] = field(default_factory=list)


@dataclass
class _Curriculum:
    id: int | None
    name: str
    grade_levels: list[str]
    edition: str | None
    standards: frozenset[str]
    subjects: list[_Subject] = field(default_factory=list)

    def triples(self) -> frozenset[tuple[str, str, str]]:
        return frozenset(
            (subject.key, unit.key, lesson_key)
            for subject in self.subjects
            for unit in subject.units
            for lesson_key in unit.lessons
        )


@dataclass(frozen=True)
class DuplicateMatch:
    id: int
    name: str
    grade_levels: list[str]
    edition: str | None
    reason: str
    matched_subjects: list[str]
    matched_units: list[str]
    matched_lessons: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            'id': self.id,
            'name': self.name,
            'grade_levels': list(self.grade_levels),
            'edition': self.edition,
            'reason': self.reason,
            'matched_subjects': list(self.matched_subjects),
            'matched_units': list(self.matched_units),
            'matched_lessons': list(self.matched_lessons),
        }


def _subject_grades(subject_grades: Iterable[str] | None, curriculum_grades: frozenset[str]) -> frozenset[str]:
    grades = normalize_grades(subject_grades)
    return grades or curriculum_grades


def _candidate_structure(payload: CurriculumImportDocument) -> _Curriculum:
    curriculum_grades = normalize_grades(payload.metadata.grade_levels)
    curriculum_edition = payload.metadata.edition or _edition_from_metadata(payload.metadata.extensions)
    candidate = _Curriculum(
        id=None,
        name=payload.name,
        grade_levels=list(payload.metadata.grade_levels),
        edition=curriculum_edition,
        standards=_normalize_tags(payload.metadata.standards_alignment),
    )
    for subject_payload in payload.subjects:
        subject = _Subject(
            key=normalize_name(subject_payload.name),
            name=subject_payload.name,
            grades=_subject_grades(subject_payload.metadata.grade_levels, curriculum_grades),
            edition=subject_payload.metadata.edition or curriculum_edition,
        )
        for unit_payload in subject_payload.units:
            unit = _Unit(key=normalize_name(unit_payload.name), name=unit_payload.name)
            for lesson_payload in unit_payload.lessons:
                unit.lessons.setdefault(normalize_name(lesson_payload.name), lesson_payload.name)
            subject.units.append(unit)
        candidate.subjects.append(subject)
    return candidate


async def load_family_curricula(db: AsyncSession, family_id: int) -> list[_Curriculum]:
    """Load family-scoped curriculum structure with four column-only queries."""
    curriculum_rows = (
        await db.execute(
            select(
                ImportedCurriculum.id,
                ImportedCurriculum.name,
                ImportedCurriculum.grade_levels,
                ImportedCurriculum.standards_alignment,
                ImportedCurriculum.curriculum_metadata,
            )
            .where(ImportedCurriculum.family_id == family_id)
            .order_by(ImportedCurriculum.id)
        )
    ).all()
    if not curriculum_rows:
        return []
    curricula: dict[int, _Curriculum] = {}
    curriculum_grades: dict[int, frozenset[str]] = {}
    for row in curriculum_rows:
        grades = list(row.grade_levels or [])
        curriculum_grades[row.id] = normalize_grades(grades)
        curricula[row.id] = _Curriculum(
            id=row.id,
            name=row.name,
            grade_levels=grades,
            edition=_edition_from_metadata(row.curriculum_metadata),
            standards=_normalize_tags(row.standards_alignment),
        )

    subject_rows = (
        await db.execute(
            select(
                ImportedCurriculumSubject.id,
                ImportedCurriculumSubject.curriculum_id,
                ImportedCurriculumSubject.name,
                ImportedCurriculumSubject.grade_levels,
                ImportedCurriculumSubject.subject_metadata,
            )
            .join(ImportedCurriculum, ImportedCurriculum.id == ImportedCurriculumSubject.curriculum_id)
            .where(ImportedCurriculum.family_id == family_id)
            .order_by(ImportedCurriculumSubject.curriculum_id, ImportedCurriculumSubject.sequence_order, ImportedCurriculumSubject.id)
        )
    ).all()
    subjects: dict[int, _Subject] = {}
    for row in subject_rows:
        curriculum = curricula[row.curriculum_id]
        subject = _Subject(
            key=normalize_name(row.name),
            name=row.name,
            grades=_subject_grades(row.grade_levels, curriculum_grades[row.curriculum_id]),
            edition=_edition_from_metadata(row.subject_metadata) or curriculum.edition,
        )
        subjects[row.id] = subject
        curriculum.subjects.append(subject)

    unit_rows = (
        await db.execute(
            select(ImportedCurriculumUnit.id, ImportedCurriculumUnit.subject_id, ImportedCurriculumUnit.name)
            .join(ImportedCurriculumSubject, ImportedCurriculumSubject.id == ImportedCurriculumUnit.subject_id)
            .join(ImportedCurriculum, ImportedCurriculum.id == ImportedCurriculumSubject.curriculum_id)
            .where(ImportedCurriculum.family_id == family_id)
            .order_by(ImportedCurriculumUnit.subject_id, ImportedCurriculumUnit.sequence_order, ImportedCurriculumUnit.id)
        )
    ).all()
    units: dict[int, _Unit] = {}
    for row in unit_rows:
        unit = _Unit(key=normalize_name(row.name), name=row.name)
        units[row.id] = unit
        subjects[row.subject_id].units.append(unit)

    lesson_rows = (
        await db.execute(
            select(ImportedCurriculumLesson.unit_id, ImportedCurriculumLesson.name)
            .join(ImportedCurriculumUnit, ImportedCurriculumUnit.id == ImportedCurriculumLesson.unit_id)
            .join(ImportedCurriculumSubject, ImportedCurriculumSubject.id == ImportedCurriculumUnit.subject_id)
            .join(ImportedCurriculum, ImportedCurriculum.id == ImportedCurriculumSubject.curriculum_id)
            .where(ImportedCurriculum.family_id == family_id)
            .order_by(ImportedCurriculumLesson.unit_id, ImportedCurriculumLesson.sequence_order, ImportedCurriculumLesson.id)
        )
    ).all()
    for row in lesson_rows:
        units[row.unit_id].lessons.setdefault(normalize_name(row.name), row.name)
    return list(curricula.values())


def _normalize_edition(value: str | None) -> str:
    return normalize_name(value)


def _subjects_compatible(candidate: _Subject, existing: _Subject) -> bool:
    if candidate.grades and existing.grades and candidate.grades != existing.grades:
        return False
    candidate_edition = _normalize_edition(candidate.edition)
    existing_edition = _normalize_edition(existing.edition)
    if candidate_edition and existing_edition and candidate_edition != existing_edition:
        return False
    return True


def _curricula_compatible(candidate: _Curriculum, existing: _Curriculum) -> bool:
    if candidate.standards and existing.standards and candidate.standards.isdisjoint(existing.standards):
        return False
    return True


def _dedupe(values: Iterable[str]) -> list[str]:
    seen: dict[str, None] = {}
    for value in values:
        if value not in seen:
            seen[value] = None
        if len(seen) >= MAX_EVIDENCE_ITEMS:
            break
    return list(seen)


def _compare(candidate: _Curriculum, existing: _Curriculum) -> DuplicateMatch | None:
    if existing.id is None or not _curricula_compatible(candidate, existing):
        return None

    candidate_by_key: dict[str, list[_Subject]] = defaultdict(list)
    for subject in candidate.subjects:
        candidate_by_key[subject.key].append(subject)
    compatible_pairs = [
        (candidate_subject, existing_subject)
        for existing_subject in existing.subjects
        for candidate_subject in candidate_by_key.get(existing_subject.key, [])
        if _subjects_compatible(candidate_subject, existing_subject)
    ]
    if not compatible_pairs:
        return None

    match_kwargs = {
        'id': existing.id,
        'name': existing.name,
        'grade_levels': list(existing.grade_levels),
        'edition': existing.edition,
    }

    candidate_triples = candidate.triples()
    has_specific_lesson = any(not is_generic_lesson(lesson_key) for _, _, lesson_key in candidate_triples)
    if has_specific_lesson and candidate_triples == existing.triples():
        all_pairs_compatible = all(
            _subjects_compatible(candidate_subject, existing_subject)
            for existing_subject in existing.subjects
            for candidate_subject in candidate_by_key.get(existing_subject.key, [])
        )
        if all_pairs_compatible:
            return DuplicateMatch(
                **match_kwargs,
                reason=REASON_EXACT,
                matched_subjects=_dedupe(subject.name for subject in existing.subjects),
                matched_units=_dedupe(unit.name for subject in existing.subjects for unit in subject.units),
                matched_lessons=_dedupe(
                    lesson for subject in existing.subjects for unit in subject.units for lesson in unit.lessons.values()
                ),
            )

    matched_subjects: list[str] = []
    matched_units: list[str] = []
    matched_lessons: list[str] = []
    for candidate_subject, existing_subject in compatible_pairs:
        candidate_units: dict[str, list[_Unit]] = defaultdict(list)
        for unit in candidate_subject.units:
            candidate_units[unit.key].append(unit)
        for existing_unit in existing_subject.units:
            candidate_lessons = {
                lesson_key
                for candidate_unit in candidate_units.get(existing_unit.key, [])
                for lesson_key in candidate_unit.lessons
            }
            shared = [
                lesson_key
                for lesson_key in existing_unit.lessons
                if lesson_key in candidate_lessons and not is_generic_lesson(lesson_key)
            ]
            if len(shared) < MIN_PARTIAL_LESSONS:
                continue
            matched_subjects.append(existing_subject.name)
            matched_units.append(existing_unit.name)
            matched_lessons.extend(existing_unit.lessons[lesson_key] for lesson_key in shared)
    if not matched_units:
        return None
    return DuplicateMatch(
        **match_kwargs,
        reason=REASON_PARTIAL,
        matched_subjects=_dedupe(matched_subjects),
        matched_units=_dedupe(matched_units),
        matched_lessons=_dedupe(matched_lessons),
    )


async def find_duplicate_matches(
    db: AsyncSession,
    *,
    family_id: int,
    payload: CurriculumImportDocument,
) -> list[DuplicateMatch]:
    candidate = _candidate_structure(payload)
    matches: list[DuplicateMatch] = []
    for existing in await load_family_curricula(db, family_id):
        match = _compare(candidate, existing)
        if match is not None:
            matches.append(match)
    return matches


def find_internal_duplicate_paths(payload: CurriculumImportDocument) -> list[str]:
    """Return safe JSON paths for names that would violate the import unique constraints."""
    paths: list[str] = []
    seen_subjects: set[str] = set()
    for subject_index, subject in enumerate(payload.subjects):
        if subject.name in seen_subjects:
            paths.append(f'subjects[{subject_index}].name')
        seen_subjects.add(subject.name)
        seen_units: set[str] = set()
        for unit_index, unit in enumerate(subject.units):
            if unit.name in seen_units:
                paths.append(f'subjects[{subject_index}].units[{unit_index}].name')
            seen_units.add(unit.name)
            seen_lessons: set[str] = set()
            for lesson_index, lesson in enumerate(unit.lessons):
                if lesson.name in seen_lessons:
                    paths.append(f'subjects[{subject_index}].units[{unit_index}].lessons[{lesson_index}].name')
                seen_lessons.add(lesson.name)
    return paths
