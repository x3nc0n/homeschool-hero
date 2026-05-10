from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models import FamilySettings
from backend.schemas.family_settings import FamilyFeatureSettingsRead, FamilyFeatureSettingsUpdate
from backend.security import AuthSession
from backend.services.authorization import Capability, require_capabilities

router = APIRouter(prefix='/family-settings', tags=['family-settings'])


@router.put('/features', response_model=FamilyFeatureSettingsRead)
async def update_family_features(
    payload: FamilyFeatureSettingsUpdate,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.manage_family, action='update family feature settings')),
) -> FamilyFeatureSettingsRead:
    family_settings = await db.get(FamilySettings, auth.family_id)
    if family_settings is None:
        family_settings = FamilySettings(family_id=auth.family_id, timezone='UTC', grading_scale='letter')
        db.add(family_settings)
    family_settings.enabled_features = payload.enabled_features or {}
    await db.commit()
    return FamilyFeatureSettingsRead(enabled_features=family_settings.enabled_features or {})
