from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models import Student
from backend.models.calendar import SchoolYear
from backend.models.schedule import Schedule
from backend.schemas.students import StudentCreate, StudentRead, StudentUpdate
from backend.security import AuthSession, get_family_record
from backend.services.authorization import (
    AppRole,
    Capability,
    ensure_student_scope,
    get_student_scope_id,
    require_any_role,
    require_capabilities,
)

router = APIRouter(prefix='/students', tags=['students'])


@router.get('', response_model=list[StudentRead])
async def list_students(
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_any_role(AppRole.teacher, AppRole.student, action='view students')),
) -> list[Student]:
    stmt = select(Student).where(Student.family_id == auth.family_id).order_by(Student.name)
    if auth.role == 'student_viewer':
        stmt = stmt.where(Student.id == get_student_scope_id(auth))
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.post('', response_model=StudentRead, status_code=status.HTTP_201_CREATED)
async def create_student(
    payload: StudentCreate,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.manage_family, action='manage students')),
) -> Student:
    existing = await db.execute(
        select(Student).where(Student.family_id == auth.family_id, Student.name == payload.name.strip())
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='Student already exists')

    student = Student(family_id=auth.family_id, name=payload.name.strip())
    db.add(student)
    await db.flush()

    # Auto-create a default schedule for the active school year
    active_year = (
        await db.execute(
            select(SchoolYear).where(
                SchoolYear.family_id == auth.family_id,
                SchoolYear.is_active.is_(True),
            )
        )
    ).scalar_one_or_none()
    if active_year:
        db.add(Schedule(
            family_id=auth.family_id,
            student_id=student.id,
            school_year_id=active_year.id,
            name='Default',
        ))

    await db.commit()
    await db.refresh(student)
    return student


@router.get('/{student_id}', response_model=StudentRead)
async def get_student(
    student_id: int,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_any_role(AppRole.teacher, AppRole.student, action='view students')),
) -> Student:
    student = await get_family_record(db, Student, student_id, auth.family_id)
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Student not found')
    ensure_student_scope(auth, student.id, action='view student records')
    return student


@router.put('/{student_id}', response_model=StudentRead)
async def update_student(
    student_id: int,
    payload: StudentUpdate,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.manage_family, action='manage students')),
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


@router.delete('/{student_id}', status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_student(
    student_id: int,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.manage_family, action='manage students')),
) -> None:
    student = await get_family_record(db, Student, student_id, auth.family_id)
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Student not found')
    await db.delete(student)
    await db.commit()
