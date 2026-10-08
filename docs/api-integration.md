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

## Curriculum import and duplicate detection

All routes require the `manage_curriculum` capability and are scoped to the caller's family.

### Background AI drafts (recommended)

`POST /api/curriculum/ai-import-sessions` accepts exactly one source: a multipart `file` (`.txt`, `.pdf`, `.docx`, at most `min(UPLOAD_MAX_BYTES, 10 MiB)`) or JSON `{"url": "https://..."}`. It stores a `processing` session and returns **202** immediately with `Location: /api/curriculum/ai-import-sessions/{id}` and `Retry-After: 2`. Text extraction, URL fetches, and model inference run in a background worker; source bytes and text stay in worker memory only.

Session resource (`POST` 202, `GET /api/curriculum/ai-import-sessions/{id}` 200):

```json
{
  "id": 12,
  "status": "processing | ready | failed | expired | confirmed",
  "source_kind": "file | url",
  "source_name": "scope.txt",
  "warnings": [],
  "revision": 2,
  "expires_at": "2026-10-09T15:51:00Z",
  "created_at": "2026-10-08T15:51:00Z",
  "updated_at": "2026-10-08T15:51:40Z",
  "draft": { "schema_version": "1.0", "name": "...", "subjects": [] },
  "error": { "code": "ai_response_invalid", "message": "..." }
}
```

- `draft` is populated only when `status` is `ready`; `error` only when `failed`.
- `GET` returns `Retry-After: 2` while `processing`. Sessions expire 24 hours after creation. A `processing` session that outlives the configured provider timeout/retry budget (minimum 30 minutes) becomes `failed` with `processing_stale`.
- Every state change increments `revision`. Late or cancelled workers cannot overwrite a session because completion is a compare-and-set on `id`, family, `processing` status, and the captured revision.
- `DELETE /api/curriculum/ai-import-sessions/{id}` returns **204** and marks an unconfirmed session `expired` (cancelling any running worker). A `confirmed` session returns **409** `curriculum_ai_import_session_confirmed`.
- `POST /api/curriculum/ai-import-sessions/{id}/confirm` with `{"draft": {...}, "client_revision": 2, "acknowledged_duplicate_ids": []}` returns **201** with the created curriculum. It returns **409** with `curriculum_ai_import_session_confirmed`, `curriculum_ai_import_session_expired`, `curriculum_ai_import_session_not_ready`, or `curriculum_ai_import_session_stale` (revision mismatch), or the duplicate/name conflicts below. On any conflict the session stays `ready` and keeps its draft.
- Worker error codes: `ai_import_unavailable`, `ai_provider_timeout`, `ai_provider_error`, `ai_response_invalid`, `source_extraction_failed`, `processing_failed`, `processing_stale`. Messages never contain model output or document text.

The synchronous `POST /api/curriculum/ai-import` and `POST /api/curriculum/ai-import/confirm` routes remain available.

With `AI_LOCAL_ONLY=true`, drafting uses the native Ollama `POST {OLLAMA_HOST}/api/chat` API with the curriculum JSON schema as `format`, `stream: false`, and `temperature: 0`. Tool calling is not required, and there is never a cloud fallback. Only transport failures (timeouts, connection errors, HTTP 429/502/503/504) are retried; invalid JSON or schema mismatches fail immediately with `ai_response_invalid`.

### Duplicate preflight and confirmation

`POST /api/curriculum/import/duplicate-check` with `{"draft": {...}}` returns `{"matches": [...]}` without creating anything. Each match:

```json
{
  "id": 7,
  "name": "Saxon Math 5/4",
  "grade_levels": ["4"],
  "edition": "3rd Edition",
  "reason": "exact_curriculum | partial_overlap",
  "matched_subjects": ["Mathematics"],
  "matched_units": ["Fractions"],
  "matched_lessons": ["Adding Fractions", "Subtracting Fractions"]
}
```

`POST /api/curriculum/import/confirm` with `{"draft": {...}, "acknowledged_duplicate_ids": [7]}` returns **201**.

Matching rules:

- Subject, unit, and lesson names are compared after Unicode NFKC normalization, case folding, and removal of cosmetic spacing and punctuation. Curriculum titles, file names, and `source` are ignored.
- `exact_curriculum`: the same subject/unit/lesson structure, with at least one non-generic lesson.
- `partial_overlap`: the same subject and unit with at least two distinct shared lessons, not counting generic names such as "Lesson 1", "Week 3", "Introduction", or "Unit Review".
- Explicitly different grade levels, editions (`metadata.edition`), or disjoint `standards_alignment` mean the curricula are not duplicates.

Every import path shares one gate, re-checked inside the creating transaction: `/curriculum/import`, `/curriculum/import/confirm`, `/curriculum/ai-import/confirm`, `/curriculum/ai-import-sessions/{id}/confirm`, and `/curriculum/sources/{source_id}/import/{item_id}`.

- `409 curriculum_import_duplicate_conflict`: one or more current matches are not in `acknowledged_duplicate_ids`. The matches are in `error.details.matches`. Acknowledgements only apply to current matches in the caller's family. `/curriculum/import` and source imports have no acknowledgement field, so they always reject matches.
- `409 curriculum_import_name_conflict`: a curriculum with the same name already exists in the family. Acknowledgements cannot override this; rename the draft.
- `422 curriculum_import_duplicate_names`: the draft repeats a sibling subject, unit, or lesson name. The JSON paths (for example `subjects[0].units[0].lessons[1].name`) are in `error.details.paths`.

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
