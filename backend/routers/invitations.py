from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.config import settings
from backend.database import get_db
from backend.models import AuditAction, Family, FamilyMembership, FamilyRole, Invitation, NotificationType, Student, User
from backend.routers.auth import _session_response, _set_session_cookie
from backend.schemas.auth import SessionResponse
from backend.schemas.invitations import InvitationAccept, InvitationCreate, InvitationRead
from backend.security import AuthSession, get_family_record, hash_password, normalize_email, verify_password
from backend.services.audit import log_event
from backend.services.authorization import Capability, require_capabilities
from backend.services.invitations import build_invitation_link, dispatch_invitation
from backend.services.notifications import create_family_notifications, create_notification

router = APIRouter(prefix='/invitations', tags=['invitations'])


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _serialize_invitation(invitation: Invitation, *, delivery_method: str = 'link', email_sent: bool = False) -> InvitationRead:
    invite_link = build_invitation_link(invitation.id, invitation.token)
    now = datetime.now(timezone.utc)
    expires_at = _as_utc(invitation.expires_at)
    return InvitationRead(
        id=invitation.id,
        email=invitation.email,
        role=invitation.role,
        student_id=invitation.student_id,
        student_name=invitation.student.name if invitation.student else None,
        expires_at=expires_at,
        accepted_at=invitation.accepted_at,
        invite_link=invite_link,
        invite_code=invitation.token,
        delivery_method=delivery_method,
        email_sent=email_sent,
        is_expired=expires_at <= now,
        created_at=invitation.created_at,
    )


def _invitation_snapshot(invitation: Invitation) -> dict[str, object | None]:
    return {
        'id': invitation.id,
        'email': invitation.email,
        'role': invitation.role.value,
        'student_id': invitation.student_id,
        'expires_at': invitation.expires_at.isoformat() if invitation.expires_at else None,
        'accepted_at': invitation.accepted_at.isoformat() if invitation.accepted_at else None,
    }


@router.get('', response_model=list[InvitationRead])
async def list_invitations(
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.manage_invitations, action='view invitations')),
) -> list[InvitationRead]:
    result = await db.execute(
        select(Invitation)
        .options(selectinload(Invitation.student))
        .where(Invitation.family_id == auth.family_id, Invitation.accepted_at.is_(None))
        .order_by(Invitation.created_at.desc())
    )
    invitations = result.scalars().all()
    return [_serialize_invitation(invitation) for invitation in invitations]


