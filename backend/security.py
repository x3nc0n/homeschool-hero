from __future__ import annotations

from dataclasses import dataclass
from typing import Any, TypeVar

import bcrypt
from fastapi import Depends, HTTPException, Request, status
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.database import get_db
from backend.models import Family, FamilyMembership, User

serializer = URLSafeTimedSerializer(settings.secret_key, salt='homeschool-session')
ModelT = TypeVar('ModelT')


@dataclass(slots=True)
class AuthSession:
    user_id: int
    family_id: int
    email: str
    display_name: str
    role: str
    is_owner: bool
    family_name: str
    student_id: int | None = None


def normalize_email(email: str) -> str:
    return email.strip().lower()


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))


def create_session_token(user_id: int, family_id: int) -> str:
    return serializer.dumps({'user_id': user_id, 'family_id': family_id})


def verify_session_token(token: str | None) -> dict[str, int] | None:
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
    if not isinstance(user_id, int) or not isinstance(family_id, int):
        return None
    return {'user_id': user_id, 'family_id': family_id}


async def get_auth_session(request: Request, db: AsyncSession = Depends(get_db)) -> AuthSession:
    claims = getattr(request.state, 'session', None)
    if not claims:
        token = request.cookies.get(settings.session_cookie_name)
        claims = verify_session_token(token)
    if not claims:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Authentication required')

    stmt = (
        select(User, FamilyMembership, Family)
        .join(FamilyMembership, FamilyMembership.user_id == User.id)
        .join(Family, Family.id == FamilyMembership.family_id)
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
    user, membership, family = row
    return AuthSession(
        user_id=user.id,
        family_id=family.id,
        email=user.email,
        display_name=user.display_name,
        role=membership.role.value,
        is_owner=membership.is_owner,
        family_name=family.name,
        student_id=membership.student_id,
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
) -> tuple[User, FamilyMembership, Family] | None:
    stmt = (
        select(User, FamilyMembership, Family)
        .join(FamilyMembership, FamilyMembership.user_id == User.id)
        .join(Family, Family.id == FamilyMembership.family_id)
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
