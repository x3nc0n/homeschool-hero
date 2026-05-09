from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models import Notification
from backend.schemas.notifications import (
    NotificationListResponse,
    NotificationPreferenceRead,
    NotificationPreferenceUpdateRequest,
    NotificationRead,
    NotificationReadAllResponse,
    NotificationReadUpdate,
)
from backend.security import AuthSession, get_auth_session
from backend.services.notifications import get_notification_preferences, get_unread_count, update_notification_preferences

router = APIRouter(prefix='/notifications', tags=['notifications'])


@router.get('', response_model=NotificationListResponse)
async def list_notifications(
    read: bool | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(get_auth_session),
) -> NotificationListResponse:
    filters = [Notification.user_id == auth.user_id, Notification.family_id == auth.family_id]
    if read is not None:
        filters.append(Notification.read.is_(read))

    total = (await db.execute(select(func.count(Notification.id)).where(*filters))).scalar_one()
    unread_count = await get_unread_count(db, user_id=auth.user_id, family_id=auth.family_id)
    total_pages = max((int(total or 0) + page_size - 1) // page_size, 1)
    items = (
        await db.execute(
            select(Notification)
            .where(*filters)
            .order_by(Notification.created_at.desc(), Notification.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).scalars().all()

    return NotificationListResponse(
        items=[NotificationRead.model_validate(item) for item in items],
        total=int(total or 0),
        unread_count=unread_count,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.patch('/{notification_id}/read', response_model=NotificationRead)
async def mark_notification_read(
    notification_id: int,
    payload: NotificationReadUpdate,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(get_auth_session),
) -> NotificationRead:
    notification = (
        await db.execute(
            select(Notification).where(
                Notification.id == notification_id,
                Notification.user_id == auth.user_id,
                Notification.family_id == auth.family_id,
            )
        )
    ).scalar_one_or_none()
    if notification is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Notification not found')

    notification.read = payload.read
    await db.commit()
    await db.refresh(notification)
    return NotificationRead.model_validate(notification)


@router.post('/read-all', response_model=NotificationReadAllResponse)
async def mark_all_notifications_read(
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(get_auth_session),
) -> NotificationReadAllResponse:
    result = await db.execute(
        update(Notification)
        .where(
            Notification.user_id == auth.user_id,
            Notification.family_id == auth.family_id,
            Notification.read.is_(False),
        )
        .values(read=True)
    )
    await db.commit()
    return NotificationReadAllResponse(updated=int(result.rowcount or 0))


@router.get('/preferences', response_model=list[NotificationPreferenceRead])
async def get_preferences(
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(get_auth_session),
) -> list[NotificationPreferenceRead]:
    preferences = await get_notification_preferences(db, auth.user_id)
    return [
        NotificationPreferenceRead(
            notification_type=preference.notification_type,
            in_app_enabled=preference.in_app_enabled,
            email_enabled=preference.email_enabled,
        )
        for preference in preferences
    ]


@router.put('/preferences', response_model=list[NotificationPreferenceRead])
async def put_preferences(
    payload: NotificationPreferenceUpdateRequest,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(get_auth_session),
) -> list[NotificationPreferenceRead]:
    updated = await update_notification_preferences(
        db,
        auth.user_id,
        [
            (preference.notification_type, preference.in_app_enabled, preference.email_enabled)
            for preference in payload.preferences
        ],
    )
    await db.commit()
    return [
        NotificationPreferenceRead(
            notification_type=preference.notification_type,
            in_app_enabled=preference.in_app_enabled,
            email_enabled=preference.email_enabled,
        )
        for preference in updated
    ]
