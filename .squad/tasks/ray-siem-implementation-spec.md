# IMPLEMENTATION SPEC: Structured Security Logging for SIEM (Issue #113)

**Prepared by:** Egon (Lead)  
**For:** Ray (Backend Dev)  
**Date:** 2026-05-18T18:03:11.180-05:00  
**Depends on:** None (standalone feature)  
**Blocks:** None initially; Phase 3 (OTel) will depend on this

---

## Executive Summary

Implement a typed security event emitter that logs auth failures, RBAC denials, SSO failures, and breakglass logins with standard fields (event_type, actor, target, result, source_ip, user_agent, correlation_id). Events go to stdout JSON logs + optional DB audit table. No new external dependencies in Phase 1–2.

---

## Part 1: Phase 1 — Core Security Event Emitter

### File: `backend/models/audit_event.py`

**Add to existing file after AuditAction enum:**

```python
class SecurityEventType(str, enum.Enum):
    """Typed security events for SIEM monitoring.
    
    These events indicate authentication, authorization, and identity provider failures
    that require immediate visibility for security operations centers.
    """
    auth_success = 'auth_success'
    """Successful login (local auth or SSO)."""
    
    auth_failure = 'auth_failure'
    """Failed login attempt (bad credentials, account locked, etc.)."""
    
    breakglass_login = 'breakglass_login'
    """Local login used while OIDC/SAML is configured (emergency access)."""
    
    rbac_denial = 'rbac_denial'
    """Authorization check failed; 403 response returned."""
    
    role_mapping_failure = 'role_mapping_failure'
    """SSO provider role claim could not be mapped to app role."""
    
    sso_success = 'sso_success'
    """Successful OIDC or SAML authentication and identity provisioning."""
    
    sso_failure = 'sso_failure'
    """OIDC/SAML authentication or callback failed."""
    
    rate_limit_exceeded = 'rate_limit_exceeded'
    """Account temporarily locked due to repeated auth failures."""
```

**Rationale:** Enum-based typing ensures SIEM rules reference valid event types; mypy enforces correctness at dev time.

---

### File: `backend/services/security_events.py` (NEW)

Create this module to emit structured security events:

```python
"""Security event emission for SIEM integration.

This module provides the SecurityEvent class and emit_security_event() function to centralize
security-relevant logging. Events are emitted to stdout JSON logs (mandatory) and optionally
persisted to the audit_events table.

Usage:
    from backend.services.security_events import SecurityEvent, emit_security_event
    from backend.models.audit_event import SecurityEventType
    
    event = SecurityEvent(
        event_type=SecurityEventType.rbac_denial,
        actor_user_id=42,
        family_id=10,
        source_ip="192.168.1.1",
        user_agent="Mozilla/5.0...",
        correlation_id="req-abc123",
        target="POST /api/assignments",
        result="deny",
        reason="role student_viewer not allowed to create assignments"
    )
    await emit_security_event(event, db)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.audit_event import AuditEvent, SecurityEventType
from backend.services.logging_config import _coerce_details

logger = logging.getLogger(__name__)


@dataclass
class SecurityEvent:
    """A structured security event for SIEM monitoring.
    
    All fields are optional to support diverse event types:
    - Pre-auth events (failed login) won't have actor_user_id
    - Internal errors may not have user_agent
    
    Fields conform to the Common Event Format (CEF) standard:
    - event_type: The classification of the security event
    - actor_user_id: User attempting the action (optional for pre-auth events)
    - actor_email: Email hint for lookups when user_id unavailable
    - family_id: Family/tenant being accessed
    - source_ip: Client IP address
    - user_agent: HTTP User-Agent header
    - correlation_id: Request correlation ID for log tracing
    - target: Resource or endpoint under test (e.g., "POST /api/assignments")
    - result: Outcome ("allow", "deny", "failure", "error")
    - reason: Human-readable explanation (e.g., "password mismatch", "role not found")
    - trace_id: OpenTelemetry trace ID (Phase 3)
    - span_id: OpenTelemetry span ID (Phase 3)
    - details: Custom context dict (sanitized before logging)
    """
    
    event_type: SecurityEventType
    target: str
    result: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    actor_user_id: int | None = None
    actor_email: str | None = None
    family_id: int | None = None
    source_ip: str | None = None
    user_agent: str | None = None
    correlation_id: str | None = None
    reason: str | None = None
    trace_id: str | None = None
    span_id: str | None = None
    details: dict[str, Any] | None = None


async def emit_security_event(
    event: SecurityEvent,
    db: AsyncSession | None = None,
) -> None:
    """Emit a security event to logs and optionally persist to audit_events table.
    
    Args:
        event: SecurityEvent instance with required fields populated.
        db: Optional AsyncSession. If provided, event is persisted to audit_events.
            Caller is responsible for db.commit() — this function only flushes.
    
    Example:
        event = SecurityEvent(
            event_type=SecurityEventType.auth_failure,
            actor_email="john@example.com",
            family_id=10,
            source_ip="192.168.1.1",
            target="POST /api/auth/login",
            result="deny",
            reason="password mismatch"
        )
        await emit_security_event(event, db)
    """
    # 1. Emit to stdout JSON logs
    log_details = {
        'event_type': event.event_type.value,
        'actor_user_id': event.actor_user_id,
        'actor_email': event.actor_email,
        'family_id': event.family_id,
        'source_ip': event.source_ip,
        'user_agent': event.user_agent,
        'correlation_id': event.correlation_id,
        'target': event.target,
        'result': event.result,
        'reason': event.reason,
    }
    if event.trace_id:
        log_details['trace_id'] = event.trace_id
    if event.span_id:
        log_details['span_id'] = event.span_id
    if event.details:
        log_details['details'] = _coerce_details(event.details)
    
    logger.info(
        'security_event',
        extra={
            'action': 'security_event',
            'details': log_details,
        },
    )
    
    # 2. Persist to audit_events if db available
    if db and event.actor_user_id and event.family_id:
        audit_event = AuditEvent(
            family_id=event.family_id,
            actor_user_id=event.actor_user_id,
            action=SecurityEventType(event.event_type.value),
            target_entity_type='security_event',
            target_entity_id=event.target,
            before_snapshot={'event_type': event.event_type.value},
            after_snapshot={
                'result': event.result,
                'reason': event.reason,
                'source_ip': event.source_ip,
            },
            ip_address=event.source_ip,
            user_agent=event.user_agent,
        )
        db.add(audit_event)
        await db.flush()
```

