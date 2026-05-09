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

### Ray Grading Pipeline Runtime (2026-05-08)
- **Author:** Ray
- **Decision:** Use PyMuPDF for PDF-to-image OCR input, implement Ollama/OpenAI grading with strict JSON-oriented prompts plus freeform parsing fallback, and run grading worker as startup-managed daemon thread polling queued jobs.
- **Impact:** End-to-end upload → OCR → AI grading active by default, auto-completes when confidence meets threshold, gracefully routes low-confidence cases to `needs_review`.

### Ray CI Setup (2026-05-08)
- **Author:** Ray
- **Context:** GitHub Actions CI for push and pull request validation on `main`; backend pytest suite already forces SQLite test database.
- **Decision:** Use SQLite for backend CI test job instead of provisioning PostgreSQL; install `tesseract-ocr` and run verbose pytest with coverage from `backend/`.
- **Impact:** CI aligned with Winston/Ray backend test strategy, faster execution, avoids unexercised database service.

### Ray Docker Local Stack (2026-05-08)
- **Author:** Ray
- **Context:** `docker compose up` failed locally: missing `.env`, exposed conflicting ports, Ollama treated as optional despite grading dependency.
- **Decision:** Default compose stack self-contained via automatic `.env.example` load with `.env` as optional override; PostgreSQL and Ollama on internal Docker network; pre-pull configured Ollama model before app start.
- **Impact:** Fresh clones boot with `docker compose up --build`; local AI grading works without manual steps; health checks represent real grading readiness.

### Winston CI Test Reliability (2026-05-08)
- **Author:** Ray (on behalf of Winston test strategy)
- **Context:** GitHub Actions test runs need backend suite to pass without PostgreSQL, Tesseract, Ollama, or OpenAI services.
- **Decision:** Keep backend pytest suite SQLite-first in CI; store upload artifacts under `backend/.pytest-state`; mock OCR/AI service calls in tests; keep static `/grades/history` and average routes ahead of `/{grade_id}`.
- **Impact:** CI executes `cd backend && python -m pytest -v` without external service containers; review-queue tests safe to skip when no review jobs seeded.

### Ray CP-01 Multi-Family Tenancy (2026-05-08)
- **Author:** Ray
- **Decision:** Keep signed cookie sessions, add first-run owner bootstrap, and scope all existing family data tables by `family_id` with query-level filtering in every router.
- **Migration note:** Legacy installs are upgraded into one default family and one owner user using `BOOTSTRAP_OWNER_EMAIL` plus the existing `FAMILY_PASSWORD` or `FAMILY_PASSWORD_HASH`.
- **Impact:** Backend and frontend can move to per-user auth immediately, while future invitation and RBAC work can build on `FamilyMembership`, `Invitation`, and `FamilySettings` without another tenancy rewrite.

### Winston DX-04 CI/CD Quality Gates (2026-05-08)
- **Author:** Winston
- **Decision:** Applied required PR checks for `main`: `Backend quality gate`, `Migration checks`, `Frontend checks`, `Container checks`, and `Secret scan`. Backend coverage floor set to 76%. Container policy fails CI on Trivy `HIGH`/`CRITICAL` with `.trivyignore` for reviewed exceptions. Release automation publishes `v*` tags to `ghcr.io/x3nc0n/homeschool-hero`.
- **Impact:** Automated quality gates enforce all PR merges meet code, migration, build, container, and secret scanning standards; release pipeline publishes versioned containers automatically.

### User Directive: OIDC Identity Provider Support (2026-05-08)
- **By:** John (via Copilot)
- **What:** Authentication should support OIDC with configurable IdP. Must integrate with Microsoft Entra ID. SAML 2.0 support is acceptable too. Config should let users pick their own identity provider. John will personally integrate with Entra ID.
- **Why:** User request — captured for team memory.

## Governance

- All meaningful changes require team consensus
- Document architectural decisions here
- Keep history focused on work, decisions focused on direction
