from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    credential: str | None = Field(default=None, min_length=1)
    method: str | None = Field(default=None, pattern="^(password|pin)$")
    password: str | None = Field(default=None, min_length=1)
    pin: str | None = Field(default=None, min_length=1)


class SessionUser(BaseModel):
    name: str = "Parent"


class AuthSessionResponse(BaseModel):
    authenticated: bool
    method: str
    user: SessionUser = Field(default_factory=SessionUser)
    message: str | None = None


LoginResponse = AuthSessionResponse
SessionResponse = AuthSessionResponse
