from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.validation import normalize_text


class StudentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)

    @field_validator('name')
    @classmethod
    def normalize_name(cls, value: str) -> str:
        return normalize_text(value, field_name='Student name')


class StudentUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=120)

    @field_validator('name')
    @classmethod
    def normalize_name(cls, value: str) -> str:
        return normalize_text(value, field_name='Student name')


class StudentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    created_at: datetime
    updated_at: datetime
