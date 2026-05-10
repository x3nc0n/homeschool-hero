from __future__ import annotations

from pydantic import BaseModel, Field


class FamilyFeatureSettingsUpdate(BaseModel):
    enabled_features: dict[str, bool] = Field(default_factory=dict)


class FamilyFeatureSettingsRead(BaseModel):
    enabled_features: dict[str, bool] = Field(default_factory=dict)
