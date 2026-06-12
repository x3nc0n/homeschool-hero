from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any

from fastapi import Request

from backend.security import AuthSession, get_request_ip
from backend.services.logging_config import _coerce_details, _coerce_log_value, _sanitize_log_text, get_context


@dataclass(slots=True, frozen=True)
class SecurityActor:
    user_id: int | None = None
    email: str | None = None


@dataclass(slots=True, frozen=True)
class SecurityTarget:
    resource: str | None = None
    id: str | None = None
    type: str | None = None


@dataclass(slots=True, frozen=True)
class SecurityEvent:
    actor: SecurityActor = field(default_factory=SecurityActor)
    target: SecurityTarget = field(default_factory=SecurityTarget)
    result: str = 'success'
    source_ip: str | None = None
    user_agent: str | None = None
    correlation_id: str | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    details: dict[str, Any] | None = None
    event_category: str = field(default='security', init=False)
    event_type: str = field(init=False)

    def to_log_extra(self) -> dict[str, Any]:
        return {
            'event_timestamp': self.timestamp.isoformat(),
            'event_category': self.event_category,
            'event_type': self.event_type,
            'actor': _compact(asdict(self.actor)),
            'target': _compact(asdict(self.target)),
            'result': self.result,
            'source_ip': self.source_ip,
            'user_agent': self.user_agent,
            'correlation_id': self.correlation_id,
            'details': self.details,
        }


@dataclass(slots=True, frozen=True)
class AuthFailureEvent(SecurityEvent):
    event_type: str = field(default='auth_failure', init=False)
    result: str = field(default='failure', init=False)


@dataclass(slots=True, frozen=True)
class AuthSuccessEvent(SecurityEvent):
    event_type: str = field(default='auth_success', init=False)
    result: str = field(default='success', init=False)


@dataclass(slots=True, frozen=True)
class BreakglassLoginEvent(SecurityEvent):
    event_type: str = field(default='breakglass_login', init=False)
    result: str = field(default='success', init=False)


@dataclass(slots=True, frozen=True)
class RbacDenialEvent(SecurityEvent):
    event_type: str = field(default='rbac_denial', init=False)
    result: str = field(default='failure', init=False)


@dataclass(slots=True, frozen=True)
class RoleMappingFailureEvent(SecurityEvent):
    event_type: str = field(default='role_mapping_failure', init=False)
    result: str = field(default='failure', init=False)


@dataclass(slots=True, frozen=True)
class SessionCreatedEvent(SecurityEvent):
    event_type: str = field(default='session_created', init=False)
    result: str = field(default='success', init=False)


@dataclass(slots=True, frozen=True)
class SessionDestroyedEvent(SecurityEvent):
    event_type: str = field(default='session_destroyed', init=False)
    result: str = field(default='success', init=False)


def _compact(payload: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in payload.items() if value is not None}


def _request_metadata(request: Request | None) -> dict[str, Any]:
    context = get_context()
    return {
        'source_ip': get_request_ip(request) if request is not None else None,
        'user_agent': request.headers.get('user-agent') if request is not None else None,
        'correlation_id': (
            getattr(request.state, 'correlation_id', None)
            if request is not None
            else context.get('correlation_id')
        ),
    }


def _actor_from_subject(subject: AuthSession | Any | None, *, email: str | None = None) -> SecurityActor:
    if isinstance(subject, AuthSession):
        return SecurityActor(user_id=subject.user_id, email=subject.email)
    if subject is None:
        return SecurityActor(email=email)
    return SecurityActor(
        user_id=getattr(subject, 'id', None),
        email=email or getattr(subject, 'email', None),
    )


def emit_security_event(
    logger: logging.Logger,
    event: SecurityEvent,
    *,
    level: int = logging.INFO,
    message: str | None = None,
) -> None:
    extra = event.to_log_extra()
    sanitized_extra = {
        'event_timestamp': _coerce_log_value(extra['event_timestamp']),
        'event_category': _coerce_log_value(extra['event_category']),
        'event_type': _coerce_log_value(extra['event_type']),
        'actor': _coerce_details(extra['actor']),
        'target': _coerce_details(extra['target']),
        'result': _coerce_log_value(extra['result']),
        'source_ip': _coerce_log_value(extra['source_ip']),
        'user_agent': _coerce_log_value(extra['user_agent']),
        'correlation_id': _coerce_log_value(extra['correlation_id']),
        'details': _coerce_details(extra['details']),
    }
    sanitized_message = _sanitize_log_text(message or f'Security event {event.event_type}')
    logger.log(level, sanitized_message, extra=sanitized_extra)


