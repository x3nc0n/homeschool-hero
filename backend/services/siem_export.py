"""Optional CEF-over-syslog export of structured security events.

Only records emitted by ``backend.services.security_events`` (``event_category="security"``)
are exported. The default JSON stdout pipeline is unchanged; this handler is attached in
addition to it when ``SIEM_SYSLOG_ENABLED=true``.
"""

from __future__ import annotations

import hashlib
import ipaddress
import json
import logging
import logging.handlers
import os
import re
import socket
import sys
import threading
import time
from datetime import UTC, datetime
from typing import Any

from backend.config import Settings

CEF_VENDOR = 'Homeschool Hero'
CEF_PRODUCT = 'Homeschool Hero API'
SYSLOG_APP_NAME = 'homeschool-hero'
FAILURE_REPORT_INTERVAL_SECONDS = 60.0
RECONNECT_BACKOFF_SECONDS = 30.0

_EVENT_NAMES = {
    'auth_success': 'Authentication succeeded',
    'auth_failure': 'Authentication failed',
    'breakglass_login': 'Break-glass local login',
    'rbac_denial': 'Authorization denied',
    'role_mapping_failure': 'SSO role mapping failed',
    'session_created': 'Session created',
    'session_destroyed': 'Session destroyed',
}
_CEF_SEVERITY = {
    'DEBUG': 1,
    'INFO': 3,
    'WARNING': 6,
    'ERROR': 8,
    'CRITICAL': 10,
}
_TRUNCATABLE_KEYS = {'request', 'requestClientApplication', 'msg'}
_FIELD_MAX_CHARS = 1023
_TRUNCATION_MARKER = ' cs6Label=exportTruncated cs6=true'
_CONTROL_RE = re.compile(r'[\x00-\x1f\x7f]')
_SYSLOG_TOKEN_RE = re.compile(r'[^\x21-\x7e]')
_failure_logger = logging.getLogger('backend.services.siem_export')
_reentry_guard = threading.local()


def _cef_header_escape(value: Any, max_chars: int = 255) -> str:
    text = str(value)[:max_chars]
    text = text.replace('\\', '\\\\').replace('|', '\\|')
    return _CONTROL_RE.sub(' ', text)


def _cef_extension_escape(value: Any) -> str:
    text = str(value)
    text = text.replace('\\', '\\\\').replace('=', '\\=')
    text = text.replace('\r\n', '\\n').replace('\n', '\\n').replace('\r', '\\r')
    return _CONTROL_RE.sub(' ', text)


def _syslog_token(value: Any, max_chars: int) -> str:
    token = _SYSLOG_TOKEN_RE.sub('_', str(value))[:max_chars]
    return token or '-'


def _truncate_escaped(escaped: str, max_bytes: int) -> str:
    if max_bytes <= 0:
        return ''
    truncated = escaped.encode('utf-8')[:max_bytes].decode('utf-8', errors='ignore')
    trailing_backslashes = len(truncated) - len(truncated.rstrip('\\'))
    if trailing_backslashes % 2:
        truncated = truncated[:-1]
    return truncated


def fingerprint_identifier(value: str) -> str:
    return 'sha256:' + hashlib.sha256(value.encode('utf-8')).hexdigest()[:16]


def _event_millis(record: logging.LogRecord) -> int:
    raw_timestamp = getattr(record, 'event_timestamp', None)
    if isinstance(raw_timestamp, str):
        try:
            parsed = datetime.fromisoformat(raw_timestamp)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=UTC)
            return int(parsed.timestamp() * 1000)
        except ValueError:
            pass
    return int(record.created * 1000)


def is_security_record(record: logging.LogRecord) -> bool:
    return getattr(record, 'event_category', None) == 'security' and bool(getattr(record, 'event_type', None))


class SecurityEventFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        return is_security_record(record)


