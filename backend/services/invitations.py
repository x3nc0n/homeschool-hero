from __future__ import annotations

from datetime import datetime
from html import escape
from urllib.parse import quote

from backend.config import Settings, settings
from backend.models import FamilyRole
from backend.services.email_service import email_enabled, send_email


def build_invitation_link(invitation_id: int, token: str) -> str:
    path = f'/accept-invite/{invitation_id}?token={quote(token)}'
    base_url = (settings.invitation_base_url or '').strip()
    if not base_url:
        return path
    return f"{base_url.rstrip('/')}{path}"


def send_invitation_email(
    *,
    email: str,
    family_name: str,
    role: FamilyRole,
    invite_link: str,
    expires_at: datetime,
    config: Settings = settings,
) -> None:
    subject = f'Join {family_name} on Homeschool Hero'
    html = (
        '<html><body style="font-family:Arial,sans-serif;background:#f8fafc;padding:24px;">'
        '<div style="max-width:560px;margin:0 auto;background:#ffffff;border:1px solid #e2e8f0;'
        'border-radius:12px;padding:24px;">'
        f'<h1 style="margin:0 0 12px;font-size:20px;color:#0f172a;">Join {escape(family_name)}</h1>'
        f'<p style="margin:0 0 12px;color:#334155;line-height:1.6;">You&apos;ve been invited to join '
        f'{escape(family_name)} as {escape(role.value)}.</p>'
        f'<p style="margin:0 0 20px;color:#334155;line-height:1.6;">Invitation expires: '
        f'{escape(expires_at.isoformat())}</p>'
        f'<p style="margin:0;"><a href="{escape(invite_link)}" '
        'style="display:inline-block;background:#2563eb;color:#ffffff;padding:10px 16px;'
        'border-radius:8px;text-decoration:none;font-weight:600;">Accept invitation</a></p>'
        '</div></body></html>'
    )
    send_email(to_email=email, subject=subject, html=html, config=config)


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
    if not email_enabled():
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