@router.post('', response_model=InvitationRead, status_code=status.HTTP_201_CREATED)
async def create_invitation(
    payload: InvitationCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.manage_invitations, action='create invitations')),
) -> InvitationRead:
    student = None
    if payload.role == FamilyRole.student_viewer:
        student = await get_family_record(db, Student, payload.student_id, auth.family_id)
        if not student:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Student not found')

    existing = await db.execute(
        select(Invitation).where(
            Invitation.family_id == auth.family_id,
            Invitation.email == normalize_email(payload.email),
            Invitation.accepted_at.is_(None),
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='A pending invitation already exists for this email')

    expires_at = datetime.now(timezone.utc) + timedelta(days=payload.expires_in_days or settings.invitation_expiry_days)
    invitation = Invitation(
        family_id=auth.family_id,
        email=normalize_email(payload.email),
        role=payload.role,
        student_id=payload.student_id,
        token=secrets.token_urlsafe(32),
        expires_at=expires_at,
    )
    db.add(invitation)
    await db.flush()
    await log_event(
        db,
        action=AuditAction.invitation_create,
        actor=auth,
        family_id=auth.family_id,
        target_type='invitation',
        target_id=invitation.id,
        before=None,
        after=_invitation_snapshot(invitation),
        request=request,
    )
    await db.commit()
    await db.refresh(invitation, attribute_names=['student'])

    await create_family_notifications(
        db,
        family_id=auth.family_id,
        notification_type=NotificationType.invitation,
        title=f'Invitation created for {invitation.email}',
        message=f'{invitation.role.value.replace("_", " ")} access was invited and expires on {expires_at.date().isoformat()}.',
        link='/invitations',
        roles={FamilyRole.parent, FamilyRole.co_parent},
    )
    existing_user = (await db.execute(select(User).where(User.email == invitation.email))).scalar_one_or_none()
    if existing_user is not None:
        await create_notification(
            db,
            existing_user.id,
            NotificationType.invitation,
            title=f'You were invited to join {auth.family_name}',
            message='Open the invitation page to accept access to this family workspace.',
            link=build_invitation_link(invitation.id, invitation.token),
            family_id=auth.family_id,
        )
    await db.commit()

    delivery_method, email_sent, _ = dispatch_invitation(
        email=invitation.email,
        family_name=auth.family_name,
        role=invitation.role,
        invitation_id=invitation.id,
        token=invitation.token,
        expires_at=expires_at,
    )
    return _serialize_invitation(invitation, delivery_method=delivery_method, email_sent=email_sent)


@router.post('/{invitation_id}/accept', response_model=SessionResponse)
async def accept_invitation(
    invitation_id: int,
    payload: InvitationAccept,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> SessionResponse:
    result = await db.execute(
        select(Invitation, Family)
        .join(Family, Family.id == Invitation.family_id)
        .where(Invitation.id == invitation_id)
    )
    row = result.one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Invitation not found')

    invitation, family = row
    now = datetime.now(timezone.utc)
    if invitation.token != payload.token:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Invitation token is invalid')
    if invitation.accepted_at is not None:
        raise HTTPException(status_code=status.HTTP_410_GONE, detail='Invitation has already been used')
    expires_at = _as_utc(invitation.expires_at)
    if expires_at <= now:
        raise HTTPException(status_code=status.HTTP_410_GONE, detail='Invitation has expired')
    if normalize_email(payload.email) != invitation.email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Invitation email does not match')
    if invitation.role == FamilyRole.student_viewer:
        if invitation.student_id is None:
            raise HTTPException(status_code=status.HTTP_410_GONE, detail='The student linked to this invitation no longer exists')
        student = await get_family_record(db, Student, invitation.student_id, invitation.family_id)
        if not student:
            raise HTTPException(status_code=status.HTTP_410_GONE, detail='The student linked to this invitation no longer exists')

    existing_user = (
        await db.execute(select(User).where(User.email == invitation.email))
    ).scalar_one_or_none()
    if existing_user is not None:
        if not existing_user.is_active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='User account is inactive')
        if not verify_password(payload.password, existing_user.password_hash):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Existing account password is incorrect')
        user = existing_user
    else:
        user = User(
            email=invitation.email,
            display_name=payload.display_name.strip(),
            password_hash=hash_password(payload.password),
            is_active=True,
        )
        db.add(user)
        await db.flush()

    membership_exists = (
        await db.execute(
            select(FamilyMembership).where(
                FamilyMembership.user_id == user.id,
                FamilyMembership.family_id == invitation.family_id,
            )
        )
    ).scalar_one_or_none()
    if membership_exists is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='User is already a member of this family')

    membership = FamilyMembership(
        user_id=user.id,
        family_id=invitation.family_id,
        role=invitation.role,
        is_owner=False,
        student_id=invitation.student_id,
        invited_at=invitation.created_at,
        accepted_at=now,
    )
    db.add(membership)
    invitation.accepted_at = now
    await create_family_notifications(
        db,
        family_id=invitation.family_id,
        notification_type=NotificationType.invitation,
        title=f'Invitation accepted by {invitation.email}',
        message=f'{payload.display_name.strip() or invitation.email} joined the family workspace.',
        link='/invitations',
        roles={FamilyRole.parent, FamilyRole.co_parent},
    )
    await create_notification(
        db,
        user.id,
        NotificationType.invitation,
        title=f'Welcome to {family.name}',
        message='Your invitation has been accepted and your access is ready.',
        link='/dashboard',
        family_id=family.id,
    )
    await db.commit()

    auth = AuthSession(
        user_id=user.id,
        family_id=family.id,
        email=user.email,
        display_name=user.display_name,
        auth_provider=user.auth_provider,
        role=membership.role.value,
        is_owner=membership.is_owner,
        family_name=family.name,
        student_id=membership.student_id,
    )
    _set_session_cookie(response, request, user_id=user.id, family_id=family.id)
    await log_event(
        db,
        action=AuditAction.invitation_accept,
        actor=user,
        family_id=family.id,
        target_type='invitation',
        target_id=invitation.id,
        before={**_invitation_snapshot(invitation), 'accepted_at': None},
        after={
            **_invitation_snapshot(invitation),
            'accepted_by_user_id': user.id,
            'membership_role': membership.role.value,
            'membership_student_id': membership.student_id,
        },
        request=request,
    )
    await db.commit()
    return _session_response(auth, message='Invitation accepted')


@router.delete('/{invitation_id}/revoke', status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def revoke_invitation(
    invitation_id: int,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.manage_invitations, action='revoke invitations')),
) -> None:
    invitation = await get_family_record(db, Invitation, invitation_id, auth.family_id)
    if not invitation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Invitation not found')
    if invitation.accepted_at is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='Accepted invitations cannot be revoked')
    await db.delete(invitation)
    await db.commit()
