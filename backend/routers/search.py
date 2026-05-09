from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.schemas.search import SearchEntityType, SearchResponse
from backend.security import AuthSession
from backend.services.authorization import Capability, require_capabilities
from backend.services.search import search_entities

router = APIRouter(prefix='/search', tags=['search'])


@router.get('', response_model=SearchResponse)
async def global_search(
    q: str | None = Query(default=None, min_length=1, max_length=200),
    entity_type: SearchEntityType | None = Query(default=None, alias='type'),
    student_id: int | None = Query(default=None, gt=0),
    subject_id: int | None = Query(default=None, gt=0),
    term_id: int | None = Query(default=None, gt=0),
    grading_period_id: int | None = Query(default=None, gt=0),
    status: str | None = Query(default=None, min_length=1, max_length=64),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    score_min: float | None = Query(default=None, ge=0),
    score_max: float | None = Query(default=None, ge=0),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(
        require_capabilities(
            Capability.read_students,
            Capability.read_curriculum,
            Capability.read_grades,
            action='use global search',
        )
    ),
) -> SearchResponse:
    return await search_entities(
        db,
        auth,
        q=q,
        entity_type=entity_type,
        student_id=student_id,
        subject_id=subject_id,
        term_id=term_id,
        grading_period_id=grading_period_id,
        status=status,
        date_from=date_from,
        date_to=date_to,
        score_min=score_min,
        score_max=score_max,
        page=page,
        page_size=page_size,
    )
