# Squad Decisions

## Active Decisions

### GitHub Repository Setup (2026-05-08)
- **Context:** The requested repository owner was `jspai`, but the authenticated GitHub CLI account resolved to `x3nc0n`.
- **Decision:** Created the public repository as `x3nc0n/homeschool-hero` so the initial publish could complete successfully with the active credentials.
- **Impact:** Team references should use https://github.com/x3nc0n/homeschool-hero unless ownership is transferred later.

### MVP Architecture (2026-05-08)
- **Author:** Egon
- **Decision:** Python/FastAPI + React/Vite + PostgreSQL, Tesseract OCR + Ollama AI, DB-based job queue, single-family auth, confidence-based grading routing (auto-approve >0.8, human review <0.8).
- **Impact:** All agents reference `docs/architecture.md`. 25 work items defined. Ray owns backend (tasks 1-8, 17-19, 25), Venkman owns frontend (9-16, 20), Winston owns tests (21-24).

### Ray Backend Implementation (2026-05-08)
- **Decision:** FastAPI + async SQLAlchemy + Alembic, cookie-based signed sessions, JSON-capable quiz/submission/grade APIs with route-level middleware protection.
- **Impact:** Frontend and test agents can integrate against stable REST endpoints via `docker compose up --build`. Migrations and model contracts defined for all MVP entities.

### Venkman Frontend Implementation (2026-05-08)
- **Decision:** React 18 + Vite SPA, React Router v6 protected routing, shadcn/ui + Tailwind components.
- **Impact:** Core flows fully wired: authentication, dashboard, student/subject/assignment CRUD, uploads with progress/preview, grade book filtering/averages, quiz builder/taking, human review queue actions.

### Winston Test Strategy (2026-05-08)
- **Decision:** Spec-first pytest under `backend/tests/`, SQLite-backed test defaults, async httpx clients, mocked OCR/AI dependencies.
- **Impact:** Suite runnable before Postgres/Tesseract/Ollama. Tests can be enforced with minor adjustments if final API differs from architecture draft.

## Governance

- All meaningful changes require team consensus
- Document architectural decisions here
- Keep history focused on work, decisions focused on direction
