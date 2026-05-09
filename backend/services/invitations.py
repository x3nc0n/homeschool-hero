from __future__ import annotations

import smtplib
from datetime import datetime
from email.message import EmailMessage
from urllib.parse import quote

from backend.config import settings
from backend.models import FamilyRole


def build_invitation_link(invitation_id: int, token: str) -> str:
    path = f'/accept-invite/{invitation_id}?token={quote(token)}'
    base_url = (settings.invitation_base_url or '').strip()
    if not base_url:
        return path
    return f"{base_url.rstrip('/')}{path}"


def smtp_enabled() -> bool:
    return bool((settings.smtp_host or '').strip() and (settings.smtp_from_email or '').strip())


def send_invitation_email(*, email: str, family_name: str, role: FamilyRole, invite_link: str, expires_at: datetime) -> None:
    message = EmailMessage()
    message['Subject'] = f'Join {family_name} on Homeschool Hero'
    message['From'] = settings.smtp_from_email or 'no-reply@homeschool-hero.local'
    message['To'] = email
    message.set_content(
        '\n'.join(
            [
                f"You've been invited to join {family_name} as {role.value}.",
                '',
                f'Accept your invitation: {invite_link}',
                f'Invitation expires: {expires_at.isoformat()}',
            ]
        )
    )

    server = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10)
    try:
        if settings.smtp_use_tls:
            server.starttls()
        if settings.smtp_username and settings.smtp_password:
            server.login(settings.smtp_username, settings.smtp_password)
        server.send_message(message)
    finally:
        server.quit()


def dispatch_invitation(
    *,
    email: str,
    family_name: str,
    role: FamilyRole,
    invitation_id: int,
    token: str,
    expires_at: datetime,
) -> tuple[str, bool, str | None]:
    invite_link = build_invitation_link(invitation_id, token)
    if not smtp_enabled():
        return 'link', False, invite_link
    try:
        send_invitation_email(
            email=email,
            family_name=family_name,
            role=role,
            invite_link=invite_link,
            expires_at=expires_at,
        )
        return 'email', True, invite_link
    except Exception:
        return 'link', False, invite_link
