from fastapi import APIRouter, HTTPException, Request, Response, status

from backend.config import settings
from backend.schemas.auth import LoginRequest, LoginResponse, SessionResponse
from backend.security import authenticate, create_session_token

router = APIRouter(prefix="/auth", tags=["auth"])


def _session_response(authenticated: bool, method: str, message: str | None = None) -> SessionResponse:
    return SessionResponse(authenticated=authenticated, method=method, message=message)


@router.post("/login", response_model=LoginResponse)
async def login(payload: LoginRequest, response: Response) -> LoginResponse:
    method = payload.method
    credential = payload.credential

    if payload.password:
        method = "password"
        credential = payload.password
    elif payload.pin:
        method = "pin"
        credential = payload.pin

    if not method or not credential:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Missing credentials")

    if not authenticate(method, credential):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    token = create_session_token(method)
    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        httponly=True,
        samesite="lax",
        max_age=settings.session_max_age_seconds,
        path="/",
    )
    return _session_response(authenticated=True, method=method, message="Login successful")


@router.post("/logout", response_model=LoginResponse)
async def logout(response: Response) -> LoginResponse:
    response.delete_cookie(settings.session_cookie_name, path="/")
    return _session_response(authenticated=False, method="logged_out", message="Logged out")


@router.get("/me", response_model=SessionResponse)
async def me(request: Request) -> SessionResponse:
    session = getattr(request.state, "session", {"method": "unknown"})
    return _session_response(authenticated=True, method=session["method"])
