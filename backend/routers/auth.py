from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.database import get_db
from backend.models import Family, FamilyMembership, FamilyRole, FamilySettings, User
from backend.schemas.auth import (
    BootstrapStatusResponse,
    LoginRequest,
    LoginResponse,
    RegisterRequest,
    RegisterResponse,
    SessionResponse,
)
from backend.security import (
    AuthSession,
    bootstrap_required,
    create_session_token,
    get_auth_session,
    get_login_membership,
    hash_password,
    verify_password,
)

router = APIRouter(prefix='/auth', tags=['auth'])


def _set_session_cookie(response: Response, *, user_id: int, family_id: int) -> None:
    response.set_cookie(
        key=settings.session_cookie_name,
        value=create_session_token(user_id=user_id, family_id=family_id),
        httponly=True,
        samesite='lax',
        secure=settings.session_cookie_secure,
        max_age=settings.session_max_age_seconds,
        path='/',
    )


def _session_response(auth: AuthSession, message: str | None = None) -> SessionResponse:
    return SessionResponse(
        authenticated=True,
        user={
            'id': auth.user_id,
            'email': auth.email,
            'display_name': auth.display_name,
            'is_active': True,
        },
        family={'id': auth.family_id, 'name': auth.family_name},
        membership={'role': auth.role, 'is_owner': auth.is_owner, 'student_id': auth.student_id},
        message=message,
    )


@router.get('/bootstrap', response_model=BootstrapStatusResponse)
async def bootstrap_status(db: AsyncSession = Depends(get_db)) -> BootstrapStatusResponse:
    return BootstrapStatusResponse(bootstrap_required=await bootstrap_required(db))


@router.post('/register', response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest, response: Response, db: AsyncSession = Depends(get_db)) -> RegisterResponse:
    if not await bootstrap_required(db):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Bootstrap is no longer available')

    family = Family(
        name=payload.family_name.strip(),
        settings={'timezone': payload.timezone, 'grading_scale': payload.grading_scale},
    )
    user = User(
        email=payload.email,
        display_name=payload.display_name.strip(),
        password_hash=hash_password(payload.password),
        is_active=True,
    )
    now = datetime.now(timezone.utc)
    membership = FamilyMembership(role=FamilyRole.parent, is_owner=True, invited_at=now, accepted_at=now)
    membership.user = user
    membership.family = family
    family_settings = FamilySettings(family=family, timezone=payload.timezone.strip(), grading_scale=payload.grading_scale.strip())

    db.add_all([family, user, membership, family_settings])
    await db.commit()

    auth = AuthSession(
        user_id=user.id,
        family_id=family.id,
        email=user.email,
        display_name=user.display_name,
        role=membership.role.value,
        is_owner=membership.is_owner,
        family_name=family.name,
        student_id=membership.student_id,
    )
    _set_session_cookie(response, user_id=user.id, family_id=family.id)
    return _session_response(auth, message='Owner account created')


@router.post('/login', response_model=LoginResponse)
async def login(payload: LoginRequest, response: Response, db: AsyncSession = Depends(get_db)) -> LoginResponse:
    membership_row = await get_login_membership(db, email=payload.email, family_id=payload.family_id)
    if membership_row is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Invalid email or password')

    user, membership, family = membership_row
    if not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Invalid email or password')

    _set_session_cookie(response, user_id=user.id, family_id=family.id)
    auth = AuthSession(
        user_id=user.id,
        family_id=family.id,
        email=user.email,
        display_name=user.display_name,
        role=membership.role.value,
        is_owner=membership.is_owner,
        family_name=family.name,
        student_id=membership.student_id,
    )
    return _session_response(auth, message='Login successful')


@router.post('/logout')
async def logout(response: Response) -> dict[str, str]:
    response.delete_cookie(settings.session_cookie_name, path='/')
    return {'status': 'logged_out'}


@router.get('/me', response_model=SessionResponse)
async def me(_: Request, auth: AuthSession = Depends(get_auth_session)) -> SessionResponse:
    return _session_response(auth)
