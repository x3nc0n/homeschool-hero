"""Email sending abstraction supporting SMTP and Azure Communication Services."""
from __future__ import annotations

import logging
import smtplib
from datetime import datetime, timezone
from email.message import EmailMessage
from typing import Any

from backend.config import Settings, settings

logger = logging.getLogger(__name__)


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def _status(*, enabled: bool, configured: bool, reason: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        'name': 'email',
        'enabled': enabled,
        'configured': configured,
        'status': 'enabled' if enabled else 'disabled',
        'reason': reason,
        'details': details or {},
        'checked_at': _timestamp(),
    }


def _provider(config: Settings) -> str:
    return (config.email_provider or '').strip().lower()


def email_enabled(config: Settings = settings) -> bool:
    """Return True if any email provider is properly configured."""
    provider = _provider(config)
    if provider == 'smtp':
        return _smtp_configured(config)
    if provider == 'acs':
        return _acs_configured(config)
    return False


def send_email(*, to_email: str, subject: str, html: str, config: Settings = settings) -> None:
    """Send an email via the configured provider."""
    provider = _provider(config)
    if provider == 'smtp':
        _send_smtp(to_email=to_email, subject=subject, html=html, config=config)
    elif provider == 'acs':
        _send_acs(to_email=to_email, subject=subject, html=html, config=config)
    else:
        logger.debug('Email sending skipped — no provider configured')


def check_provider_health(config: Settings = settings) -> dict[str, Any]:
    """Return health/capability status dict for the configured email provider."""
    provider = _provider(config)
    if provider == 'smtp':
        return _check_smtp_health(config)
    if provider == 'acs':
        return _check_acs_health(config)
    if provider in {'', 'none'}:
        return _status(
            enabled=False,
            configured=False,
            reason='EMAIL_PROVIDER is not set or set to "none".',
            details={},
        )
    return _status(
        enabled=False,
        configured=False,
        reason=f'Unsupported email provider "{provider}".',
        details={'provider': provider},
    )


def _smtp_configured(config: Settings) -> bool:
    if not config.smtp_host or not config.smtp_from_email:
        return False
    if config.smtp_username and not config.smtp_password:
        return False
    return True


def _send_smtp(*, to_email: str, subject: str, html: str, config: Settings) -> None:
    if not _smtp_configured(config):
        return

    message = EmailMessage()
    message['Subject'] = subject
    message['From'] = config.smtp_from_email or ''
    message['To'] = to_email
    message.set_content('This email contains HTML content. Please view it in an HTML-capable client.')
    message.add_alternative(html, subtype='html')

    server = smtplib.SMTP(config.smtp_host, config.smtp_port, timeout=10)
    try:
        server.ehlo()
        if config.smtp_use_tls:
            server.starttls()
            server.ehlo()
        if config.smtp_username:
            server.login(config.smtp_username, config.smtp_password or '')
        server.send_message(message)
    finally:
        try:
            server.quit()
        except Exception:
            logger.debug('SMTP quit failed', exc_info=True)


def _check_smtp_health(config: Settings) -> dict[str, Any]:
    if not config.smtp_host or not config.smtp_from_email:
        return _status(
            enabled=False,
            configured=False,
            reason='SMTP_HOST and SMTP_FROM_EMAIL must be configured to enable email.',
            details={},
        )
    if config.smtp_username and not config.smtp_password:
        return _status(
            enabled=False,
            configured=False,
            reason='SMTP_PASSWORD is required when SMTP_USERNAME is configured.',
            details={'host': config.smtp_host, 'port': config.smtp_port},
        )

    server: smtplib.SMTP | None = None
    try:
        server = smtplib.SMTP(config.smtp_host, config.smtp_port, timeout=5)
        server.ehlo()
        if config.smtp_use_tls:
            server.starttls()
            server.ehlo()
        if config.smtp_username:
            server.login(config.smtp_username, config.smtp_password or '')
        code, _ = server.noop()
        if code >= 400:
            raise RuntimeError(f'SMTP NOOP returned {code}')
    except Exception as exc:
        return _status(
            enabled=False,
            configured=True,
            reason=f'SMTP is unreachable: {exc}',
            details={'host': config.smtp_host, 'port': config.smtp_port},
        )
    finally:
        if server is not None:
            try:
                server.quit()
            except Exception:
                pass

    return _status(
        enabled=True,
        configured=True,
        reason='SMTP is reachable.',
        details={'host': config.smtp_host, 'port': config.smtp_port},
    )


def _acs_configured(config: Settings) -> bool:
    return bool(config.acs_connection_string and config.acs_sender_address)


def _send_acs(*, to_email: str, subject: str, html: str, config: Settings) -> None:
    if not _acs_configured(config):
        return

    from azure.communication.email import EmailClient

    client = EmailClient.from_connection_string(config.acs_connection_string or '')
    message = {
        'senderAddress': config.acs_sender_address,
        'recipients': {
            'to': [{'address': to_email}],
        },
        'content': {
            'subject': subject,
            'html': html,
            'plainText': 'This email contains HTML content. Please view it in an HTML-capable client.',
        },
    }
    poller = client.begin_send(message)
    result = poller.result()
    logger.info('ACS email sent: message_id=%s, status=%s', result.get('id'), result.get('status'))


def _check_acs_health(config: Settings) -> dict[str, Any]:
    if not config.acs_connection_string:
        return _status(
            enabled=False,
            configured=False,
            reason='ACS_CONNECTION_STRING must be configured to enable Azure Communication Services email.',
            details={},
        )
    if not config.acs_sender_address:
        return _status(
            enabled=False,
            configured=False,
            reason='ACS_SENDER_ADDRESS must be configured.',
            details={'provider': 'acs'},
        )

    try:
        from azure.communication.email import EmailClient

        EmailClient.from_connection_string(config.acs_connection_string)
    except Exception as exc:
        return _status(
            enabled=False,
            configured=True,
            reason=f'ACS client initialization failed: {exc}',
            details={'provider': 'acs', 'sender': config.acs_sender_address},
        )

    return _status(
        enabled=True,
        configured=True,
        reason='Azure Communication Services email is configured.',
        details={'provider': 'acs', 'sender': config.acs_sender_address},
    )
