from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.schemas.health import DetailedHealthRead, ReadinessRead, SimpleHealthRead, SystemStatusRead
from backend.security import AuthSession, get_auth_session
from backend.services.health import (
    build_health_payload,
    build_readiness_payload,
    build_simple_health_payload,
    build_status_payload,
)

router = APIRouter(tags=['health'])


@router.get('/health', response_model=SimpleHealthRead)
async def health(request: Request) -> JSONResponse:
    status_code, payload = await build_simple_health_payload(request.app)
    return JSONResponse(status_code=status_code, content=payload)


@router.get('/health/detailed', response_model=DetailedHealthRead)
async def detailed_health(
    request: Request,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(get_auth_session),
) -> DetailedHealthRead:
    return DetailedHealthRead.model_validate(await build_health_payload(request.app, auth=auth, db=db))


@router.get('/health/ready', response_model=ReadinessRead)
async def readiness(request: Request) -> JSONResponse:
    status_code, payload = await build_readiness_payload(request.app)
    return JSONResponse(status_code=status_code, content=payload)


@router.get('/status', response_model=SystemStatusRead)
async def status_center(
    request: Request,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(get_auth_session),
) -> SystemStatusRead:
    return SystemStatusRead.model_validate(await build_status_payload(request.app, auth=auth, db=db))
