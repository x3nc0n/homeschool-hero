from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator


ThemePreference = Literal['light', 'dark', 'high-contrast', 'system']
FontSizePreference = Literal['small', 'medium', 'large']
DensityPreference = Literal['compact', 'comfortable']
SidebarPositionPreference = Literal['left', 'right', 'collapsed']


class UserPreferencesBase(BaseModel):
    theme: ThemePreference = 'system'
    accent_color: str = Field(default='#2563eb', min_length=4, max_length=16)
    font_size: FontSizePreference = 'medium'
    density: DensityPreference = 'comfortable'
    sidebar_position: SidebarPositionPreference = 'left'

    @field_validator('accent_color')
    @classmethod
    def validate_accent_color(cls, value: str) -> str:
        normalized = value.strip().lower()
        if len(normalized) == 4 and normalized.startswith('#'):
            expanded = '#' + ''.join(character * 2 for character in normalized[1:])
            return expanded
        if len(normalized) != 7 or not normalized.startswith('#'):
            raise ValueError('Accent color must be a hex value like #2563eb.')
        hex_part = normalized[1:]
        if any(character not in '0123456789abcdef' for character in hex_part):
            raise ValueError('Accent color must be a hex value like #2563eb.')
        return normalized


class UserPreferencesRead(UserPreferencesBase):
    pass


class UserPreferencesUpdate(UserPreferencesBase):
    pass
