from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Iterable
from typing import Any
import weakref

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.models import (
    Family,
    ImportedCurriculum,
    ImportedCurriculumLesson,
    ImportedCurriculumSubject,
    ImportedCurriculumUnit,
)
from backend.schemas.curriculum import CurriculumImportDocument
from backend.services.curriculum_duplicates import (
    DuplicateMatch,
    find_duplicate_matches,
    find_internal_duplicate_paths,
)

NAME_CONFLICT_MESSAGE = 'Imported curriculum already exists'
DUPLICATE_CONFLICT_MESSAGE = 'This curriculum appears to duplicate an existing curriculum. Review and acknowledge the matches to import it anyway.'
DUPLICATE_NAMES_MESSAGE = 'Curriculum import contains duplicate subject, unit, or lesson names'
_NAME_CONSTRAINT = 'uq_imported_curricula_family_name'

ClaimHook = Callable[[AsyncSession], Awaitable[None]]
CreatedHook = Callable[[AsyncSession, ImportedCurriculum], Awaitable[None]]


class CurriculumImportConflict(ValueError):
    """Base class for import gate failures. Subclasses ValueError for existing callers."""

    status_code = 409
    code = 'curriculum_import_conflict'
    message_key = 'errors.curriculum.import_conflict'

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details


class CurriculumNameConflictError(CurriculumImportConflict):
    code = 'curriculum_import_name_conflict'
    message_key = 'errors.curriculum.import_name_conflict'

    def __init__(self) -> None:
        super().__init__(NAME_CONFLICT_MESSAGE)


class CurriculumDuplicateConflictError(CurriculumImportConflict):
    code = 'curriculum_import_duplicate_conflict'
    message_key = 'errors.curriculum.import_duplicate_conflict'

    def __init__(self, matches: list[DuplicateMatch]) -> None:
        super().__init__(DUPLICATE_CONFLICT_MESSAGE, details={'matches': [match.to_dict() for match in matches]})
        self.matches = matches


class CurriculumDuplicateNamesError(CurriculumImportConflict):
    status_code = 422
    code = 'curriculum_import_duplicate_names'
    message_key = 'errors.curriculum.import_duplicate_names'

    def __init__(self, paths: list[str]) -> None:
        super().__init__(DUPLICATE_NAMES_MESSAGE, details={'paths': paths})
        self.paths = paths


_family_locks: weakref.WeakValueDictionary[int, asyncio.Lock] = weakref.WeakValueDictionary()


def _family_lock(family_id: int) -> asyncio.Lock:
    lock = _family_locks.get(family_id)
    if lock is None:
        lock = asyncio.Lock()
        _family_locks[family_id] = lock
    return lock


def imported_curriculum_load_options() -> tuple:
    return (
        selectinload(ImportedCurriculum.subjects)
        .selectinload(ImportedCurriculumSubject.units)
        .selectinload(ImportedCurriculumUnit.lessons),
    )


async def _name_exists(db: AsyncSession, *, family_id: int, name: str) -> bool:
    return (
        await db.execute(
            select(ImportedCurriculum.id).where(ImportedCurriculum.family_id == family_id, ImportedCurriculum.name == name)
        )
    ).first() is not None


async def check_import_gates(
    db: AsyncSession,
    *,
    family_id: int,
    payload: CurriculumImportDocument,
    acknowledged_duplicate_ids: Iterable[int] = (),
) -> list[DuplicateMatch]:
    """Run the shared import gate. Acknowledgements only subtract from the current family-scoped matches."""
    paths = find_internal_duplicate_paths(payload)
    if paths:
        raise CurriculumDuplicateNamesError(paths)
    if await _name_exists(db, family_id=family_id, name=payload.name):
        raise CurriculumNameConflictError()
    matches = await find_duplicate_matches(db, family_id=family_id, payload=payload)
    acknowledged = set(acknowledged_duplicate_ids)
    if any(match.id not in acknowledged for match in matches):
        raise CurriculumDuplicateConflictError(matches)
    return matches


def _is_name_constraint_violation(exc: IntegrityError) -> bool:
    return _NAME_CONSTRAINT in str(getattr(exc, 'orig', exc)) or 'imported_curricula.family_id, imported_curricula.name' in str(
        getattr(exc, 'orig', exc)
    )


