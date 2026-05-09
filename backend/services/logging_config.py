from __future__ import annotations

import json
import logging
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
_log_context: ContextVar[dict[str, Any]] = ContextVar('backend_log_context', default=_DEFAULT_CONTEXT.copy())
_configured = False


def _coerce_details(details: Any) -> Any:
    if details is None:
        return None
    if isinstance(details, dict):
        return {str(key): _coerce_details(value) for key, value in details.items()}
    if isinstance(details, (list, tuple, set)):
        return [_coerce_details(value) for value in details]
    if isinstance(details, (str, int, float, bool)):
        return details
    return str(details)


def bind_context(**values: Any) -> Token:
    current = _log_context.get().copy()
    for key, value in values.items():
        if key not in _DEFAULT_CONTEXT:
            continue
        current[key] = _coerce_details(value) if key == 'details' else value
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
        record.correlation_id = getattr(record, 'correlation_id', None) or context['correlation_id']
        record.user_id = getattr(record, 'user_id', None) or context['user_id']
        record.family_id = getattr(record, 'family_id', None) or context['family_id']
        record.action = getattr(record, 'action', None) or context['action']
        details = getattr(record, 'details', None)
        record.details = _coerce_details(context['details'] if details is None else details)
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            'timestamp': datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'correlation_id': getattr(record, 'correlation_id', None),
            'user_id': getattr(record, 'user_id', None),
            'family_id': getattr(record, 'family_id', None),
            'action': getattr(record, 'action', None),
            'details': getattr(record, 'details', None),
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
        return f'{timestamp} {record.levelname:<8} [{correlation_id}] {action} {record.getMessage()}{details_suffix}'


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
    logger.log(
        level,
        message,
        extra={
            'correlation_id': correlation_id,
            'user_id': user_id,
            'family_id': family_id,
            'action': action,
            'details': _coerce_details(details),
        },
        exc_info=exc_info,
    )
