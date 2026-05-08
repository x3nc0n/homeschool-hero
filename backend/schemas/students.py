from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class StudentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class StudentUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class StudentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    created_at: datetime
    updated_at: datetime
