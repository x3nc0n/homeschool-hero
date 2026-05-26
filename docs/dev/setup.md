---
title: Local Setup
description: Prerequisites, environment configuration, and commands to run Homeschool Hero locally.
---

# Local Setup

## Prerequisites

| Tool | Version | Notes |
|------|---------|-------|
| Python | 3.12 | 3.11 is also supported in CI |
| Node.js | 22 | Required for the frontend and docs |
| PostgreSQL | 16 | For local parity with Docker deployments |
| Tesseract | any | Optional — needed for OCR-based grading |
| Ollama | any | Optional — needed for local AI grading |

> **Note:** The backend test suite uses SQLite so you can run tests without PostgreSQL. PostgreSQL is only needed when running the full application.

## Environment Configuration

Copy the example env file and edit it:

```powershell
copy .env.example .env
```

Key variables to set for local development:

| Variable | Description | Default / Example |
|----------|-------------|-------------------|
| `DATABASE_URL` | PostgreSQL or SQLite connection string | `postgresql+asyncpg://user:pass@localhost/homeschool` |
| `SECRET_KEY` | Cookie signing key (generate a random value) | — |
| `AUTH_PROVIDER` | `local`, `oidc`, or `saml` | `local` |
| `AUTH_BREAKGLASS_LOCAL` | Allow local login when OIDC/SAML is active | `false` |
| `SESSION_COOKIE_NAME` | Session cookie name | `homeschool_session` |
| `CSRF_COOKIE_NAME` | CSRF cookie name | `homeschool_csrf` |

See `docs/auth-providers.md` for OIDC and SAML-specific variables.

## Backend

### Install dependencies

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### Apply migrations

```powershell
cd backend
python -m backend.cli migrations upgrade head
```

### Run the development server

```powershell
cd backend
uvicorn backend.main:app --reload
```

The API is available at `http://localhost:8000/api`. Swagger UI is at `http://localhost:8000/api/docs`.

### Common backend commands

```powershell
# Run tests
python -m pytest -q

# Check migration status
python -m backend.cli migrations status

# Apply all pending migrations
python -m backend.cli migrations upgrade head

# Roll back one migration
python -m backend.cli migrations downgrade -1
```

## Frontend

### Install dependencies

```powershell
cd frontend
npm ci
```

### Development server (Vite hot-reload)

```powershell
npm run dev
```

The Vite dev server proxies API requests to `http://localhost:8000`.

### Production build check

```powershell
npm run build
```

### Optional lint

```powershell
npm run lint
```

## Full Stack with Docker

### Standard stack (app + database)

```powershell
docker compose up --build
```

### Full stack (includes Ollama for AI grading)

```powershell
docker compose --profile full up --build
```

Docker Compose starts:
- `app` — FastAPI backend + background grading worker
- `db` — PostgreSQL 16
- `ollama` — local LLM (full profile only)

The app is accessible at `http://localhost:8000`.

## First Run

After starting the server with an empty database, navigate to `http://localhost:8000`. The application detects that no owner account exists and prompts for first-run setup. Alternatively, call the API directly:

```http
GET /api/auth/bootstrap
```

If `bootstrap_required` is `true`, post to `/api/auth/register` with owner credentials to create the first family.

## Adding a New Endpoint

1. Add or extend the SQLAlchemy model in `backend/models/`.
2. Mirror the public contract in `backend/schemas/`.
3. Implement the router in `backend/routers/`.
4. Re-export the router from `backend/routers/__init__.py`.
5. Mount the router in `backend/main.py`.
6. Add pytest coverage in `backend/tests/`.
7. Verify the generated OpenAPI schema at `/api/openapi.json`.

Conventions to follow:

- Every query must filter by `family_id`.
- Use async SQLAlchemy sessions via FastAPI `Depends(get_db)`.
- Declare a Pydantic `response_model` on every route decorator.
- Raise `HTTPException` for all error conditions — use the shared error envelope.
- Use `require_capabilities()` or `require_any_role()` from `backend.services.authorization` for protected routes.

## Adding or Changing Models

- Define columns and relationships in `backend/models/`.
- Mirror the public contract in `backend/schemas/`.
- Keep serialization logic in routers or services, not in the frontend.
- If the model affects reporting, exports, notifications, or audit history, update those paths in the same change.
- Generate a migration: see [Migrations](/migrations).
