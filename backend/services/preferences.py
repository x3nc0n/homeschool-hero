from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import UserPreference
from backend.schemas.preferences import UserPreferencesRead, UserPreferencesUpdate

DEFAULT_USER_PREFERENCES = UserPreferencesRead()


def serialize_user_preferences(preferences: UserPreference | None) -> dict[str, str]:
    if preferences is None:
        return DEFAULT_USER_PREFERENCES.model_dump()
    return UserPreferencesRead(
        theme=preferences.theme,
        accent_color=preferences.accent_color,
        font_size=preferences.font_size,
        density=preferences.density,
        sidebar_position=preferences.sidebar_position,
    ).model_dump()


async def get_or_create_user_preferences(db: AsyncSession, user_id: int) -> UserPreference:
    preferences = (
        await db.execute(select(UserPreference).where(UserPreference.user_id == user_id))
    ).scalar_one_or_none()
    if preferences is not None:
        return preferences

    defaults = DEFAULT_USER_PREFERENCES.model_dump()
    preferences = UserPreference(user_id=user_id, **defaults)
    db.add(preferences)
    await db.flush()
    return preferences


async def read_user_preferences(db: AsyncSession, user_id: int) -> UserPreferencesRead:
    preferences = await get_or_create_user_preferences(db, user_id)
    await db.commit()
    return UserPreferencesRead.model_validate(serialize_user_preferences(preferences))


async def update_user_preferences(db: AsyncSession, user_id: int, payload: UserPreferencesUpdate) -> UserPreferencesRead:
    preferences = await get_or_create_user_preferences(db, user_id)
    values = payload.model_dump()
    preferences.theme = values['theme']
    preferences.accent_color = values['accent_color']
    preferences.font_size = values['font_size']
    preferences.density = values['density']
    preferences.sidebar_position = values['sidebar_position']
    await db.commit()
    await db.refresh(preferences)
    return UserPreferencesRead.model_validate(serialize_user_preferences(preferences))
