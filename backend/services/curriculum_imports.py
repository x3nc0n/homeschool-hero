from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.models import ImportedCurriculum, ImportedCurriculumLesson, ImportedCurriculumSubject, ImportedCurriculumUnit
from backend.schemas.curriculum import CurriculumImportDocument


def imported_curriculum_load_options() -> tuple:
    return (
        selectinload(ImportedCurriculum.subjects)
        .selectinload(ImportedCurriculumSubject.units)
        .selectinload(ImportedCurriculumUnit.lessons),
    )


async def create_imported_curriculum(
    db: AsyncSession,
    *,
    family_id: int,
    user_id: int,
    payload: CurriculumImportDocument,
) -> ImportedCurriculum:
    duplicate = (
        await db.execute(
            select(ImportedCurriculum).where(
                ImportedCurriculum.family_id == family_id,
                ImportedCurriculum.name == payload.name,
            )
        )
    ).scalar_one_or_none()
    if duplicate is not None:
        raise ValueError('Imported curriculum already exists')

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
                lesson = ImportedCurriculumLesson(
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
                db.add(lesson)

    await db.commit()
    return curriculum
