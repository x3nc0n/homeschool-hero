from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models import Subject
from backend.schemas.subjects import SubjectCreate, SubjectRead, SubjectUpdate

router = APIRouter(prefix="/subjects", tags=["subjects"])


@router.get("", response_model=list[SubjectRead])
async def list_subjects(db: AsyncSession = Depends(get_db)) -> list[Subject]:
    result = await db.execute(select(Subject).order_by(Subject.name))
    return list(result.scalars().all())


@router.post("", response_model=SubjectRead, status_code=status.HTTP_201_CREATED)
async def create_subject(payload: SubjectCreate, db: AsyncSession = Depends(get_db)) -> Subject:
    existing = await db.execute(select(Subject).where(Subject.name == payload.name))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Subject already exists")

    subject = Subject(name=payload.name, color=payload.color)
    db.add(subject)
    await db.commit()
    await db.refresh(subject)
    return subject


@router.get("/{subject_id}", response_model=SubjectRead)
async def get_subject(subject_id: int, db: AsyncSession = Depends(get_db)) -> Subject:
    subject = await db.get(Subject, subject_id)
    if not subject:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subject not found")
    return subject


@router.put("/{subject_id}", response_model=SubjectRead)
async def update_subject(subject_id: int, payload: SubjectUpdate, db: AsyncSession = Depends(get_db)) -> Subject:
    subject = await db.get(Subject, subject_id)
    if not subject:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subject not found")
    subject.name = payload.name
    subject.color = payload.color
    await db.commit()
    await db.refresh(subject)
    return subject


@router.delete("/{subject_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_subject(subject_id: int, db: AsyncSession = Depends(get_db)) -> None:
    subject = await db.get(Subject, subject_id)
    if not subject:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subject not found")
    await db.delete(subject)
    await db.commit()