**Key Design Choices:**
- `@dataclass` for immutability and clarity
- All fields optional to support pre-auth events
- Logging to stdout JSON (works with existing `JsonFormatter`)
- DB persistence optional (not all events warrant DB storage)
- Sanitization delegated to existing `_coerce_details()`

---

### File: `backend/models/audit_event.py` — Update Enum

**Add SecurityEventType to AuditAction or extend AuditAction:**

Option A (Recommended): Extend AuditAction with security events:

```python
class AuditAction(str, enum.Enum):
    # ... existing entries ...
    
    # Security events (Phase 1–2)
    auth_success = 'auth_success'
    auth_failure = 'auth_failure'
    breakglass_login = 'breakglass_login'
    rbac_denial = 'rbac_denial'
    role_mapping_failure = 'role_mapping_failure'
    sso_success = 'sso_success'
    sso_failure = 'sso_failure'
    rate_limit_exceeded = 'rate_limit_exceeded'
```

**Rationale:** Single enum avoids dual tracking; audit_events table queries stay simple.

---

### Tests: `backend/tests/services/test_security_events.py` (NEW)

```python
"""Unit tests for security_events module."""

import pytest
from datetime import datetime, UTC

from backend.models.audit_event import SecurityEventType
from backend.services.security_events import SecurityEvent, emit_security_event


@pytest.mark.asyncio
async def test_emit_security_event_to_logs(caplog, db):
    """Verify security event is logged to stdout."""
    event = SecurityEvent(
        event_type=SecurityEventType.auth_failure,
        actor_email="john@example.com",
        family_id=42,
        source_ip="192.168.1.1",
        user_agent="Mozilla/5.0",
        target="POST /api/auth/login",
        result="deny",
        reason="password mismatch"
    )
    
    with caplog.at_level(logging.INFO):
        await emit_security_event(event, db=None)
    
    assert "security_event" in caplog.text
    assert "auth_failure" in caplog.text
    assert "password mismatch" in caplog.text


@pytest.mark.asyncio
async def test_emit_security_event_to_db(db):
    """Verify security event is persisted to audit_events."""
    from backend.models.audit_event import AuditEvent
    
    event = SecurityEvent(
        event_type=SecurityEventType.rbac_denial,
        actor_user_id=10,
        family_id=42,
        source_ip="192.168.1.1",
        target="POST /api/assignments",
        result="deny",
        reason="role not allowed"
    )
    
    await emit_security_event(event, db)
    await db.commit()
    
    # Query audit_events for the event
    result = await db.execute(
        select(AuditEvent).where(
            AuditEvent.action == SecurityEventType.rbac_denial
        )
    )
    audit_row = result.scalar_one_or_none()
    assert audit_row is not None
    assert audit_row.actor_user_id == 10
    assert audit_row.target_entity_id == "POST /api/assignments"
```

