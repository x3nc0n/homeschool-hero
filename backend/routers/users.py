from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.schemas.preferences import UserPreferencesRead, UserPreferencesUpdate
from backend.security import AuthSession, get_auth_session
from backend.services.preferences import read_user_preferences, update_user_preferences

router = APIRouter(prefix='/users', tags=['users'])


@router.get('/preferences', response_model=UserPreferencesRead)
async def get_preferences(
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(get_auth_session),
) -> UserPreferencesRead:
    return await read_user_preferences(db, auth.user_id)


@router.put('/preferences', response_model=UserPreferencesRead)
async def put_preferences(
    payload: UserPreferencesUpdate,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(get_auth_session),
) -> UserPreferencesRead:
    return await update_user_preferences(db, auth.user_id, payload)
