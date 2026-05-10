from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, TypedDict, TypeVar

import bcrypt
from fastapi import Depends, HTTPException, Request, Response, status
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.database import get_db
from backend.models import Family, FamilyMembership, FamilySettings, User, UserPreference
from backend.services.preferences import serialize_user_preferences

serializer = URLSafeTimedSerializer(settings.secret_key, salt='homeschool-session')
ModelT = TypeVar('ModelT')
SAFE_METHODS = {'GET', 'HEAD', 'OPTIONS'}


class SessionClaims(TypedDict):
    user_id: int
    family_id: int
    csrf: str
    sid: str
    issued_at: int


@dataclass(slots=True)
class AuthSession:
    user_id: int
    family_id: int
    email: str
    display_name: str
    auth_provider: str
    role: str
    is_owner: bool
    family_name: str
    family_state_code: str = 'CUSTOM'
    enabled_features: dict[str, bool] | None = None
    student_id: int | None = None
    ui_preferences: dict[str, str] | None = None


def normalize_email(email: str) -> str:
    return email.strip().lower()


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))


def _build_session_claims(user_id: int, family_id: int) -> SessionClaims:
    return {
        'user_id': user_id,
        'family_id': family_id,
        'csrf': secrets.token_urlsafe(24),
        'sid': secrets.token_urlsafe(24),
        'issued_at': int(datetime.now(timezone.utc).timestamp()),
    }


def create_session_token(user_id: int, family_id: int) -> tuple[str, SessionClaims]:
    claims = _build_session_claims(user_id, family_id)
    return serializer.dumps(claims), claims


def is_secure_request(request: Request | None = None) -> bool:
    if settings.session_cookie_secure:
        return True
    if request is None:
        return False
    forwarded_proto = request.headers.get('x-forwarded-proto', '')
    if forwarded_proto:
        proto = forwarded_proto.split(',')[0].strip().lower()
        return proto == 'https'
    return request.url.scheme == 'https'


def set_session_cookies(response: Response, request: Request | None, *, user_id: int, family_id: int) -> SessionClaims:
    token, claims = create_session_token(user_id=user_id, family_id=family_id)
    secure = is_secure_request(request)
    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        httponly=True,
        samesite='lax',
        secure=secure,
        max_age=settings.session_max_age_seconds,
        path='/',
    )
    response.set_cookie(
        key=settings.csrf_cookie_name,
        value=claims['csrf'],
        httponly=False,
        samesite='lax',
        secure=secure,
        max_age=settings.session_max_age_seconds,
        path='/',
    )
    return claims


def clear_session_cookies(response: Response, request: Request | None = None) -> None:
    secure = is_secure_request(request)
    response.delete_cookie(settings.session_cookie_name, path='/', secure=secure, httponly=True, samesite='lax')
    response.delete_cookie(settings.csrf_cookie_name, path='/', secure=secure, samesite='lax')


def verify_session_token(token: str | None) -> SessionClaims | None:
    if not token:
        return None
    try:
        data = serializer.loads(token, max_age=settings.session_max_age_seconds)
    except (BadSignature, SignatureExpired):
        return None
    if not isinstance(data, dict):
        return None
    user_id = data.get('user_id')
    family_id = data.get('family_id')
    csrf = data.get('csrf')
    session_id = data.get('sid')
    issued_at = data.get('issued_at')
    if not isinstance(user_id, int) or not isinstance(family_id, int):
        return None
    if not isinstance(csrf, str) or not csrf:
        return None
    if not isinstance(session_id, str) or not session_id:
        return None
    if not isinstance(issued_at, int):
        return None
    return {
        'user_id': user_id,
        'family_id': family_id,
        'csrf': csrf,
        'sid': session_id,
        'issued_at': issued_at,
    }


def session_needs_rotation(claims: SessionClaims) -> bool:
    age_seconds = int(datetime.now(timezone.utc).timestamp()) - claims['issued_at']
    threshold = min(settings.session_rotation_seconds, settings.session_max_age_seconds)
    return age_seconds >= threshold