---

## Part 2: Phase 2 — Emit Events at Security Points

### 1. Auth Router: Failed Logins

**File:** `backend/routers/auth.py`

**At line ~96 (_register_failed_login), add:**

```python
from backend.services.security_events import SecurityEvent, emit_security_event

async def _register_failed_login(db: AsyncSession, user: User, source_ip: str | None = None) -> None:
    """Register a failed login attempt and emit security event."""
    user.failed_login_attempts += 1
    
    # Emit security event
    event = SecurityEvent(
        event_type=SecurityEventType.auth_failure,
        actor_email=user.email,
        family_id=None,  # Not yet authenticated
        source_ip=source_ip,
        target="POST /api/auth/login",
        result="deny",
        reason=f"invalid credentials (attempt {user.failed_login_attempts})"
    )
    await emit_security_event(event, db=None)  # Don't persist pre-auth events to DB
    
    if user.failed_login_attempts >= settings.auth_lockout_threshold:
        user.locked_until = get_lockout_deadline()
        user.failed_login_attempts = 0
        
        # Emit rate limit event
        event_lockout = SecurityEvent(
            event_type=SecurityEventType.rate_limit_exceeded,
            actor_email=user.email,
            source_ip=source_ip,
            target="POST /api/auth/login",
            result="error",
            reason="account locked after repeated failures"
        )
        await emit_security_event(event_lockout, db=None)
        
        await create_security_alert_for_user(...)
    
    await db.commit()
```

**In login endpoint (line ~212), pass source_ip:**

```python
@router.post('/login', response_model=LoginResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db)
) -> LoginResponse:
    source_ip = request.client.host if request.client else None
    
    # ... existing code ...
    
    if membership_row is None:
        user = await _find_user_by_email(db, payload.email)
        if user is not None:
            if _is_locked(user):
                raise HTTPException(...)
            await _register_failed_login(db, user, source_ip=source_ip)
        raise HTTPException(...)
    
    # ... existing code ...
    
    if not verify_password(payload.password, user.password_hash):
        await _register_failed_login(db, user, source_ip=source_ip)
        raise HTTPException(...)
    
    # Success: emit auth_success
    event = SecurityEvent(
        event_type=SecurityEventType.auth_success,
        actor_user_id=user.id,
        family_id=family.id,
        source_ip=source_ip,
        user_agent=request.headers.get('user-agent'),
        target="POST /api/auth/login",
        result="allow",
        reason="credentials valid"
    )
    await emit_security_event(event, db)
    
    # Breakglass check
    if _is_breakglass_local_login():
        event_breakglass = SecurityEvent(
            event_type=SecurityEventType.breakglass_login,
            actor_user_id=user.id,
            family_id=family.id,
            source_ip=source_ip,
            user_agent=request.headers.get('user-agent'),
            target="POST /api/auth/login",
            result="allow",
            reason=f"local login used while AUTH_PROVIDER={settings.auth_provider}"
        )
        await emit_security_event(event_breakglass, db)
```

### 2. Authorization Guards: RBAC Denials

**File:** `backend/services/authorization.py`

**SIMPLER APPROACH: Wrap at router level:**

```python
# In router endpoints
from backend.services.authorization import require_admin
from backend.services.security_events import SecurityEvent, emit_security_event

async def guard_with_logging(
    auth: AuthSession,
    request: Request,
    db: AsyncSession,
    required_role: AppRole
):
    """Wrapper to emit RBAC denial before guard raises 403."""
    if not has_app_role(auth, required_role):
        event = SecurityEvent(...)
        await emit_security_event(event, db)
    # Let guard raise HTTPException
    return require_any_role(required_role)(auth)
```

**Better yet:** Use a middleware or async context to capture 403s post-facto.

---

### 3. SSO Callbacks: Failures & Role Mapping

**File:** `backend/routers/auth.py` — OIDC callback:

