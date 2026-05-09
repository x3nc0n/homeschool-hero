# API integration guide

Homeschool Hero exposes a family-scoped REST API under `/api`. FastAPI publishes the live OpenAPI schema at `/api/openapi.json`, Swagger UI at `/api/docs`, and ReDoc at `/api/redoc`.

## Authentication

### Session + CSRF model

- Authentication uses the signed `SESSION_COOKIE_NAME` cookie (`homeschool_session` by default).
- Mutating requests (`POST`, `PUT`, `PATCH`, `DELETE`) must also send `X-CSRF-Token` with the value from the `CSRF_COOKIE_NAME` cookie (`homeschool_csrf` by default).
- Read-only requests (`GET`, `HEAD`, `OPTIONS`) only need the session cookie.
- Standard auth failures return `401` with the shared JSON error envelope.

### Local authentication flow

1. Check whether first-run bootstrap is still available: `GET /api/auth/bootstrap`
2. Create the owner account and first family: `POST /api/auth/register`
3. Reuse the issued session cookie for later calls.
4. Restore a session summary at any time with `GET /api/auth/me`.

Example local sign-in request:

```http
POST /api/auth/login
Content-Type: application/json

{
  "email": "parent@example.com",
  "password": "CorrectHorseBatteryStaple123!",
  "family_id": 1
}
```

### OIDC flow

When `AUTH_PROVIDER=oidc`:

1. Redirect the user to `GET /api/auth/oidc/login`
2. Complete the provider handshake at `GET /api/auth/oidc/callback`
3. Homeschool Hero provisions or matches the user by email, then issues the normal session cookie

Use this for Microsoft Entra ID or any OpenID Connect provider with a discovery document. See `docs/auth-providers.md` for environment variables and the Entra example.

### SAML flow

When `AUTH_PROVIDER=saml`:

1. Publish SP metadata from `GET /api/auth/saml/metadata`
2. Redirect the user to `GET /api/auth/saml/login`
3. Accept the signed assertion at `POST /api/auth/saml/acs`
4. Homeschool Hero matches or provisions the user and then issues the normal session cookie

## Common workflow

### 1. Create the student roster

1. `POST /api/students`
2. `POST /api/subjects`
3. Optional planning setup:
   - `POST /api/calendar/school-years`
   - `POST /api/calendar/terms`
   - `POST /api/calendar/grading-periods`
   - `POST /api/schedule`
   - `POST /api/lesson-plans`

### 2. Create assignments

1. `POST /api/assignments`
2. Optional assessment helpers:
   - `POST /api/quizzes`
   - `PUT /api/gradebook/categories`
   - `PUT /api/gradebook/scales`

### 3. Submit work

1. Upload work with `POST /api/submissions`
2. Poll grading progress through:
   - `GET /api/submissions`
   - `GET /api/grading/jobs`
   - `GET /api/reviews` for manual review items

### 4. Grade and review

1. Auto or manual grading persists through `POST /api/grades`
2. Gradebook rollups are available from:
   - `GET /api/gradebook/{student_id}`
   - `GET /api/gradebook/{student_id}/summary`
   - `GET /api/gradebook/{student_id}/trends`
   - `GET /api/grades/history`

### 5. Produce reports and exports

1. `POST /api/report-cards/generate`
2. `POST /api/transcripts/generate`
3. `POST /api/compliance-reports/generate`
4. `POST /api/exports`
5. Poll `GET /api/exports/{job_id}/status`
6. Download `GET /api/exports/{job_id}/download`

## Notifications and integration points

Homeschool Hero currently supports these integration-friendly surfaces:

- **In-app notifications:** `GET /api/notifications`, `PATCH /api/notifications/{notification_id}/read`, `PUT /api/notifications/preferences`
- **Email delivery:** invitation, grading, backup, compliance, and security alert emails when SMTP is configured
- **Polling-friendly job APIs:** import, grading, compliance report, transcript, report card, and export endpoints expose status-oriented resources
- **Audit trail:** `GET /api/audit` provides an immutable activity stream for downstream operational review

There is no outbound webhook dispatcher yet. Integrations that need near-real-time updates should poll the relevant job or notification endpoints.

## Rate limiting

The API applies in-memory per-window throttles:

- Auth-sensitive endpoints (`/api/auth/login`, `/api/auth/register`, invitation acceptance): **5 requests / 60 seconds**
- Submission uploads: **10 requests / 60 seconds**
- Export creation and deletion: **5 requests / 60 seconds**
- General authenticated API traffic: **100 requests / 60 seconds**

When a limit is exceeded the API returns:

- `429 Too Many Requests`
- a standard JSON error body
- `Retry-After` header with the retry window in seconds

## Error handling

All structured errors use the same envelope:

```json
{
  "detail": "Invalid request.",
  "error": {
    "code": "validation_error",
    "message": "Invalid request.",
    "details": [
      {
        "loc": ["body", "field"],
        "msg": "Field is required",
        "type": "missing"
      }
    ]
  }
}
```

Recommended client handling:

- `400`: request shape or business rule issue; correct the payload
- `401`: missing or expired session; re-authenticate
- `403`: authenticated but missing capability/role
- `404`: entity not found in the current family scope
- `409`: operation state conflict (for example, downloading an export before it completes)
- `422`: validation error; surface field-level details
- `429`: respect `Retry-After` and back off

## Documentation endpoints

- OpenAPI JSON: `/api/openapi.json`
- Swagger UI: `/api/docs`
- ReDoc: `/api/redoc`

Swagger UI automatically forwards the current session cookie and injects `X-CSRF-Token` from the CSRF cookie for same-origin mutating requests.
