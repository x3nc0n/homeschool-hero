from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models import Quiz, QuizAttempt, Student, Subject
from backend.schemas.quizzes import QuizAttemptCreate, QuizAttemptRead, QuizCreate, QuizRead, QuizUpdate
from backend.security import AuthSession, get_family_record
from backend.services.authorization import Capability, ensure_student_scope, get_student_scope_id, require_capabilities
from backend.services.cache import invalidate_compliance_cache

router = APIRouter(prefix='/quizzes', tags=['quizzes'])


def _normalize_answer(value: Any) -> Any:
    if isinstance(value, str):
        return value.strip().lower()
    return value


@router.get('', response_model=list[QuizRead])
async def list_quizzes(
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.read_curriculum, action='view quizzes')),
) -> list[Quiz]:
    quizzes = (
        await db.execute(select(Quiz).where(Quiz.family_id == auth.family_id).order_by(Quiz.created_at.desc()))
    ).scalars().all()
    return list(quizzes)


@router.post('', response_model=QuizRead, status_code=status.HTTP_201_CREATED)
async def create_quiz(
    payload: QuizCreate,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.manage_curriculum, action='manage quizzes')),
) -> Quiz:
    subject = await get_family_record(db, Subject, payload.subject_id, auth.family_id)
    if not subject:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Subject not found')
    quiz = Quiz(
        family_id=auth.family_id,
        title=payload.title,
        subject_id=payload.subject_id,
        questions=[q.model_dump() for q in payload.questions],
    )
    db.add(quiz)
    await db.commit()
    await db.refresh(quiz)
    return quiz


@router.get('/{quiz_id}', response_model=QuizRead)
async def get_quiz(
    quiz_id: int,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.read_curriculum, action='view quizzes')),
) -> Quiz:
    quiz = await get_family_record(db, Quiz, quiz_id, auth.family_id)
    if not quiz:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Quiz not found')
    return quiz


@router.put('/{quiz_id}', response_model=QuizRead)
async def update_quiz(
    quiz_id: int,
    payload: QuizUpdate,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.manage_curriculum, action='manage quizzes')),
) -> Quiz:
    quiz = await get_family_record(db, Quiz, quiz_id, auth.family_id)
    if not quiz:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Quiz not found')
    subject = await get_family_record(db, Subject, payload.subject_id, auth.family_id)
    if not subject:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Subject not found')
    quiz.title = payload.title
    quiz.subject_id = payload.subject_id
    quiz.questions = [q.model_dump() for q in payload.questions]
    await db.commit()
    await db.refresh(quiz)
    return quiz


@router.delete('/{quiz_id}', status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_quiz(
    quiz_id: int,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.manage_curriculum, action='manage quizzes')),
) -> None:
    quiz = await get_family_record(db, Quiz, quiz_id, auth.family_id)
    if not quiz:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Quiz not found')
    await db.delete(quiz)
    await db.commit()


@router.post('/{quiz_id}/attempts', response_model=QuizAttemptRead, status_code=status.HTTP_201_CREATED)
async def take_quiz(
    quiz_id: int,
    payload: QuizAttemptCreate,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.manage_curriculum, action='submit quiz attempts')),
) -> QuizAttempt:
    quiz = await get_family_record(db, Quiz, quiz_id, auth.family_id)
    if not quiz:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Quiz not found')
    student = await get_family_record(db, Student, payload.student_id, auth.family_id)
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Student not found')

    questions = quiz.questions or []
    answers = payload.answers
    max_score = 0.0
    score = 0.0

    for idx, question in enumerate(questions):
        points = float(question.get('points', 1.0))
        max_score += points
        expected = _normalize_answer(question.get('correct_answer'))
        actual = _normalize_answer(answers[idx] if idx < len(answers) else None)
        if actual == expected:
            score += points

    attempt = QuizAttempt(
        family_id=auth.family_id,
        quiz_id=quiz.id,
        student_id=payload.student_id,
        answers=answers,
        score=score,
        max_score=max_score,
    )
    db.add(attempt)
    await db.commit()
    invalidate_compliance_cache(family_id=auth.family_id, student_id=payload.student_id)
    await db.refresh(attempt)
    return attempt


@router.get('/{quiz_id}/attempts', response_model=list[QuizAttemptRead])
async def list_attempts(
    quiz_id: int,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.read_curriculum, action='view quiz attempts')),
) -> list[QuizAttempt]:
    quiz = await get_family_record(db, Quiz, quiz_id, auth.family_id)
    if not quiz:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Quiz not found')
    stmt = select(QuizAttempt).where(QuizAttempt.family_id == auth.family_id, QuizAttempt.quiz_id == quiz_id)
    if auth.role == 'student_viewer':
        stmt = stmt.where(QuizAttempt.student_id == get_student_scope_id(auth))
    attempts = (await db.execute(stmt)).scalars().all()
    return list(attempts)
