from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models import Student
from backend.schemas.students import StudentCreate, StudentRead, StudentUpdate
from backend.security import AuthSession, get_auth_session, get_family_record

router = APIRouter(prefix='/students', tags=['students'])


@router.get('', response_model=list[StudentRead])
async def list_students(
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(get_auth_session),
) -> list[Student]:
    result = await db.execute(select(Student).where(Student.family_id == auth.family_id).order_by(Student.name))
    return list(result.scalars().all())


@router.post('', response_model=StudentRead, status_code=status.HTTP_201_CREATED)
async def create_student(
    payload: StudentCreate,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(get_auth_session),
) -> Student:
    existing = await db.execute(
        select(Student).where(Student.family_id == auth.family_id, Student.name == payload.name.strip())
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='Student already exists')

    student = Student(family_id=auth.family_id, name=payload.name.strip())
    db.add(student)
    await db.commit()
    await db.refresh(student)
    return student


@router.get('/{student_id}', response_model=StudentRead)
async def get_student(
    student_id: int,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(get_auth_session),
) -> Student:
    student = await get_family_record(db, Student, student_id, auth.family_id)
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Student not found')
    return student


@router.put('/{student_id}', response_model=StudentRead)
async def update_student(
    student_id: int,
    payload: StudentUpdate,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(get_auth_session),
) -> Student:
    student = await get_family_record(db, Student, student_id, auth.family_id)
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Student not found')

    existing = await db.execute(
        select(Student).where(
            Student.family_id == auth.family_id,
            Student.name == payload.name.strip(),
            Student.id != student_id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='Student already exists')

    student.name = payload.name.strip()
    await db.commit()
    await db.refresh(student)
    return student


@router.delete('/{student_id}', status_code=status.HTTP_204_NO_CONTENT)
async def delete_student(
    student_id: int,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(get_auth_session),
) -> None:
    student = await get_family_record(db, Student, student_id, auth.family_id)
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Student not found')
    await db.delete(student)
    await db.commit()
