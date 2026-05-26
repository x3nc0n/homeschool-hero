---
title: API Reference
description: Overview of the Homeschool Hero REST API — base URL, versioning, content types, and interactive documentation.
---

# API Reference

Homeschool Hero exposes a family-scoped REST API built with FastAPI. Every authenticated request operates within the context of a single family; cross-family data access is not possible.

## Base URL

```
/api
```

All endpoints are relative to `/api`. For a local development instance running on port 8000:

```
http://localhost:8000/api
```

## Versioning

The API is currently unversioned. Breaking changes follow the project's release changelog. The live OpenAPI schema at `/api/openapi.json` always reflects the running server version.

## Content Types

| Direction | Value |
|-----------|-------|
| Request body | `application/json` |
| Response body | `application/json` |
| File uploads | `multipart/form-data` |
| SAML metadata | `application/xml` |

All JSON responses use UTF-8 encoding.

## Authentication

Requests are authenticated via a signed session cookie (`homeschool_session`). Mutating requests additionally require the `X-CSRF-Token` header populated from the `homeschool_csrf` cookie.

See [Authentication](./authentication.md) for full details on local, OIDC, and SAML flows.

## Interactive Documentation

FastAPI publishes interactive docs automatically from the same server:

| Interface | URL |
|-----------|-----|
| OpenAPI JSON schema | `/api/openapi.json` |
| Swagger UI | `/api/docs` |
| ReDoc | `/api/redoc` |

Swagger UI automatically forwards the session cookie and injects `X-CSRF-Token` for same-origin mutating requests, so you can authenticate once and test endpoints directly in the browser.

## Rate Limiting

The API applies per-window in-memory throttles:

| Endpoint group | Limit |
|----------------|-------|
| Auth endpoints (`/api/auth/login`, `/api/auth/register`, invitation acceptance) | 5 req / 60 s |
| Submission uploads | 10 req / 60 s |
| Export creation and deletion | 5 req / 60 s |
| General authenticated traffic | 100 req / 60 s |

Exceeded limits return `429 Too Many Requests` with a `Retry-After` header indicating the retry window in seconds.

## Error Envelope

All structured errors share a common JSON envelope:

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

See [Errors](./errors.md) for the full list of status codes and recommended client handling.

## Resource Overview

| Resource | Base path | Description |
|----------|-----------|-------------|
| Auth | `/api/auth` | Login, logout, session management, OIDC, SAML |
| Students | `/api/students` | Student roster CRUD |
| Assignments | `/api/assignments` | Assignments and answer keys |
| Submissions | `/api/submissions` | Student work uploads |
| Grades | `/api/grades` | Grade records and averages |
| Gradebook | `/api/gradebook` | Rollups, summaries, trends |
| Subjects | `/api/subjects` | Subject management |
| Curriculum | `/api/curriculum` | Packages, units, lessons, resources |
| Calendar | `/api/calendar` | School years, terms, grading periods, events |
| Schedule | `/api/schedule` | Student weekly schedules |
| Lesson Plans | `/api/lesson-plans` | Lesson plan management |
| Quizzes | `/api/quizzes` | Quiz creation and delivery |
| Reviews | `/api/reviews` | Manual grading review queue |
| Grading | `/api/grading` | Background grading jobs |
| Notifications | `/api/notifications` | In-app notification feed and preferences |
| Invitations | `/api/invitations` | Family member invitations |
| Exports | `/api/exports` | Async data export jobs |
| Report Cards | `/api/report-cards` | Report card generation |
| Transcripts | `/api/transcripts` | Transcript generation |
| Compliance | `/api/compliance-reports` | Compliance report generation |
| Audit | `/api/audit` | Immutable activity log |
| Search | `/api/search` | Cross-resource search |
| Dashboard | `/api/dashboard` | Aggregated dashboard data |
| Admin | `/api/admin` | Platform administration |
| Health | `/api/health` | Service health check |
