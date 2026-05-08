from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class SubjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    color: str = Field(default="#4f46e5", max_length=32)


class SubjectUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    color: str = Field(default="#4f46e5", max_length=32)


class SubjectRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    color: str
    created_at: datetime
    updated_at: datetime
