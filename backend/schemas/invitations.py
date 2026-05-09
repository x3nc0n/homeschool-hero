from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from backend.models import FamilyRole
from backend.validation import normalize_email_address, normalize_text, validate_password_policy


class InvitationCreate(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    role: FamilyRole
    student_id: int | None = Field(default=None, gt=0)
    expires_in_days: int = Field(default=7, ge=1, le=30)

    @field_validator('email')
    @classmethod
    def validate_email(cls, value: str) -> str:
        return normalize_email_address(value)

    @model_validator(mode='after')
    def validate_student_binding(self) -> 'InvitationCreate':
        if self.role == FamilyRole.student_viewer and self.student_id is None:
            raise ValueError('student_id is required for student viewer invitations')
        if self.role != FamilyRole.student_viewer:
            self.student_id = None
        return self


class InvitationRead(BaseModel):
    id: int
    email: str
    role: FamilyRole
    student_id: int | None = None
    student_name: str | None = None
    expires_at: datetime
    accepted_at: datetime | None = None
    invite_link: str | None = None
    invite_code: str | None = None
    delivery_method: Literal['email', 'link']
    email_sent: bool = False
    is_expired: bool = False
    created_at: datetime


class InvitationAccept(BaseModel):
    token: str = Field(min_length=16, max_length=255)
    email: str = Field(min_length=3, max_length=255)
    display_name: str = Field(min_length=1, max_length=160)
    password: str = Field(min_length=12, max_length=255)

    @field_validator('email')
    @classmethod
    def validate_email(cls, value: str) -> str:
        return normalize_email_address(value)

    @field_validator('display_name')
    @classmethod
    def validate_display_name(cls, value: str) -> str:
        return normalize_text(value, field_name='Display name')

    @field_validator('password')
    @classmethod
    def validate_password(cls, value: str) -> str:
        return validate_password_policy(value)
