from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models import GradeScale, Subject
from backend.schemas.subjects import SubjectCreate, SubjectRead, SubjectUpdate
from backend.security import AuthSession, get_family_record
from backend.services.authorization import Capability, require_capabilities
from backend.services.cache import invalidate_compliance_cache

router = APIRouter(prefix='/subjects', tags=['subjects'])


@router.get('', response_model=list[SubjectRead])
async def list_subjects(
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.read_curriculum, action='view subjects')),
) -> list[Subject]:
    result = await db.execute(select(Subject).where(Subject.family_id == auth.family_id).order_by(Subject.name))
    return list(result.scalars().all())


@router.post('', response_model=SubjectRead, status_code=status.HTTP_201_CREATED)
async def create_subject(
    payload: SubjectCreate,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.manage_curriculum, action='manage subjects')),
) -> Subject:
    if payload.grade_scale_id is not None:
        grade_scale = await get_family_record(db, GradeScale, payload.grade_scale_id, auth.family_id)
        if not grade_scale:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Grade scale not found')
    existing = await db.execute(
        select(Subject).where(Subject.family_id == auth.family_id, Subject.name == payload.name.strip())
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='Subject already exists')

    subject = Subject(
        family_id=auth.family_id,
        name=payload.name.strip(),
        color=payload.color,
        grading_mode=payload.grading_mode,
        grade_scale_id=payload.grade_scale_id,
    )
    db.add(subject)
    await db.commit()
    invalidate_compliance_cache(family_id=auth.family_id)
    await db.refresh(subject)
    return subject


@router.get('/{subject_id}', response_model=SubjectRead)
async def get_subject(
    subject_id: int,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.read_curriculum, action='view subjects')),
) -> Subject:
    subject = await get_family_record(db, Subject, subject_id, auth.family_id)
    if not subject:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Subject not found')
    return subject


@router.put('/{subject_id}', response_model=SubjectRead)
async def update_subject(
    subject_id: int,
    payload: SubjectUpdate,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.manage_curriculum, action='manage subjects')),
) -> Subject:
    subject = await get_family_record(db, Subject, subject_id, auth.family_id)
    if not subject:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Subject not found')
    if payload.grade_scale_id is not None:
        grade_scale = await get_family_record(db, GradeScale, payload.grade_scale_id, auth.family_id)
        if not grade_scale:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Grade scale not found')

    existing = await db.execute(
        select(Subject).where(
            Subject.family_id == auth.family_id,
            Subject.name == payload.name.strip(),
            Subject.id != subject_id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='Subject already exists')

    subject.name = payload.name.strip()
    subject.color = payload.color
    subject.grading_mode = payload.grading_mode
    subject.grade_scale_id = payload.grade_scale_id
    await db.commit()
    invalidate_compliance_cache(family_id=auth.family_id)
    await db.refresh(subject)
    return subject


@router.delete('/{subject_id}', status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_subject(
    subject_id: int,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.manage_curriculum, action='manage subjects')),
) -> None:
    subject = await get_family_record(db, Subject, subject_id, auth.family_id)
    if not subject:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Subject not found')
    await db.delete(subject)
    await db.commit()
    invalidate_compliance_cache(family_id=auth.family_id)
