# Development guide

## Local setup

### Prerequisites

- Python 3.12
- Node.js 22
- PostgreSQL 16 for local parity with Docker deployments
- Optional: Tesseract OCR and Ollama if you want to exercise the full grading pipeline locally

### Backend

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Create `.env` from `.env.example`, then point `DATABASE_URL` at your local PostgreSQL instance or the default SQLite test database as needed.

Common backend commands:

```powershell
cd backend
python -m pytest -q
python -m backend.cli migrations status
python -m backend.cli migrations upgrade head
uvicorn backend.main:app --reload
```

### Frontend

```powershell
cd frontend
npm ci
npm run build
```

Use `npm run dev` for the Vite dev server when you want frontend-only iteration.

### Full stack with Docker

```powershell
docker compose up --build
docker compose --profile full up --build
```

## Running tests

- Backend regression suite: `cd backend && python -m pytest -q`
- Frontend production build check: `cd frontend && npm run build`
- Optional frontend lint: `cd frontend && npm run lint`
- Migration verification: `python -m backend.cli migrations verify`

The backend test harness uses SQLite and stores ephemeral state under `backend\.pytest-state`.

## Adding a new endpoint

1. Add or extend the SQLAlchemy model in `backend\models\`
2. Add request/response schemas in `backend\schemas\`
3. Implement the router in `backend\routers\`
4. Re-export the router from `backend\routers\__init__.py`
5. Mount the router in `backend\main.py`
6. Add pytest coverage in `backend\tests\`
7. Confirm the generated OpenAPI output at `/api/openapi.json`

Conventions worth keeping:

- Keep every query family-scoped
- Use async SQLAlchemy sessions and FastAPI dependency injection
- Return Pydantic response models from routers
- Reuse the shared JSON error envelope by raising `HTTPException`
- Prefer capability checks from `backend.services.authorization` for protected actions

## Adding or changing models

- Define columns and relationships in `backend\models\`
- Mirror the public contract in `backend\schemas\`
- Keep serialization logic in routers or services, not in the frontend
- If the model affects reporting, exports, notifications, or audit history, update those paths in the same change

## Migration workflow

Homeschool Hero uses Alembic. See `docs/migrations.md` for the full policy.

Typical workflow:

```powershell
python -m backend.cli migrations create -m "add_new_feature"
python -m backend.cli migrations lint
python -m backend.cli migrations upgrade head
python -m backend.cli migrations downgrade -1
python -m backend.cli migrations upgrade head
```

Every migration must:

- include a `ROLLBACK_NOTES` block
- define a real `downgrade()`
- describe destructive behavior plainly

## Code style and conventions

- Python uses type annotations, async route handlers, and Pydantic v2 models
- FastAPI routes live under `/api` and should expose response models whenever possible
- Backend services hold reusable business logic; routers stay thin
- Frontend uses React 18 + Vite + TypeScript
- Multi-family isolation is mandatory: never query shared data without filtering by `family_id`
- Mutating browser/API requests require CSRF protection

## Handy references

- Architecture overview: `docs/architecture.md`
- Auth provider setup: `docs/auth-providers.md`
- Migration policy: `docs/migrations.md`
- API docs: `/api/docs`, `/api/redoc`
