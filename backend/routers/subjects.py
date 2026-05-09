from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models import Subject
from backend.schemas.subjects import SubjectCreate, SubjectRead, SubjectUpdate
from backend.security import AuthSession, get_auth_session, get_family_record

router = APIRouter(prefix='/subjects', tags=['subjects'])


@router.get('', response_model=list[SubjectRead])
async def list_subjects(
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(get_auth_session),
) -> list[Subject]:
    result = await db.execute(select(Subject).where(Subject.family_id == auth.family_id).order_by(Subject.name))
    return list(result.scalars().all())


@router.post('', response_model=SubjectRead, status_code=status.HTTP_201_CREATED)
async def create_subject(
    payload: SubjectCreate,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(get_auth_session),
) -> Subject:
    existing = await db.execute(
        select(Subject).where(Subject.family_id == auth.family_id, Subject.name == payload.name.strip())
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='Subject already exists')

    subject = Subject(family_id=auth.family_id, name=payload.name.strip(), color=payload.color)
    db.add(subject)
    await db.commit()
    await db.refresh(subject)
    return subject


@router.get('/{subject_id}', response_model=SubjectRead)
async def get_subject(
    subject_id: int,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(get_auth_session),
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
    auth: AuthSession = Depends(get_auth_session),
) -> Subject:
    subject = await get_family_record(db, Subject, subject_id, auth.family_id)
    if not subject:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Subject not found')

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
    await db.commit()
    await db.refresh(subject)
    return subject


@router.delete('/{subject_id}', status_code=status.HTTP_204_NO_CONTENT)
async def delete_subject(
    subject_id: int,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(get_auth_session),
) -> None:
    subject = await get_family_record(db, Subject, subject_id, auth.family_id)
    if not subject:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Subject not found')
    await db.delete(subject)
    await db.commit()