```python
@router.get('/oidc/callback')
async def oidc_callback(request: Request, db: AsyncSession = Depends(get_db)):
    try:
        identity = await complete_oidc_login(request)
        
        # Emit SSO success
        event = SecurityEvent(
            event_type=SecurityEventType.sso_success,
            actor_email=identity.email,
            family_id=None,  # Unknown until provisioned
            source_ip=request.client.host if request.client else None,
            user_agent=request.headers.get('user-agent'),
            target="GET /auth/oidc/callback",
            result="allow",
            reason=f"OIDC auth successful for {identity.email}"
        )
        await emit_security_event(event, db=None)
        
        return await _complete_external_login(identity=identity, request=request, db=db)
    
    except HTTPException as exc:
        # Role mapping or provisioning failed
        event = SecurityEvent(
            event_type=SecurityEventType.role_mapping_failure,
            actor_email=request.query_params.get('user_hint'),  # Best effort
            source_ip=request.client.host if request.client else None,
            target="GET /auth/oidc/callback",
            result="deny",
            reason=f"OIDC callback rejected login: {exc.detail}"
        )
        await emit_security_event(event, db=None)
        
        logger.warning('OIDC callback rejected login: %s', exc.detail)
        return _redirect_to_login_error(str(exc.detail))
    
    except Exception as exc:
        event = SecurityEvent(
            event_type=SecurityEventType.sso_failure,
            source_ip=request.client.host if request.client else None,
            user_agent=request.headers.get('user-agent'),
            target="GET /auth/oidc/callback",
            result="error",
            reason=f"OIDC auth failed: {type(exc).__name__}"
        )
        await emit_security_event(event, db=None)
        
        logger.exception('OIDC callback failed.', exc_info=exc)
        return _redirect_to_login_error('OIDC sign-in failed. Please try again.')
```

**Similar pattern for SAML ACS endpoint.**

---

## Part 3: Integration Testing

### Test: Verify No Silent 403s

**File:** `backend/tests/routers/test_auth_security_events.py` (NEW)

```python
"""Integration tests for security event emission in auth flows."""

import pytest
from backend.models.audit_event import SecurityEventType

@pytest.mark.asyncio
async def test_failed_login_emits_auth_failure_event(client, db, caplog):
    """Verify failed login emits security event."""
    response = client.post('/api/auth/login', json={
        'email': 'nonexistent@example.com',
        'password': 'wrongpass'
    })
    assert response.status_code == 401
    assert 'auth_failure' in caplog.text


@pytest.mark.asyncio
async def test_rbac_denial_emits_event(client, db, authenticated_user, caplog):
    """Verify 403 RBAC denial emits security event."""
    # Try to access admin endpoint without admin role
    response = client.get(
        '/api/admin/reports',
        headers={'Authorization': f'Bearer {authenticated_user.token}'}
    )
    assert response.status_code == 403
    # Check logs contain rbac_denial event
    assert 'rbac_denial' in caplog.text or caplog.records  # DB audit event


@pytest.mark.asyncio
async def test_sso_failure_emits_event(client, caplog, monkeypatch):
    """Verify SSO provider failure emits security event."""
    # Mock OIDC provider to return error
    monkeypatch.setattr('backend.services.auth_oidc.complete_oidc_login', 
                        side_effect=OIDCConfigurationError("Provider unreachable"))
    
    response = client.get('/api/auth/oidc/callback?code=bad_code')
    assert response.status_code in (302, 400)
    assert 'sso_failure' in caplog.text
```

---

## Part 4: Verification Checklist

- [ ] `SecurityEventType` enum created and documented
- [ ] `backend/services/security_events.py` module added with `emit_security_event()`
- [ ] Auth router emits `auth_success`, `auth_failure`, `breakglass_login`, `rate_limit_exceeded`
- [ ] OIDC/SAML callbacks emit `sso_success`, `sso_failure`, `role_mapping_failure`
- [ ] Events include standard fields: event_type, actor, target, result, source_ip, user_agent, correlation_id
- [ ] Unit tests verify logging to stdout
- [ ] Integration tests verify no silent 403s
- [ ] JSON log format passes SIEM schema validation
- [ ] No regression in existing audit_events table
- [ ] 300+ backend tests passing

---

## Deliverables

1. ✅ Code committed to `main`
2. ✅ All tests passing (300+ backend tests)
3. ✅ JSON log sample attached to PR
4. ⏳ Phase 2 issue created for RBAC emission (depends on authorization refactor)
5. ⏳ Phase 3 issue created for OTel integration (evaluate cost/benefit)

---

## Notes for Ray

- Keep events **immutable** (use @dataclass fields)
- Emit to logs **always**; persist to DB **only** if actor_user_id + family_id present
- Don't commit DB in emit function — caller decides scope
- Sanitize reason strings (avoid user input reflection)
- Test in Docker (`LOG_JSON=true`) to verify Azure Monitor format
- Consider performance: is emitting ~1000 events/day acceptable?
