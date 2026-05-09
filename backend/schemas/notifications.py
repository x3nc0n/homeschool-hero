from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from backend.models.notification import NotificationType


class NotificationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    family_id: int
    user_id: int
    type: NotificationType
    title: str
    message: str
    read: bool
    created_at: datetime
    link: str | None = None


class NotificationListResponse(BaseModel):
    items: list[NotificationRead]
    total: int
    unread_count: int
    page: int
    page_size: int
    total_pages: int


class NotificationReadUpdate(BaseModel):
    read: bool = True


class NotificationReadAllResponse(BaseModel):
    updated: int


class NotificationPreferenceRead(BaseModel):
    notification_type: NotificationType
    in_app_enabled: bool
    email_enabled: bool


class NotificationPreferenceUpdate(BaseModel):
    notification_type: NotificationType
    in_app_enabled: bool = True
    email_enabled: bool = False


class NotificationPreferenceUpdateRequest(BaseModel):
    preferences: list[NotificationPreferenceUpdate] = Field(default_factory=list)
