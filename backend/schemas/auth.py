from pydantic import BaseModel, Field, field_validator


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=8, max_length=255)
    family_id: int | None = None

    @field_validator('email')
    @classmethod
    def validate_email(cls, value: str) -> str:
        email = value.strip().lower()
        if '@' not in email:
            raise ValueError('Enter a valid email address')
        return email


class RegisterRequest(BaseModel):
    family_name: str = Field(min_length=1, max_length=160)
    email: str = Field(min_length=3, max_length=255)
    display_name: str = Field(min_length=1, max_length=160)
    password: str = Field(min_length=8, max_length=255)
    timezone: str = Field(default='UTC', min_length=1, max_length=64)
    grading_scale: str = Field(default='letter', min_length=1, max_length=64)

    @field_validator('email')
    @classmethod
    def validate_email(cls, value: str) -> str:
        email = value.strip().lower()
        if '@' not in email:
            raise ValueError('Enter a valid email address')
        return email


class SessionUser(BaseModel):
    id: int
    email: str
    display_name: str
    is_active: bool = True


class SessionFamily(BaseModel):
    id: int
    name: str


class SessionMembership(BaseModel):
    role: str
    is_owner: bool
    student_id: int | None = None


class AuthSessionResponse(BaseModel):
    authenticated: bool
    user: SessionUser
    family: SessionFamily
    membership: SessionMembership
    message: str | None = None


class BootstrapStatusResponse(BaseModel):
    bootstrap_required: bool


LoginResponse = AuthSessionResponse
RegisterResponse = AuthSessionResponse
SessionResponse = AuthSessionResponse