class CefSyslogFormatter(logging.Formatter):
    """Formats a security record as an RFC 5424 syslog body carrying a CEF:0 message.

    The ``<PRI>`` prefix is added by the handler. ``max_bytes`` bounds the UTF-8 size of the
    returned text; lower-priority long fields are truncated or dropped to fit.
    """

    def __init__(self, *, max_bytes: int, device_version: str, hostname: str | None = None) -> None:
        super().__init__()
        self.max_bytes = max_bytes
        self.device_version = device_version
        self.hostname = _syslog_token(hostname or socket.gethostname(), 255)

    def format(self, record: logging.LogRecord) -> str:
        event_type = str(getattr(record, 'event_type', None) or 'unknown')
        millis = _event_millis(record)
        timestamp = datetime.fromtimestamp(millis / 1000, tz=UTC).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'
        syslog_header = (
            f'1 {timestamp} {self.hostname} {SYSLOG_APP_NAME} {os.getpid()} {_syslog_token(event_type, 32)} - '
        )
        severity = _CEF_SEVERITY.get(record.levelname, 5)
        cef_header = '|'.join(
            [
                'CEF:0',
                _cef_header_escape(CEF_VENDOR),
                _cef_header_escape(CEF_PRODUCT),
                _cef_header_escape(self.device_version, 63),
                _cef_header_escape(event_type, 1023),
                _cef_header_escape(_EVENT_NAMES.get(event_type, event_type), 512),
                str(severity),
                '',
            ]
        )
        prefix = syslog_header + cef_header
        groups = self._extension_groups(record, event_type, millis)
        budget = self.max_bytes - len(prefix.encode('utf-8'))
        extension, truncated = self._render_extension(groups, budget)
        if truncated:
            extension, _ = self._render_extension(groups, budget - len(_TRUNCATION_MARKER.encode('utf-8')))
            extension += _TRUNCATION_MARKER
        return prefix + extension

    def _extension_groups(self, record: logging.LogRecord, event_type: str, millis: int) -> list[list[tuple[str, Any]]]:
        actor = getattr(record, 'actor', None) or {}
        target = getattr(record, 'target', None) or {}
        if not isinstance(actor, dict):
            actor = {}
        if not isinstance(target, dict):
            target = {}
        target_id = target.get('id')
        if target_id is not None and target.get('type') == 'session':
            target_id = fingerprint_identifier(str(target_id))

        source_ip = getattr(record, 'source_ip', None)
        if source_ip is not None:
            try:
                source_ip = str(ipaddress.ip_address(str(source_ip)))
            except ValueError:
                source_ip = None

        details = getattr(record, 'details', None)
        details_text = (
            json.dumps(details, sort_keys=True, separators=(',', ':'), ensure_ascii=False, default=str)
            if details
            else None
        )

        candidates: list[list[tuple[str, Any]]] = [
            [('rt', millis)],
            [('cat', getattr(record, 'event_category', None))],
            [('act', event_type)],
            [('outcome', getattr(record, 'result', None))],
            [('src', source_ip)],
            [('suid', actor.get('user_id'))],
            [('suser', actor.get('email'))],
            [('cs3Label', 'correlationId'), ('cs3', getattr(record, 'correlation_id', None))],
            [('cs1Label', 'targetType'), ('cs1', target.get('type'))],
            [('cs2Label', 'targetId'), ('cs2', target_id)],
            [('request', target.get('resource'))],
            [('requestClientApplication', getattr(record, 'user_agent', None))],
            [('msg', details_text)],
        ]
        return [group for group in candidates if group[-1][1] not in (None, '')]

    def _render_extension(self, groups: list[list[tuple[str, Any]]], budget: int) -> tuple[str, bool]:
        parts: list[str] = []
        used = 0
        truncated = False
        for group in groups:
            last_key, last_value = group[-1]
            escaped = _cef_extension_escape(last_value)
            if len(escaped) > _FIELD_MAX_CHARS:
                truncated = True
                if last_key not in _TRUNCATABLE_KEYS:
                    continue
                escaped = _truncate_escaped(escaped[:_FIELD_MAX_CHARS], _FIELD_MAX_CHARS * 4)
            tokens = [f'{key}={_cef_extension_escape(value)}' for key, value in group[:-1]]
            prefix = (' ' if parts else '') + ' '.join([*tokens, f'{last_key}='])
            prefix_size = len(prefix.encode('utf-8'))
            value_size = len(escaped.encode('utf-8'))
            if used + prefix_size + value_size <= budget:
                parts.append(prefix + escaped)
                used += prefix_size + value_size
                continue
            truncated = True
            room = budget - used - prefix_size
            if last_key in _TRUNCATABLE_KEYS and room >= 16:
                value_text = _truncate_escaped(escaped, room)
                parts.append(prefix + value_text)
                used += prefix_size + len(value_text.encode('utf-8'))
        return ''.join(parts), truncated


