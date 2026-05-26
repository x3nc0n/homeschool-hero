---
title: Errors
description: Error response format, HTTP status codes, and troubleshooting guidance for the Homeschool Hero API.
---

# Errors

## Error Envelope

All structured error responses use a shared JSON envelope:

```json
{
  "detail": "Human-readable summary.",
  "error": {
    "code": "error_code_string",
    "message": "Human-readable summary.",
    "details": [
      {
        "loc": ["body", "field_name"],
        "msg": "Field is required",
        "type": "missing"
      }
    ]
  }
}
```

`detail` mirrors FastAPI's standard error field and is present on all `HTTPException` responses. The nested `error` object provides additional structure for validation errors; for non-validation errors it may be absent.

## HTTP Status Codes

| Code | Name | Meaning & Recommended Action |
|------|------|-------------------------------|
| `200` | OK | Request succeeded. |
| `201` | Created | Resource created successfully. |
| `204` | No Content | Successful delete or no-body response. |
| `400` | Bad Request | Request shape or business rule violation. Correct the payload and retry. |
| `401` | Unauthorized | Missing or expired session. Re-authenticate and retry. |
| `403` | Forbidden | Authenticated but lacks the required role or capability. Check `effective_capabilities` in the session response. |
| `404` | Not Found | Resource does not exist within the current family scope. |
| `409` | Conflict | Operation state conflict. Examples: student name collision, grading a non-current submission, downloading an in-progress export. |
| `422` | Unprocessable Entity | Pydantic validation failure. Surface the `details` array to the user. |
| `423` | Locked | Account temporarily locked after repeated login failures. Wait for the lockout window to expire. |
| `429` | Too Many Requests | Rate limit exceeded. Read the `Retry-After` response header and back off. |
| `503` | Service Unavailable | Maintenance mode is active. The `detail` field contains the maintenance message. |

## Common Error Scenarios

### 401 — Session expired

```json
{ "detail": "Not authenticated" }
```

**Cause:** The session cookie is missing, expired, or invalid.

**Fix:** Call `POST /api/auth/login` (or redirect to the OIDC/SAML login URL) to obtain a fresh session.

### 403 — Insufficient capability

```json
{ "detail": "Role 'tutor' is not allowed to manage students." }
```

**Cause:** The authenticated session lacks the required capability for the requested action.

**Fix:** Review `effective_capabilities` from `GET /api/auth/me`. Tutors cannot create or delete students; only `parent`, `co_parent`, or `admin` sessions with `manage_students` are permitted.

### 403 — App role mismatch

```json
{
  "detail": "App roles 'student' are not allowed to view students; expected one of: teacher."
}
```

**Cause:** The session carries an app role (`student`) that is below the minimum required for the endpoint.

**Fix:** Ensure the user has been assigned the appropriate app role by an admin.

### 404 — Resource not found (family scoped)

```json
{ "detail": "Student not found" }
```

**Cause:** The requested resource either does not exist or belongs to a different family. The API never reveals the existence of cross-family data.

### 409 — Conflict

```json
{ "detail": "Student already exists" }
```

**Cause:** A uniqueness constraint was violated within the family scope (e.g., duplicate student name, grade already recorded for a submission).

### 422 — Validation error

```json
{
  "detail": "Invalid request.",
  "error": {
    "code": "validation_error",
    "message": "Invalid request.",
    "details": [
      {
        "loc": ["body", "name"],
        "msg": "Field required",
        "type": "missing"
      }
    ]
  }
}
```

**Cause:** The request body failed Pydantic schema validation.

**Fix:** Use the `loc` path to identify the offending field and correct the payload.

### 423 — Account locked

```json
{ "detail": "Account temporarily locked. Try again later." }
```

**Cause:** Five or more consecutive failed login attempts triggered a lockout. A security alert notification is also sent to the account.

**Fix:** Wait for the lockout window (configured by `AUTH_LOCKOUT_DURATION`) to expire, then try again.

### 429 — Rate limit exceeded

```http
HTTP/1.1 429 Too Many Requests
Retry-After: 45
Content-Type: application/json

{ "detail": "Too many requests. Retry after 45 seconds." }
```

**Cause:** The per-window request limit was exceeded for the endpoint group.

**Fix:** Pause for at least `Retry-After` seconds before retrying. Implement exponential back-off in automated clients.

### 503 — Maintenance mode

```json
{ "detail": "The system is undergoing scheduled maintenance. Please try again shortly." }
```

**Cause:** An administrator has enabled maintenance mode.

**Fix:** Only sessions with the `manage_platform` capability (admin sessions) can bypass maintenance mode. All other clients should display the maintenance message and retry later.

## CSRF Errors

Mutating requests missing the `X-CSRF-Token` header, or with a token that does not match the `homeschool_csrf` cookie, are rejected with:

```
403 Forbidden
```

Ensure the CSRF cookie value is read from the browser cookie store and sent in the header on every `POST`, `PUT`, `PATCH`, and `DELETE` request.

## Debugging Tips

1. **Swagger UI** at `/api/docs` automatically handles CSRF for same-origin requests — use it to isolate whether an issue is client-side.
2. **`GET /api/auth/me`** returns the full session including `effective_capabilities` — compare against the capability required by the failing endpoint.
3. **`GET /api/health`** requires no authentication and confirms the server and database are reachable.
4. **Audit log** at `GET /api/audit` (requires `manage_platform`) records login events, grade changes, and other mutations — useful for tracing unexpected `403` or `409` patterns.
