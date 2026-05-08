from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models import Student
from backend.schemas.students import StudentCreate, StudentRead, StudentUpdate

router = APIRouter(prefix="/students", tags=["students"])


@router.get("", response_model=list[StudentRead])
async def list_students(db: AsyncSession = Depends(get_db)) -> list[Student]:
    result = await db.execute(select(Student).order_by(Student.name))
    return list(result.scalars().all())


@router.post("", response_model=StudentRead, status_code=status.HTTP_201_CREATED)
async def create_student(payload: StudentCreate, db: AsyncSession = Depends(get_db)) -> Student:
    existing = await db.execute(select(Student).where(Student.name == payload.name))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Student already exists")

    student = Student(name=payload.name)
    db.add(student)
    await db.commit()
    await db.refresh(student)
    return student


@router.get("/{student_id}", response_model=StudentRead)
async def get_student(student_id: int, db: AsyncSession = Depends(get_db)) -> Student:
    student = await db.get(Student, student_id)
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")
    return student


@router.put("/{student_id}", response_model=StudentRead)
async def update_student(student_id: int, payload: StudentUpdate, db: AsyncSession = Depends(get_db)) -> Student:
    student = await db.get(Student, student_id)
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")
    student.name = payload.name
    await db.commit()
    await db.refresh(student)
    return student


@router.delete("/{student_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_student(student_id: int, db: AsyncSession = Depends(get_db)) -> None:
    student = await db.get(Student, student_id)
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")
    await db.delete(student)
    await db.commit()
