from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.validation import HEX_COLOR_RE, normalize_text


class SubjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    color: str = Field(default="#4f46e5", max_length=7)

    @field_validator('name')
    @classmethod
    def validate_name(cls, value: str) -> str:
        return normalize_text(value, field_name='Subject name')

    @field_validator('color')
    @classmethod
    def validate_color(cls, value: str) -> str:
        color = value.strip()
        if not HEX_COLOR_RE.match(color):
            raise ValueError('Color must be a valid hex color')
        return color.lower()


class SubjectUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    color: str = Field(default="#4f46e5", max_length=7)

    @field_validator('name')
    @classmethod
    def validate_name(cls, value: str) -> str:
        return normalize_text(value, field_name='Subject name')

    @field_validator('color')
    @classmethod
    def validate_color(cls, value: str) -> str:
        color = value.strip()
        if not HEX_COLOR_RE.match(color):
            raise ValueError('Color must be a valid hex color')
        return color.lower()


class SubjectRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    color: str
    created_at: datetime
    updated_at: datetime
