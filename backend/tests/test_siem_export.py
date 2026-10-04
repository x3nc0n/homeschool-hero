from __future__ import annotations

import logging
import re
import socket
import threading
from unittest.mock import Mock

import pytest
from pydantic import ValidationError

from backend.config import Settings
from backend.services import logging_config
from backend.services.siem_export import (
    RECONNECT_BACKOFF_SECONDS,
    CefSyslogFormatter,
    SecuritySyslogHandler,
    build_siem_syslog_handler,
    fingerprint_identifier,
)
from tests.contracts import AUTH, bootstrap_payload

_EXTENSION_RE = re.compile(r'(\w+)=((?:\\.|[^\\])*?)(?= \w+=|$)')
_RFC5424_RE = re.compile(
    r'^<(?P<pri>\d{1,3})>1 (?P<ts>\S+) (?P<host>\S+) (?P<app>\S+) (?P<procid>\S+) (?P<msgid>\S+) - (?P<cef>CEF:0\|.*)$',
    re.DOTALL,
)


def _siem_settings(**overrides) -> Settings:
    values = {
        'SIEM_SYSLOG_ENABLED': True,
        'SIEM_SYSLOG_HOST': '127.0.0.1',
        'SIEM_SYSLOG_PORT': 514,
        'SIEM_SYSLOG_TIMEOUT_SECONDS': 2,
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def _unescape(value: str) -> str:
    out: list[str] = []
    index = 0
    while index < len(value):
        char = value[index]
        if char == '\\' and index + 1 < len(value):
            nxt = value[index + 1]
            out.append({'n': '\n', 'r': '\r'}.get(nxt, nxt))
            index += 2
            continue
        out.append(char)
        index += 1
    return ''.join(out)


def _split_cef_header(cef: str) -> tuple[list[str], str]:
    fields: list[str] = []
    current: list[str] = []
    index = 0
    while len(fields) < 7:
        char = cef[index]
        if char == '\\':
            current.append(cef[index + 1])
            index += 2
            continue
        if char == '|':
            fields.append(''.join(current))
            current = []
        else:
            current.append(char)
        index += 1
    return fields, cef[index:]


def _parse_syslog(payload: bytes) -> dict:
    text = payload.decode('utf-8')
    match = _RFC5424_RE.match(text)
    assert match, text
    header, extension = _split_cef_header(match.group('cef'))
    return {
        'pri': int(match.group('pri')),
        'msgid': match.group('msgid'),
        'app': match.group('app'),
        'header': header,
        'extension_raw': extension,
        'extension': {key: _unescape(value) for key, value in _EXTENSION_RE.findall(extension)},
    }


def _security_record(**attrs) -> logging.LogRecord:
    record = logging.LogRecord('test', logging.WARNING, __file__, 1, 'Security event', None, None)
    record.event_category = 'security'
    record.event_type = 'auth_failure'
    record.event_timestamp = '2026-10-04T16:00:00.123456+00:00'
    record.actor = {'email': 'owner@example.com', 'user_id': 7}
    record.target = {'resource': '/api/auth/login', 'type': 'auth_endpoint'}
    record.result = 'failure'
    record.source_ip = '127.0.0.1'
    record.user_agent = 'pytest'
    record.correlation_id = 'corr-1'
    record.details = {'reason': 'bad_password'}
    for key, value in attrs.items():
        setattr(record, key, value)
    return record


@pytest.fixture
def udp_receiver():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(('127.0.0.1', 0))
    sock.settimeout(5)
    try:
        yield sock
    finally:
        sock.close()


@pytest.fixture
def tcp_receiver():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(('127.0.0.1', 0))
    server.listen(1)
    server.settimeout(5)
    try:
        yield server
    finally:
        server.close()


@pytest.fixture
def attach_handler():
    attached: list[SecuritySyslogHandler] = []
    root = logging.getLogger()

    def _attach(handler: SecuritySyslogHandler) -> SecuritySyslogHandler:
        handler.addFilter(logging_config.RequestContextFilter())
        root.addHandler(handler)
        attached.append(handler)
        return handler

    yield _attach
    for handler in attached:
        root.removeHandler(handler)
        handler.close()


def _drain_udp(sock: socket.socket) -> list[bytes]:
    packets = []
    sock.settimeout(5)
    packets.append(sock.recvfrom(65535)[0])
    sock.settimeout(0.3)
    while True:
        try:
            packets.append(sock.recvfrom(65535)[0])
        except TimeoutError:
            return packets


def test_siem_syslog_is_disabled_by_default() -> None:
    config = Settings(_env_file=None)
    assert config.siem_syslog_enabled is False
    assert build_siem_syslog_handler(config) is None


@pytest.mark.parametrize(
    ('overrides', 'message'),
    [
        ({'SIEM_SYSLOG_HOST': None}, 'SIEM_SYSLOG_HOST is required'),
        ({'SIEM_SYSLOG_HOST': '  '}, 'SIEM_SYSLOG_HOST is required'),
        ({'SIEM_SYSLOG_HOST': 'udp://collector'}, 'without scheme'),
        ({'SIEM_SYSLOG_HOST': 'user@collector'}, 'without scheme'),
        ({'SIEM_SYSLOG_PROTOCOL': 'tls'}, 'SIEM_SYSLOG_PROTOCOL'),
        ({'SIEM_SYSLOG_FACILITY': 'nonsense'}, 'SIEM_SYSLOG_FACILITY must be one of'),
        ({'SIEM_SYSLOG_PORT': 0}, 'SIEM_SYSLOG_PORT'),
        ({'SIEM_SYSLOG_MAX_MESSAGE_BYTES': 100}, 'SIEM_SYSLOG_MAX_MESSAGE_BYTES'),
        ({'SIEM_SYSLOG_TIMEOUT_SECONDS': 0}, 'SIEM_SYSLOG_TIMEOUT_SECONDS'),
    ],
)
def test_siem_syslog_settings_are_validated(overrides, message) -> None:
    with pytest.raises(ValidationError, match=message):
        _siem_settings(**overrides)


def test_siem_syslog_settings_normalize_case() -> None:
    config = _siem_settings(SIEM_SYSLOG_PROTOCOL=' TCP ', SIEM_SYSLOG_FACILITY='AuthPriv')
    assert config.siem_syslog_protocol == 'tcp'
    assert config.siem_syslog_facility == 'authpriv'


def test_cef_formatter_escapes_header_and_extension_values() -> None:
    record = _security_record(
        event_type='custom|type\\x',
        actor={'email': 'a=b\\c|d@example.com'},
        user_agent='line1\nline2\rline3\x00end',
        details={'reason': 'k=v'},
    )
    output = CefSyslogFormatter(max_bytes=4000, device_version='1|2', hostname='host name').format(record)

    assert '\n' not in output and '\r' not in output and '\x00' not in output
    assert ' host_name homeschool-hero ' in output
    assert 'CEF:0|Homeschool Hero|Homeschool Hero API|1\\|2|custom\\|type\\\\x|' in output
    assert 'suser=a\\=b\\\\c|d@example.com' in output
    assert 'requestClientApplication=line1\\nline2\\rline3 end' in output
    parsed = _parse_syslog(b'<134>' + output.encode())
    assert parsed['header'][4] == 'custom|type\\x'
    assert parsed['extension']['suser'] == 'a=b\\c|d@example.com'
    assert parsed['extension']['msg'] == '{"reason":"k=v"}'


def test_cef_formatter_fingerprints_session_ids_and_drops_invalid_ip() -> None:
    raw_sid = 'raw-session-identifier-value'
    record = _security_record(
        event_type='session_created',
        target={'resource': 'session', 'id': raw_sid, 'type': 'session'},
        source_ip='not-an-ip',
    )
    output = CefSyslogFormatter(max_bytes=4000, device_version='0.1.0', hostname='h').format(record)

    assert raw_sid not in output
    parsed = _parse_syslog(b'<134>' + output.encode())
    assert parsed['extension']['cs2'] == fingerprint_identifier(raw_sid)
    assert 'src' not in parsed['extension']


def test_cef_formatter_bounds_message_size_and_marks_truncation() -> None:
    record = _security_record(user_agent='U\\' * 4000, details={'blob': 'é' * 4000})
    output = CefSyslogFormatter(max_bytes=600, device_version='0.1.0', hostname='h').format(record)

    assert len(output.encode('utf-8')) <= 600
    parsed = _parse_syslog(b'<134>' + output.encode())
    assert parsed['extension']['act'] == 'auth_failure'
    assert parsed['extension']['suser'] == 'owner@example.com'
    assert parsed['extension']['cs6Label'] == 'exportTruncated'
    assert parsed['extension']['cs6'] == 'true'


def test_handler_ignores_non_security_records(udp_receiver) -> None:
    port = udp_receiver.getsockname()[1]
    handler = build_siem_syslog_handler(_siem_settings(SIEM_SYSLOG_PORT=port))
    try:
        logger = logging.getLogger('test.siem.nonsecurity')
        logger.addHandler(handler)
        logger.propagate = False
        logger.warning('ordinary application log with password=hunter2')
        udp_receiver.settimeout(0.3)
        with pytest.raises(TimeoutError):
            udp_receiver.recvfrom(65535)
        assert handler.sent_count == 0
    finally:
        logger.removeHandler(handler)
        logger.propagate = True
        handler.close()


@pytest.mark.asyncio
async def test_failed_login_is_exported_as_cef_over_udp(
    authorized_client, secondary_client, udp_receiver, attach_handler, caplog
) -> None:
    port = udp_receiver.getsockname()[1]
    handler = attach_handler(build_siem_syslog_handler(_siem_settings(SIEM_SYSLOG_PORT=port)))
    caplog.set_level(logging.INFO)
    wrong_password = 'definitely-wrong-password'

    response = await secondary_client.post(
        AUTH['login'],
        json={'email': 'owner@example.com', 'password': wrong_password},
        headers={'User-Agent': 'siem-test|agent=1'},
    )

    assert response.status_code == 401, response.text
    packets = _drain_udp(udp_receiver)
    assert handler.failure_count == 0
    assert all(wrong_password.encode() not in packet for packet in packets)
    events = [_parse_syslog(packet) for packet in packets]
    failure = next(event for event in events if event['extension'].get('act') == 'auth_failure')
    assert failure['pri'] == (20 << 3) | 4  # local4.warning
    assert failure['app'] == 'homeschool-hero'
    assert failure['msgid'] == 'auth_failure'
    assert failure['header'][:6] == [
        'CEF:0', 'Homeschool Hero', 'Homeschool Hero API', failure['header'][3], 'auth_failure', 'Authentication failed'
    ]
    assert failure['header'][6] == '6'
    ext = failure['extension']
    assert ext['cat'] == 'security'
    assert ext['outcome'] == 'failure'
    assert ext['suser'] == 'owner@example.com'
    assert ext['request'] == '/api/auth/login'
    assert ext['requestClientApplication'] == 'siem-test|agent=1'
    assert '"reason":"bad_password"' in ext['msg']
    json_record = next(r for r in caplog.records if getattr(r, 'event_type', None) == 'auth_failure')
    assert ext['cs3'] == json_record.correlation_id


@pytest.mark.asyncio
async def test_successful_login_is_exported_over_tcp_without_raw_session_id(
    authorized_client, secondary_client, tcp_receiver, attach_handler, caplog
) -> None:
    port = tcp_receiver.getsockname()[1]
    handler = attach_handler(
        build_siem_syslog_handler(
            _siem_settings(SIEM_SYSLOG_PORT=port, SIEM_SYSLOG_PROTOCOL='tcp', SIEM_SYSLOG_FACILITY='authpriv')
        )
    )
    assert handler.startup_error is None
    connection, _ = tcp_receiver.accept()
    connection.settimeout(5)
    caplog.set_level(logging.INFO)
    password = bootstrap_payload()['password']

    response = await secondary_client.post(AUTH['login'], json={'email': 'owner@example.com', 'password': password})

    assert response.status_code == 200, response.text
    buffer = b''
    try:
        while buffer.count(b'\n') < 2:
            chunk = connection.recv(65535)
            if not chunk:
                break
            buffer += chunk
    finally:
        connection.close()
    lines = [line for line in buffer.split(b'\n') if line]
    assert password.encode() not in buffer
    events = {event['extension']['act']: event for event in map(_parse_syslog, lines)}
    assert {'auth_success', 'session_created'} <= set(events)
    assert events['auth_success']['pri'] == (10 << 3) | 6  # authpriv.info
    session_record = next(r for r in caplog.records if getattr(r, 'event_type', None) == 'session_created')
    raw_sid = session_record.target['id']
    assert raw_sid and raw_sid.encode() not in buffer
    assert events['session_created']['extension']['cs2'] == fingerprint_identifier(raw_sid)
    assert handler.sent_count >= 2


def test_unreachable_tcp_destination_is_reported_not_raised(caplog, monkeypatch) -> None:
    probe = socket.socket()
    probe.bind(('127.0.0.1', 0))
    closed_port = probe.getsockname()[1]
    probe.close()
    handler = build_siem_syslog_handler(
        _siem_settings(SIEM_SYSLOG_PORT=closed_port, SIEM_SYSLOG_PROTOCOL='tcp', SIEM_SYSLOG_TIMEOUT_SECONDS=1)
    )
    assert isinstance(handler.startup_error, OSError)
    caplog.set_level(logging.ERROR, logger='backend.services.siem_export')
    connect_attempts = []
    monkeypatch.setattr(handler, 'createSocket', lambda: connect_attempts.append(1))
    try:
        handler.handle(_security_record())
        handler.handle(_security_record())
    finally:
        handler.close()

    assert connect_attempts == []  # reconnect backoff avoids blocking requests on connect timeouts

    assert handler.failure_count == 2
    assert handler.sent_count == 0
    failures = [r for r in caplog.records if getattr(r, 'action', None) == 'siem_export_failure']
    assert len(failures) == 1  # rate limited
    assert failures[0].details['destination'] == f'127.0.0.1:{closed_port}'
    assert failures[0].details['dropped_events'] == 1


def test_failed_tcp_send_waits_for_backoff_before_reconnecting(tcp_receiver, monkeypatch) -> None:
    now = 100.0
    monkeypatch.setattr('backend.services.siem_export.time.monotonic', lambda: now)
    failed_socket = Mock(spec=socket.socket)
    failed_socket.sendall.side_effect = ConnectionResetError('collector dropped connection')
    create_connection = socket.create_connection
    connect = Mock()

    def _connect(*args, **kwargs):
        connect(*args, **kwargs)
        if connect.call_count == 1:
            return failed_socket
        return create_connection(*args, **kwargs)

    monkeypatch.setattr(socket, 'create_connection', _connect)
    handler = build_siem_syslog_handler(
        _siem_settings(SIEM_SYSLOG_PORT=tcp_receiver.getsockname()[1], SIEM_SYSLOG_PROTOCOL='tcp')
    )
    try:
        handler.handle(_security_record())
        failed_socket.close.assert_called_once()
        assert handler.socket is None
        assert handler._reconnect_after == now + RECONNECT_BACKOFF_SECONDS

        handler.handle(_security_record())
        now += RECONNECT_BACKOFF_SECONDS - 1
        handler.handle(_security_record())
        assert connect.call_count == 1
        assert handler.failure_count == 3
        assert handler.sent_count == 0
        assert handler._reconnect_after == 100.0 + RECONNECT_BACKOFF_SECONDS

        now += 2
        handler.handle(_security_record(correlation_id='after-send-recovery'))
        assert connect.call_count == 2
        assert handler.sent_count == 1
        connection, _ = tcp_receiver.accept()
        with connection:
            connection.settimeout(5)
            payload = connection.recv(65535)
        assert payload.endswith(b'\n')
        assert _parse_syslog(payload.rstrip(b'\n'))['extension']['cs3'] == 'after-send-recovery'
        recovered_socket = handler.socket
    finally:
        handler.close()

    assert handler.socket is None
    assert recovered_socket.fileno() == -1


def test_configure_logging_attaches_handler_only_when_enabled(udp_receiver, monkeypatch, caplog) -> None:
    root = logging.getLogger()
    before = list(root.handlers)
    monkeypatch.setattr(logging_config, '_configured', False)
    logging_config.configure_logging(Settings(_env_file=None, TESTING=True))
    assert [h for h in root.handlers if isinstance(h, SecuritySyslogHandler)] == []

    monkeypatch.setattr(logging_config, '_configured', False)
    port = udp_receiver.getsockname()[1]
    logging_config.configure_logging(_siem_settings(SIEM_SYSLOG_PORT=port, TESTING=True))
    added = [h for h in root.handlers if h not in before]
    try:
        assert len(added) == 1 and isinstance(added[0], SecuritySyslogHandler)
        from backend.services.security_events import AuthFailureEvent, SecurityActor, emit_security_event

        emit_security_event(logging.getLogger('test.siem.configure'), AuthFailureEvent(actor=SecurityActor(email='x@y.z')))
        event = _parse_syslog(udp_receiver.recvfrom(65535)[0])
        assert event['extension']['suser'] == 'x@y.z'
    finally:
        for handler in added:
            root.removeHandler(handler)
            handler.close()


def test_tcp_export_recovers_when_collector_becomes_available() -> None:
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(('127.0.0.1', 0))
    port = server.getsockname()[1]
    server.close()
    handler = build_siem_syslog_handler(
        _siem_settings(SIEM_SYSLOG_PORT=port, SIEM_SYSLOG_PROTOCOL='tcp', SIEM_SYSLOG_TIMEOUT_SECONDS=1)
    )
    assert handler.startup_error is not None
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(('127.0.0.1', port))
    server.listen(1)
    server.settimeout(5)
    try:
        handler._reconnect_after = 0.0  # simulate the backoff window elapsing
        handler.handle(_security_record(correlation_id='after-recovery'))
        connection, _ = server.accept()
        with connection:
            connection.settimeout(5)
            payload = connection.recv(65535)
    finally:
        handler.close()
        server.close()

    assert payload.endswith(b'\n')
    assert _parse_syslog(payload.rstrip(b'\n'))['extension']['cs3'] == 'after-recovery'
    assert handler.sent_count == 1
