from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import Float, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models import Assignment, Grade, Student, Subject, Submission
from backend.schemas.grades import (
    GradeAverageByStudent,
    GradeAverageBySubject,
    GradeCreate,
    GradeHistoryItem,
    GradeRead,
    GradeUpdate,
)
from backend.security import AuthSession, get_auth_session, get_family_record

router = APIRouter(prefix='/grades', tags=['grades'])


@router.get('', response_model=list[GradeRead])
async def list_grades(
    student_id: int | None = Query(default=None),
    subject_id: int | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(get_auth_session),
) -> list[Grade]:
    stmt = (
        select(Grade)
        .join(Submission, Submission.id == Grade.submission_id)
        .join(Assignment, Assignment.id == Submission.assignment_id)
        .where(Grade.family_id == auth.family_id)
    )
    if student_id:
        stmt = stmt.where(Grade.student_id == student_id)
    if subject_id:
        stmt = stmt.where(Assignment.subject_id == subject_id)
    stmt = stmt.order_by(Grade.created_at.desc())
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.post('', response_model=GradeRead, status_code=status.HTTP_201_CREATED)
async def create_grade(
    payload: GradeCreate,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(get_auth_session),
) -> Grade:
    submission = await get_family_record(db, Submission, payload.submission_id, auth.family_id)
    if not submission:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Submission not found')
    student = await get_family_record(db, Student, payload.student_id, auth.family_id)
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Student not found')

    existing = await db.execute(
        select(Grade).where(Grade.family_id == auth.family_id, Grade.submission_id == payload.submission_id)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='Grade already exists for submission')

    grade = Grade(family_id=auth.family_id, **payload.model_dump())
    db.add(grade)
    await db.commit()
    await db.refresh(grade)
    return grade


@router.get('/averages/student/{student_id}', response_model=list[GradeAverageByStudent])
async def averages_by_student(
    student_id: int,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(get_auth_session),
) -> list[GradeAverageByStudent]:
    student = await get_family_record(db, Student, student_id, auth.family_id)
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Student not found')
    stmt = (
        select(
            Grade.student_id,
            Student.name,
            Subject.id,
            Subject.name,
            func.avg(cast(Grade.score / Grade.max_score * 100.0, Float)),
        )
        .join(Student, Student.id == Grade.student_id)
        .join(Submission, Submission.id == Grade.submission_id)
        .join(Assignment, Assignment.id == Submission.assignment_id)
        .join(Subject, Subject.id == Assignment.subject_id)
        .where(Grade.family_id == auth.family_id, Grade.student_id == student_id)
        .group_by(Grade.student_id, Student.name, Subject.id, Subject.name)
        .order_by(Subject.name)
    )
    rows = (await db.execute(stmt)).all()
    return [
        GradeAverageByStudent(
            student_id=row[0],
            student_name=row[1],
            subject_id=row[2],
            subject_name=row[3],
            average_percent=round(float(row[4]), 2),
        )
        for row in rows
    ]


@router.get('/averages/subject/{subject_id}', response_model=list[GradeAverageBySubject])
async def averages_by_subject(
    subject_id: int,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(get_auth_session),
) -> list[GradeAverageBySubject]:
    subject = await get_family_record(db, Subject, subject_id, auth.family_id)
    if not subject:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Subject not found')
    stmt = (
        select(
            Subject.id,
            Subject.name,
            Grade.student_id,
            Student.name,
            func.avg(cast(Grade.score / Grade.max_score * 100.0, Float)),
        )
        .join(Submission, Submission.id == Grade.submission_id)
        .join(Assignment, Assignment.id == Submission.assignment_id)
        .join(Subject, Subject.id == Assignment.subject_id)
        .join(Student, Student.id == Grade.student_id)
        .where(Grade.family_id == auth.family_id, Subject.id == subject_id)
        .group_by(Subject.id, Subject.name, Grade.student_id, Student.name)
        .order_by(Student.name)
    )
    rows = (await db.execute(stmt)).all()
    return [
        GradeAverageBySubject(
            subject_id=row[0],
            subject_name=row[1],
            student_id=row[2],
            student_name=row[3],
            average_percent=round(float(row[4]), 2),
        )
        for row in rows
    ]


@router.get('/history', response_model=list[GradeHistoryItem])
async def grade_history(
    student_id: int | None = Query(default=None),
    subject_id: int | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(get_auth_session),
) -> list[GradeHistoryItem]:
    stmt = (
        select(
            Grade.id,
            Grade.student_id,
            Student.name,
            Subject.id,
            Subject.name,
            Assignment.id,
            Assignment.title,
            Grade.score,
            Grade.max_score,
            Grade.letter_grade,
            Grade.graded_by,
            Grade.created_at,
        )
        .join(Student, Student.id == Grade.student_id)
        .join(Submission, Submission.id == Grade.submission_id)
        .join(Assignment, Assignment.id == Submission.assignment_id)
        .join(Subject, Subject.id == Assignment.subject_id)
        .where(Grade.family_id == auth.family_id)
    )
    if student_id:
        stmt = stmt.where(Grade.student_id == student_id)
    if subject_id:
        stmt = stmt.where(Subject.id == subject_id)
    stmt = stmt.order_by(Grade.created_at.desc())
    rows = (await db.execute(stmt)).all()
    return [
        GradeHistoryItem(
            grade_id=row[0],
            student_id=row[1],
            student_name=row[2],
            subject_id=row[3],
            subject_name=row[4],
            assignment_id=row[5],
            assignment_title=row[6],
            score=float(row[7]),
            max_score=float(row[8]),
            percent=round((float(row[7]) / float(row[8])) * 100, 2),
            letter_grade=row[9],
            graded_by=row[10],
            created_at=row[11],
        )
        for row in rows
    ]


@router.get('/gradebook')
async def gradebook(
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(get_auth_session),
):
    rows = await grade_history(student_id=None, subject_id=None, db=db, auth=auth)
    return {'items': rows}


@router.get('/{grade_id}', response_model=GradeRead)
async def get_grade(
    grade_id: int,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(get_auth_session),
) -> Grade:
    grade = await get_family_record(db, Grade, grade_id, auth.family_id)
    if not grade:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Grade not found')
    return grade


@router.put('/{grade_id}', response_model=GradeRead)
async def update_grade(
    grade_id: int,
    payload: GradeUpdate,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(get_auth_session),
) -> Grade:
    grade = await get_family_record(db, Grade, grade_id, auth.family_id)
    if not grade:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Grade not found')
    for key, value in payload.model_dump().items():
        setattr(grade, key, value)
    await db.commit()
    await db.refresh(grade)
    return grade


@router.delete('/{grade_id}', status_code=status.HTTP_204_NO_CONTENT)
async def delete_grade(
    grade_id: int,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(get_auth_session),
) -> None:
    grade = await get_family_record(db, Grade, grade_id, auth.family_id)
    if not grade:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Grade not found')
    await db.delete(grade)
    await db.commit()
