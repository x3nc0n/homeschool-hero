from __future__ import annotations

import json
import logging
import re
import sys
from contextvars import ContextVar, Token
from datetime import UTC, datetime
from typing import Any

from backend.config import Settings, settings

_DEFAULT_CONTEXT = {
    'correlation_id': None,
    'user_id': None,
    'family_id': None,
    'action': None,
    'details': None,
}
_CONTROL_CHARACTER_RE = re.compile(r'[\x00-\x1f\x7f]')
_CONTROL_CHARACTER_ESCAPES = {
    '\n': r'\n',
    '\r': r'\r',
    '\t': r'\t',
}
_log_context: ContextVar[dict[str, Any]] = ContextVar('backend_log_context', default=_DEFAULT_CONTEXT.copy())
_configured = False


def _sanitize_log_text(value: str) -> str:
    return _CONTROL_CHARACTER_RE.sub(
        lambda match: _CONTROL_CHARACTER_ESCAPES.get(match.group(0), f'\\x{ord(match.group(0)):02x}'),
        value,
    )


def _coerce_log_value(value: Any) -> Any:
    if isinstance(value, str):
        escaped_value = value.replace('\n', r'\n').replace('\r', r'\r')
        return _sanitize_log_text(escaped_value)
    return value


def _coerce_details(details: Any) -> Any:
    if details is None:
        return None
    if isinstance(details, dict):
        sanitized_details: dict[str, Any] = {}
        for key, value in details.items():
            escaped_key = str(key).replace('\n', r'\n').replace('\r', r'\r')
            sanitized_details[_sanitize_log_text(escaped_key)] = _coerce_details(value)
        return sanitized_details
    if isinstance(details, (list, tuple, set)):
        return [_coerce_details(value) for value in details]
    if isinstance(details, str):
        escaped_detail = details.replace('\n', r'\n').replace('\r', r'\r')
        return _sanitize_log_text(escaped_detail)
    if isinstance(details, (int, float, bool)):
        return details
    escaped_detail = str(details).replace('\n', r'\n').replace('\r', r'\r')
    return _sanitize_log_text(escaped_detail)


def bind_context(**values: Any) -> Token:
    current = _log_context.get().copy()
    for key, value in values.items():
        if key not in _DEFAULT_CONTEXT:
            continue
        current[key] = _coerce_details(value) if key == 'details' else _coerce_log_value(value)
    return _log_context.set(current)


def update_context(**values: Any) -> None:
    bind_context(**values)


def reset_context(token: Token) -> None:
    _log_context.reset(token)


def clear_context() -> None:
    _log_context.set(_DEFAULT_CONTEXT.copy())


def get_context() -> dict[str, Any]:
    return _log_context.get().copy()


class RequestContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        context = get_context()
        record.correlation_id = _coerce_log_value(getattr(record, 'correlation_id', None) or context['correlation_id'])
        record.user_id = getattr(record, 'user_id', None) or context['user_id']
        record.family_id = getattr(record, 'family_id', None) or context['family_id']
        record.action = _coerce_log_value(getattr(record, 'action', None) or context['action'])
        details = getattr(record, 'details', None)
        record.details = _coerce_details(context['details'] if details is None else details)
        event_timestamp = getattr(record, 'event_timestamp', None)
        record.event_timestamp = _coerce_log_value(event_timestamp) if event_timestamp is not None else None
        record.event_category = _coerce_log_value(getattr(record, 'event_category', None))
        record.event_type = _coerce_log_value(getattr(record, 'event_type', None))
        actor = getattr(record, 'actor', None)
        record.actor = _coerce_details(actor) if actor is not None else None
        target = getattr(record, 'target', None)
        record.target = _coerce_details(target) if target is not None else None
        record.result = _coerce_log_value(getattr(record, 'result', None))
        record.source_ip = _coerce_log_value(getattr(record, 'source_ip', None))
        record.user_agent = _coerce_log_value(getattr(record, 'user_agent', None))
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        timestamp = getattr(record, 'event_timestamp', None) or datetime.fromtimestamp(record.created, tz=UTC).isoformat()
        payload: dict[str, Any] = {
            'timestamp': timestamp,
            'level': record.levelname,
            'logger': record.name,
            'message': _sanitize_log_text(record.getMessage()),
            'correlation_id': getattr(record, 'correlation_id', None),
            'user_id': getattr(record, 'user_id', None),
            'family_id': getattr(record, 'family_id', None),
            'action': getattr(record, 'action', None),
            'details': getattr(record, 'details', None),
            'event_category': getattr(record, 'event_category', None),
            'event_type': getattr(record, 'event_type', None),
            'actor': getattr(record, 'actor', None),
            'target': getattr(record, 'target', None),
            'result': getattr(record, 'result', None),
            'source_ip': getattr(record, 'source_ip', None),
            'user_agent': getattr(record, 'user_agent', None),
        }
        if record.exc_info:
            payload['exception'] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


class ConsoleFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        timestamp = datetime.fromtimestamp(record.created, tz=UTC).strftime('%Y-%m-%d %H:%M:%S')
        correlation_id = getattr(record, 'correlation_id', None) or '-'
        action = getattr(record, 'action', None) or '-'
        details = getattr(record, 'details', None)
        details_suffix = f' details={json.dumps(details, default=str)}' if details is not None else ''
        event_category = getattr(record, 'event_category', None)
        event_type = getattr(record, 'event_type', None)
        security_suffix = f' event={event_category}:{event_type}' if event_category and event_type else ''
        return f'{timestamp} {record.levelname:<8} [{correlation_id}] {action}{security_suffix} {_sanitize_log_text(record.getMessage())}{details_suffix}'


def should_use_json_logging(config: Settings = settings) -> bool:
    if config.log_json is not None:
        return config.log_json
    return not config.testing


def configure_logging(config: Settings = settings) -> None:
    global _configured
    if _configured:
        return

    level = getattr(logging, config.log_level.upper(), logging.INFO)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter() if should_use_json_logging(config) else ConsoleFormatter())
    handler.addFilter(RequestContextFilter())

    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    for existing in root_logger.handlers:
        existing.addFilter(RequestContextFilter())
        existing.setFormatter(handler.formatter)
    if not root_logger.handlers:
        root_logger.addHandler(handler)
    _configured = True


def log_action(
    logger: logging.Logger,
    level: int,
    message: str,
    *,
    action: str,
    correlation_id: str | None = None,
    user_id: int | None = None,
    family_id: int | None = None,
    details: dict[str, Any] | None = None,
    exc_info: Any = None,
) -> None:
    # Pre-compute sanitized values before passing to logger to ensure no raw
    # user-controlled content (which could contain newlines or other control
    # characters) reaches the log sink.
    escaped_message = message.replace('\n', r'\n').replace('\r', r'\r')
    sanitized_message = _sanitize_log_text(escaped_message)
    escaped_correlation_id = correlation_id.replace('\n', r'\n').replace('\r', r'\r') if isinstance(correlation_id, str) else correlation_id
    sanitized_correlation_id = _coerce_log_value(escaped_correlation_id)
    escaped_action = action.replace('\n', r'\n').replace('\r', r'\r')
    sanitized_action = _sanitize_log_text(escaped_action)
    sanitized_details = _coerce_details(details)
    logger.log(
        level,
        sanitized_message,
        extra={
            'correlation_id': sanitized_correlation_id,
            'user_id': user_id,
            'family_id': family_id,
            'action': sanitized_action,
            'details': sanitized_details,
        },
        exc_info=exc_info,
    )