class SecuritySyslogHandler(logging.handlers.SysLogHandler):
    """Bounded syslog transport for security events (UDP datagrams or LF-framed TCP).

    Delivery failures are never raised into request handling; they are counted and reported
    (rate-limited) through the normal application log stream, which this handler ignores.
    """

    append_nul = False

    def __init__(
        self,
        *,
        host: str,
        port: int,
        protocol: str,
        facility: str,
        max_message_bytes: int,
        timeout_seconds: float,
    ) -> None:
        # SysLogHandler.__init__ is intentionally not called: it connects eagerly and raises on an
        # unavailable receiver. Connection is attempted here and retried on emit after a backoff.
        logging.Handler.__init__(self)
        self.address = (host, port)
        self.facility = self.facility_names[facility]
        self.socktype = socket.SOCK_STREAM if protocol == 'tcp' else socket.SOCK_DGRAM
        self.socket = None
        self.unixsocket = False
        self.protocol = protocol
        self.max_message_bytes = max_message_bytes
        self.timeout_seconds = timeout_seconds
        self.sent_count = 0
        self.failure_count = 0
        self._last_failure_report = 0.0
        self._unreported_failures = 0
        self.startup_error: OSError | None = None
        self._reconnect_after = 0.0
        self.addFilter(SecurityEventFilter())
        try:
            self.createSocket()
        except OSError as exc:
            self.startup_error = exc
            self._reconnect_after = time.monotonic() + RECONNECT_BACKOFF_SECONDS

    def createSocket(self) -> None:  # noqa: N802 - stdlib hook name
        host, port = self.address
        try:
            if self.socktype == socket.SOCK_STREAM:
                sock = socket.create_connection((host, port), timeout=self.timeout_seconds)
            else:
                family, socktype, proto, _, sockaddr = socket.getaddrinfo(host, port, 0, socket.SOCK_DGRAM)[0]
                sock = socket.socket(family, socktype, proto)
                sock.settimeout(self.timeout_seconds)
                self.address = sockaddr[:2]
        except OSError:
            self.socket = None
            raise
        self.socket = sock
        self.unixsocket = False

    def emit(self, record: logging.LogRecord) -> None:
        if getattr(_reentry_guard, 'active', False):
            return
        _reentry_guard.active = True
        try:
            body = self.format(record)
            priority = self.encodePriority(self.facility, self.mapPriority(record.levelname))
            payload = f'<{priority}>'.encode('ascii') + body.encode('utf-8')
            if self.protocol == 'tcp':
                payload += b'\n'
            if len(payload) > self.max_message_bytes:
                raise ValueError('formatted syslog message exceeded configured size bound')
            if self.socket is None:
                # Avoid blocking every request on connect timeouts while the collector is down.
                if time.monotonic() < self._reconnect_after:
                    raise ConnectionError('SIEM syslog destination unavailable; reconnect backoff in effect')
                try:
                    self.createSocket()
                except OSError:
                    self._reconnect_after = time.monotonic() + RECONNECT_BACKOFF_SECONDS
                    raise
            if self.socktype == socket.SOCK_DGRAM:
                self.socket.sendto(payload, self.address)
            else:
                try:
                    self.socket.sendall(payload)
                except OSError:
                    self._reconnect_after = time.monotonic() + RECONNECT_BACKOFF_SECONDS
                    raise
            self.sent_count += 1
        except Exception as exc:  # noqa: BLE001 - transport errors must not break requests
            self._drop_socket()
            self._report_failure(exc, record)
        finally:
            _reentry_guard.active = False

    def _drop_socket(self) -> None:
        if self.socktype == socket.SOCK_STREAM and self.socket is not None:
            try:
                self.socket.close()
            except OSError:
                pass
            self.socket = None

    def _report_failure(self, exc: BaseException, record: logging.LogRecord) -> None:
        self.failure_count += 1
        self._unreported_failures += 1
        now = time.monotonic()
        if self._last_failure_report and now - self._last_failure_report < FAILURE_REPORT_INTERVAL_SECONDS:
            return
        dropped = self._unreported_failures
        self._unreported_failures = 0
        self._last_failure_report = now
        try:
            _failure_logger.error(
                'SIEM syslog export failed; security events were dropped from the syslog destination',
                extra={
                    'action': 'siem_export_failure',
                    'details': {
                        'protocol': self.protocol,
                        'destination': f'{self.address[0]}:{self.address[1]}',
                        'error_type': type(exc).__name__,
                        'error': str(exc)[:200],
                        'dropped_events': dropped,
                        'event_type': getattr(record, 'event_type', None),
                    },
                },
            )
        except Exception:  # noqa: BLE001
            sys.stderr.write(f'SIEM syslog export failed: {type(exc).__name__}\n')


def build_siem_syslog_handler(config: Settings) -> SecuritySyslogHandler | None:
    if not config.siem_syslog_enabled:
        return None
    if not config.siem_syslog_host:
        raise ValueError('SIEM_SYSLOG_HOST is required when SIEM_SYSLOG_ENABLED=true.')
    from backend.openapi import API_VERSION

    handler = SecuritySyslogHandler(
        host=config.siem_syslog_host,
        port=config.siem_syslog_port,
        protocol=config.siem_syslog_protocol,
        facility=config.siem_syslog_facility,
        max_message_bytes=config.siem_syslog_max_message_bytes,
        timeout_seconds=config.siem_syslog_timeout_seconds,
    )
    handler.setFormatter(
        CefSyslogFormatter(
            # Reserve room for the "<PRI>" prefix (max 5 bytes) and TCP LF framing.
            max_bytes=config.siem_syslog_max_message_bytes - 6,
            device_version=API_VERSION,
        )
    )
    return handler


def report_startup_error(handler: SecuritySyslogHandler) -> None:
    if handler.startup_error is None:
        return
    _failure_logger.error(
        'SIEM syslog destination unavailable at startup; export will retry after the reconnect backoff',
        extra={
            'action': 'siem_export_failure',
            'details': {
                'protocol': handler.protocol,
                'destination': f'{handler.address[0]}:{handler.address[1]}',
                'error_type': type(handler.startup_error).__name__,
                'error': str(handler.startup_error)[:200],
            },
        },
    )