def emit_auth_failure(
    logger: logging.Logger,
    *,
    request: Request,
    email: str,
    family_id: int | None,
    reason: str,
    user_id: int | None = None,
    target_resource: str = '/api/auth/login',
    target_id: str | None = None,
) -> None:
    emit_security_event(
        logger,
        AuthFailureEvent(
            actor=SecurityActor(user_id=user_id, email=email),
            target=SecurityTarget(resource=target_resource, id=target_id, type='auth_endpoint'),
            details=_compact({'reason': reason, 'family_id': family_id}),
            **_request_metadata(request),
        ),
        level=logging.WARNING,
    )


def emit_auth_success(
    logger: logging.Logger,
    *,
    request: Request,
    subject: AuthSession | Any,
    family_id: int | None,
    provider: str,
    target_resource: str,
    target_id: str | None = None,
) -> None:
    emit_security_event(
        logger,
        AuthSuccessEvent(
            actor=_actor_from_subject(subject),
            target=SecurityTarget(resource=target_resource, id=target_id, type='auth_endpoint'),
            details=_compact({'family_id': family_id, 'provider': provider}),
            **_request_metadata(request),
        ),
    )


def emit_breakglass_login(
    logger: logging.Logger,
    *,
    request: Request,
    subject: AuthSession | Any,
    configured_provider: str,
    family_id: int | None,
    target_id: str | None = None,
) -> None:
    emit_security_event(
        logger,
        BreakglassLoginEvent(
            actor=_actor_from_subject(subject),
            target=SecurityTarget(resource='/api/auth/login', id=target_id, type='auth_endpoint'),
            details=_compact({'configured_provider': configured_provider, 'family_id': family_id}),
            **_request_metadata(request),
        ),
        level=logging.WARNING,
    )


def emit_session_created(
    logger: logging.Logger,
    *,
    request: Request,
    subject: AuthSession | Any,
    session_id: str | None,
    family_id: int | None,
    auth_provider: str,
) -> None:
    emit_security_event(
        logger,
        SessionCreatedEvent(
            actor=_actor_from_subject(subject),
            target=SecurityTarget(resource='session', id=session_id, type='session'),
            details=_compact({'family_id': family_id, 'auth_provider': auth_provider}),
            **_request_metadata(request),
        ),
    )


def emit_session_destroyed(
    logger: logging.Logger,
    *,
    request: Request | None,
    subject: AuthSession | Any,
    session_id: str | None,
    family_id: int | None,
    auth_provider: str | None,
) -> None:
    emit_security_event(
        logger,
        SessionDestroyedEvent(
            actor=_actor_from_subject(subject),
            target=SecurityTarget(resource='session', id=session_id, type='session'),
            details=_compact({'family_id': family_id, 'auth_provider': auth_provider}),
            **_request_metadata(request),
        ),
    )


def emit_rbac_denial(
    logger: logging.Logger,
    *,
    request: Request | None,
    auth: AuthSession,
    action: str,
    reason: str,
    details: dict[str, Any] | None = None,
) -> None:
    target_resource = request.url.path if request is not None else action
    emit_security_event(
        logger,
        RbacDenialEvent(
            actor=_actor_from_subject(auth),
            target=SecurityTarget(resource=target_resource, type='authorization'),
            details=_compact({'action': action, 'reason': reason, **(details or {})}),
            **_request_metadata(request),
        ),
        level=logging.WARNING,
    )


def emit_role_mapping_failure(
    logger: logging.Logger,
    *,
    provider: str,
    source: str,
    request: Request | None = None,
    email: str | None = None,
    external_id: str | None = None,
    unmapped_roles: list[str] | tuple[str, ...] = (),
) -> None:
    emit_security_event(
        logger,
        RoleMappingFailureEvent(
            actor=SecurityActor(email=email),
            target=SecurityTarget(resource=source, id=external_id, type=f'{provider}_roles'),
            details=_compact({'provider': provider, 'unmapped_roles': list(unmapped_roles) or None}),
            **_request_metadata(request),
        ),
        level=logging.WARNING,
    )