def require_csrf(request: Request, claims: SessionClaims) -> None:
    if request.method.upper() in SAFE_METHODS:
        return
    cookie_token = request.cookies.get(settings.csrf_cookie_name)
    header_token = request.headers.get('x-csrf-token')
    if not cookie_token or not header_token or cookie_token != header_token or header_token != claims['csrf']:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='CSRF validation failed')


def get_request_ip(request: Request) -> str:
    forwarded_for = request.headers.get('x-forwarded-for', '')
    if forwarded_for:
        return forwarded_for.split(',')[0].strip()
    client = request.client
    return client.host if client else 'unknown'


def get_lockout_deadline() -> datetime:
    return datetime.now(timezone.utc) + timedelta(minutes=settings.auth_lockout_minutes)


async def get_auth_session(request: Request, db: AsyncSession = Depends(get_db)) -> AuthSession:
    claims = getattr(request.state, 'session', None)
    if not claims:
        token = request.cookies.get(settings.session_cookie_name)
        claims = verify_session_token(token)
    if not claims:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Authentication required')

    stmt = (
        select(User, FamilyMembership, Family, FamilySettings.state_code, FamilySettings.enabled_features, UserPreference)
        .join(FamilyMembership, FamilyMembership.user_id == User.id)
        .join(Family, Family.id == FamilyMembership.family_id)
        .outerjoin(FamilySettings, FamilySettings.family_id == Family.id)
        .outerjoin(UserPreference, UserPreference.user_id == User.id)
        .where(
            User.id == claims['user_id'],
            User.is_active.is_(True),
            FamilyMembership.family_id == claims['family_id'],
            FamilyMembership.accepted_at.is_not(None),
        )
    )
    result = await db.execute(stmt)
    row = result.one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Authentication required')
    user, membership, family, state_code, enabled_features, preferences = row
    return AuthSession(
        user_id=user.id,
        family_id=family.id,
        email=user.email,
        display_name=user.display_name,
        auth_provider=user.auth_provider,
        role=membership.role.value,
        is_owner=membership.is_owner,
        family_name=family.name,
        family_state_code=(state_code or 'CUSTOM').upper(),
        enabled_features=enabled_features or {},
        student_id=membership.student_id,
        ui_preferences=serialize_user_preferences(preferences),
    )


async def get_family_record(
    db: AsyncSession,
    model: type[ModelT],
    record_id: int,
    family_id: int,
    *,
    options: tuple[Any, ...] = (),
) -> ModelT | None:
    stmt = select(model)
    if options:
        stmt = stmt.options(*options)
    stmt = stmt.where(model.id == record_id, model.family_id == family_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def bootstrap_required(db: AsyncSession) -> bool:
    result = await db.execute(select(User.id).limit(1))
    return result.scalar_one_or_none() is None


async def get_login_membership(
    db: AsyncSession,
    *,
    email: str,
    family_id: int | None = None,
) -> tuple[User, FamilyMembership, Family, str | None, dict[str, bool] | None, UserPreference | None] | None:
    stmt = (
        select(User, FamilyMembership, Family, FamilySettings.state_code, FamilySettings.enabled_features, UserPreference)
        .join(FamilyMembership, FamilyMembership.user_id == User.id)
        .join(Family, Family.id == FamilyMembership.family_id)
        .outerjoin(FamilySettings, FamilySettings.family_id == Family.id)
        .outerjoin(UserPreference, UserPreference.user_id == User.id)
        .where(
            User.email == normalize_email(email),
            User.is_active.is_(True),
            FamilyMembership.accepted_at.is_not(None),
        )
        .order_by(desc(FamilyMembership.is_owner), Family.name, Family.id)
    )
    if family_id is not None:
        stmt = stmt.where(FamilyMembership.family_id == family_id)
    result = await db.execute(stmt)
    return result.first()
