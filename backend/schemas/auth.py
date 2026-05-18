from pydantic import BaseModel, Field, field_validator

from backend.schemas.preferences import UserPreferencesRead
from backend.validation import normalize_email_address, normalize_text, validate_password_policy


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=1, max_length=255)
    family_id: int | None = Field(default=None, gt=0)

    @field_validator('email')
    @classmethod
    def validate_email(cls, value: str) -> str:
        return normalize_email_address(value)

    @field_validator('password')
    @classmethod
    def validate_password(cls, value: str) -> str:
        return value.strip()


class RegisterRequest(BaseModel):
    family_name: str = Field(min_length=1, max_length=160)
    email: str = Field(min_length=3, max_length=255)
    display_name: str = Field(min_length=1, max_length=160)
    password: str = Field(min_length=12, max_length=255)
    timezone: str = Field(default='UTC', min_length=1, max_length=64)
    grading_scale: str = Field(default='letter', min_length=1, max_length=64)

    @field_validator('email')
    @classmethod
    def validate_email(cls, value: str) -> str:
        return normalize_email_address(value)

    @field_validator('family_name', 'display_name', 'timezone', 'grading_scale')
    @classmethod
    def validate_text_fields(cls, value: str, info) -> str:
        return normalize_text(value, field_name=info.field_name.replace('_', ' ').title())

    @field_validator('password')
    @classmethod
    def validate_password(cls, value: str) -> str:
        return validate_password_policy(value)


class SessionUser(BaseModel):
    id: int
    email: str
    display_name: str
    is_active: bool = True
    auth_provider: str = 'local'


class SessionFamily(BaseModel):
    id: int
    name: str
    state_code: str = 'CUSTOM'
    enabled_features: dict[str, bool] = Field(default_factory=dict)


class SessionMembership(BaseModel):
    role: str
    is_owner: bool
    student_id: int | None = None


class AuthSessionResponse(BaseModel):
    authenticated: bool
    user: SessionUser
    family: SessionFamily
    membership: SessionMembership
    app_roles: list[str] = Field(default_factory=list)
    effective_capabilities: list[str] = Field(default_factory=list)
    ui_preferences: UserPreferencesRead
    message: str | None = None


class BootstrapStatusResponse(BaseModel):
    bootstrap_required: bool


class OIDCVerifyResponse(BaseModel):
    configured: bool
    reachable: bool
    message: str
    discovery_url: str | None = None
    issuer: str | None = None
    authorization_endpoint: str | None = None


LoginResponse = AuthSessionResponse
RegisterResponse = AuthSessionResponse
SessionResponse = AuthSessionResponse