async def create_imported_curriculum(
    db: AsyncSession,
    *,
    family_id: int,
    user_id: int,
    payload: CurriculumImportDocument,
    acknowledged_duplicate_ids: Iterable[int] = (),
    claim: ClaimHook | None = None,
    on_created: CreatedHook | None = None,
) -> ImportedCurriculum:
    """Gate, persist, and commit an imported curriculum atomically for the family.

    An in-process per-family lock plus a family row lock (``FOR UPDATE`` on PostgreSQL)
    serialize the claim, duplicate gate, insert, and commit so concurrent confirmations
    cannot both pass the gate.
    """
    async with _family_lock(family_id):
        try:
            await db.execute(select(Family.id).where(Family.id == family_id).with_for_update())
            if claim is not None:
                await claim(db)
            await check_import_gates(
                db,
                family_id=family_id,
                payload=payload,
                acknowledged_duplicate_ids=acknowledged_duplicate_ids,
            )
            curriculum = await _insert_curriculum(db, family_id=family_id, user_id=user_id, payload=payload)
            if on_created is not None:
                await on_created(db, curriculum)
            await db.commit()
        except IntegrityError as exc:
            await db.rollback()
            if _is_name_constraint_violation(exc) or await _name_exists(db, family_id=family_id, name=payload.name):
                raise CurriculumNameConflictError() from None
            raise
        except BaseException:
            await db.rollback()
            raise
    return curriculum


async def _insert_curriculum(
    db: AsyncSession,
    *,
    family_id: int,
    user_id: int,
    payload: CurriculumImportDocument,
) -> ImportedCurriculum:
    curriculum = ImportedCurriculum(
        family_id=family_id,
        created_by_user_id=user_id,
        name=payload.name,
        description=payload.description,
        source=payload.source,
        schema_version=payload.schema_version,
        grade_levels=payload.metadata.grade_levels,
        standards_alignment=payload.metadata.standards_alignment,
        estimated_hours=payload.metadata.estimated_hours,
        prerequisites=payload.metadata.prerequisites,
        curriculum_metadata=payload.metadata.model_dump(mode='json'),
        payload=payload.model_dump(mode='json'),
    )
    db.add(curriculum)
    await db.flush()

    for subject_index, subject_payload in enumerate(payload.subjects, start=1):
        subject = ImportedCurriculumSubject(
            curriculum_id=curriculum.id,
            name=subject_payload.name,
            description=subject_payload.description,
            sequence_order=subject_index,
            grade_levels=subject_payload.metadata.grade_levels,
            standards_alignment=subject_payload.metadata.standards_alignment,
            estimated_hours=subject_payload.metadata.estimated_hours,
            prerequisites=subject_payload.metadata.prerequisites,
            subject_metadata=subject_payload.metadata.model_dump(mode='json'),
        )
        db.add(subject)
        await db.flush()
        for unit_index, unit_payload in enumerate(subject_payload.units, start=1):
            unit = ImportedCurriculumUnit(
                subject_id=subject.id,
                name=unit_payload.name,
                description=unit_payload.description,
                sequence_order=unit_index,
                standards_alignment=unit_payload.metadata.standards_alignment,
                estimated_hours=unit_payload.metadata.estimated_hours,
                prerequisites=unit_payload.metadata.prerequisites,
                unit_metadata=unit_payload.metadata.model_dump(mode='json'),
            )
            db.add(unit)
            await db.flush()
            for lesson_index, lesson_payload in enumerate(unit_payload.lessons, start=1):
                db.add(
                    ImportedCurriculumLesson(
                        unit_id=unit.id,
                        name=lesson_payload.name,
                        description=lesson_payload.description,
                        sequence_order=lesson_index,
                        estimated_minutes=lesson_payload.estimated_minutes,
                        objectives=lesson_payload.objectives,
                        resources=[item.model_dump(mode='json') for item in lesson_payload.resources],
                        standards_alignment=lesson_payload.metadata.standards_alignment,
                        prerequisites=lesson_payload.metadata.prerequisites,
                        lesson_metadata=lesson_payload.metadata.model_dump(mode='json'),
                    )
                )
    await db.flush()
    return curriculum
