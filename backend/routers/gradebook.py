from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models import GradeScale, Student, Subject
from backend.schemas.gradebook import (
    GradeCategoryRead,
    GradeScaleRead,
    GradebookCalculationRequest,
    GradebookCategoriesUpsert,
    GradebookScalesUpsert,
    GradebookSummary,
    GradebookTrends,
    GradebookView,
)
from backend.security import AuthSession, get_family_record
from backend.services.authorization import Capability, ensure_student_scope, get_student_scope_id, require_capabilities
from backend.services.gradebook import (
    build_gradebook_summary,
    build_gradebook_trends,
    calculate_gradebook,
    list_grade_scales,
    list_or_build_grade_categories,
    save_grade_categories,
    save_grade_scales,
)
from backend.services.cache import cache_headers, get_cache, invalidate_gradebook_cache, is_not_modified

router = APIRouter(prefix='/gradebook', tags=['gradebook'])
GRADEBOOK_TTL = timedelta(seconds=30)
GRADEBOOK_MAX_AGE = 30


def _resolve_student_scope(auth: AuthSession, requested_student_id: int) -> int:
    if auth.role != 'student_viewer':
        return requested_student_id
    student_id = get_student_scope_id(auth)
    if student_id != requested_student_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Role '{auth.role}' is not allowed to view another student's gradebook.",
        )
    return student_id


@router.get('/categories', response_model=list[GradeCategoryRead])
async def get_grade_categories(
    subject_id: int = Query(gt=0),
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.read_grades, action='view grade categories')),
) -> list[dict[str, object]]:
    subject = await get_family_record(db, Subject, subject_id, auth.family_id)
    if not subject:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Subject not found')
    return await list_or_build_grade_categories(db, auth.family_id, subject_id)


@router.put('/categories', response_model=list[GradeCategoryRead])
async def upsert_grade_categories(
    payload: GradebookCategoriesUpsert,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.manage_curriculum, Capability.manage_grading, action='manage grade categories')),
) -> list[GradeCategoryRead]:
    subject = await get_family_record(db, Subject, payload.subject_id, auth.family_id)
    if not subject:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Subject not found')
    try:
        categories = await save_grade_categories(
            db,
            family_id=auth.family_id,
            subject_id=payload.subject_id,
            categories=[category.model_dump() for category in payload.categories],
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    await db.commit()
    invalidate_gradebook_cache(family_id=auth.family_id)
    return [GradeCategoryRead(**{'id': category.id, 'name': category.name, 'weight': category.weight, 'drop_lowest': category.drop_lowest or 0}) for category in categories]


@router.get('/scales', response_model=list[GradeScaleRead])
async def get_grade_scales(
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.read_grades, action='view grade scales')),
) -> list[GradeScale]:
    return await list_grade_scales(db, auth.family_id)


@router.put('/scales', response_model=list[GradeScaleRead])
async def upsert_grade_scales(
    payload: GradebookScalesUpsert,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.manage_family, action='manage grade scales')),
) -> list[GradeScale]:
    try:
        scales = await save_grade_scales(db, auth.family_id, [scale.model_dump() for scale in payload.scales])
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    await db.commit()
    invalidate_gradebook_cache(family_id=auth.family_id)
    return scales


@router.get('/{student_id}', response_model=GradebookView)
async def get_gradebook(
    student_id: int,
    request: Request,
    response: Response,
    subject_id: int | None = Query(default=None, gt=0),
    grading_period_id: int | None = Query(default=None, gt=0),
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.read_grades, action='view gradebook')),
) -> dict[str, object]:
    student = await get_family_record(db, Student, _resolve_student_scope(auth, student_id), auth.family_id)
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Student not found')
    ensure_student_scope(auth, student.id, action='view gradebook')
    try:
        cache_key = f'gradebook:{auth.family_id}:{student.id}:detail:{subject_id or "all"}:{grading_period_id or "all"}'
        entry = await get_cache().get_or_set(
            cache_key,
            ttl=GRADEBOOK_TTL,
            factory=lambda: calculate_gradebook(
                db,
                family_id=auth.family_id,
                student_id=student.id,
                subject_id=subject_id,
                grading_period_id=grading_period_id,
            ),
        )
        headers = cache_headers(entry, max_age_seconds=GRADEBOOK_MAX_AGE)
        if request is not None and is_not_modified(request, entry):
            return Response(status_code=status.HTTP_304_NOT_MODIFIED, headers=headers)
        if response is not None:
            response.headers.update(headers)
        return entry.value
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get('/{student_id}/summary', response_model=GradebookSummary)
async def get_gradebook_summary(
    student_id: int,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.read_grades, action='view grade summaries')),
) -> dict[str, object]:
    student = await get_family_record(db, Student, _resolve_student_scope(auth, student_id), auth.family_id)
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Student not found')
    cache_key = f'gradebook:{auth.family_id}:{student.id}:detail:all:all'
    entry = await get_cache().get_or_set(
        cache_key,
        ttl=GRADEBOOK_TTL,
        factory=lambda: calculate_gradebook(db, family_id=auth.family_id, student_id=student.id),
    )
    headers = cache_headers(entry, max_age_seconds=GRADEBOOK_MAX_AGE)
    if request is not None and is_not_modified(request, entry):
        return Response(status_code=status.HTTP_304_NOT_MODIFIED, headers=headers)
    if response is not None:
        response.headers.update(headers)
    return build_gradebook_summary(entry.value)


@router.get('/{student_id}/trends', response_model=GradebookTrends)
async def get_grade_trends(
    student_id: int,
    request: Request,
    response: Response,
    subject_id: int | None = Query(default=None, gt=0),
    grading_period_id: int | None = Query(default=None, gt=0),
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.read_grades, action='view grade trends')),
) -> dict[str, object]:
    student = await get_family_record(db, Student, _resolve_student_scope(auth, student_id), auth.family_id)
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Student not found')
    cache_key = f'gradebook:{auth.family_id}:{student.id}:detail:{subject_id or "all"}:{grading_period_id or "all"}'
    entry = await get_cache().get_or_set(
        cache_key,
        ttl=GRADEBOOK_TTL,
        factory=lambda: calculate_gradebook(
            db,
            family_id=auth.family_id,
            student_id=student.id,
            subject_id=subject_id,
            grading_period_id=grading_period_id,
        ),
    )
    headers = cache_headers(entry, max_age_seconds=GRADEBOOK_MAX_AGE)
    if request is not None and is_not_modified(request, entry):
        return Response(status_code=status.HTTP_304_NOT_MODIFIED, headers=headers)
    if response is not None:
        response.headers.update(headers)
    return build_gradebook_trends(entry.value)


@router.post('/calculate', response_model=GradebookView)
async def recalculate_gradebook(
    payload: GradebookCalculationRequest,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.manage_grading, action='recalculate grades')),
) -> dict[str, object]:
    student = await get_family_record(db, Student, _resolve_student_scope(auth, payload.student_id), auth.family_id)
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Student not found')
    invalidate_gradebook_cache(family_id=auth.family_id, student_id=student.id)
    return await calculate_gradebook(
        db,
        family_id=auth.family_id,
        student_id=student.id,
        subject_id=payload.subject_id,
        grading_period_id=payload.grading_period_id,
    )
