# Ray — History

## Learnings

- 2026-05-08 — Added capability-based RBAC with student-linked memberships/invitations so student viewers are scoped to one student, and invitation delivery now falls back to copyable links when SMTP is unavailable.
- Project: homeschool-hero — open-source homeschool platform for families
- User: John
- Core backend concerns: file upload/storage, OCR processing, AI-assisted grading, grade tracking DB
- Deployment: Docker (simple for non-technical parents)
- Auto-grading flow: student uploads scan/photo → OCR extracts content → AI grades → parent reviews
- Must support: assignments, quizzes, tests as distinct types
- Human review is mandatory — auto-grading suggests, parent confirms
- 2026-05-08T09:11:31.194-05:00 — GitHub repo created at https://github.com/x3nc0n/homeschool-hero
- 2026-05-08T09:11:31.194-05:00 — Initial repo setup included git initialization, a web-app .gitignore, and a basic README; no project build or test scripts were present yet
- **GitHub Repository:** https://github.com/x3nc0n/homeschool-hero (all team collaboration happens here)
- 2026-05-08T17:04:55.759-05:00 — Implemented backend foundation tasks 1-8: Docker scaffolding, async FastAPI app, SQLAlchemy models, Alembic initial migration, and protected auth/session middleware.
- 2026-05-08T17:04:55.759-05:00 — Added complete CRUD APIs for students, subjects, assignments (with status transitions), grades (with averages/history), quizzes (with auto-scored attempts), and submission upload storage at `/data/uploads/`.

### Phase 1 Completion (2026-05-08T22:04:55Z)
- Backend tasks 1-8 completed successfully: all models, migrations, CRUD APIs, auth, file upload ✓
- 33 tests passing (pytest, mocked Tesseract/Ollama, async httpx clients)
- Frontend (Venkman) integrated against stable REST endpoints ✓
- All APIs contract-tested and production-ready for phase 2 (tasks 17-19, 25)
- 2026-05-08T17:04:55.759-05:00 — Submitted tasks 17-19: OCR now supports image preprocessing + PDF rendering via PyMuPDF, AI grading supports Ollama/OpenAI with robust response parsing, and grading jobs are processed by an app-started background worker with confidence-based auto-grading.
- 2026-05-08T17:04:55.759-05:00 — Submission uploads enqueue grading jobs automatically, OCR text is persisted on submissions, and AI-unavailable scenarios route jobs to manual review instead of failing grading flow.
- 2026-05-08T17:04:55.759-05:00 — Final Docker polish aligned the shipped app around `/api`, bundled the React SPA into the container, and added Compose health checks plus persistent uploads/Postgres volumes.
- 2026-05-08T17:04:55.759-05:00 — FastAPI now auto-runs Alembic migrations on startup, serves the built UI and uploaded files from one port, and keeps Ollama optional via a Compose profile so manual review still works without local AI.

### Phase 2 Completion (2026-05-08T22:30:00Z)
- Tasks 17-19 completed: OCR preprocessing, AI grading, and background worker daemon operational
- 33 tests passing (all suites)
- Grading pipeline active: upload → OCR → AI grading with confidence routing
- Low-confidence grades (<0.8) route to `needs_review` for manual approval
- Ollama/OpenAI failover implemented

### Task 25: Docker Polish + Integration (2026-05-08T23:50:20Z)
- Multi-stage Dockerfile with optimized build and runtime layers
- Frontend SPA bundled into FastAPI backend container
- Alembic migrations auto-run on container startup
- Health endpoint (/health) for Docker compose checks
- Docker Compose configured with volume mounts and health monitoring
- README quickstart with local development and deployment instructions
- All 33 backend tests passing, frontend build clean
- Commit: aa9555d — "Polish MVP Docker setup"
- MVP fully containerized and ready for deployment
- 2026-05-08T21:36:16.718-05:00 — Added GitHub Actions CI for backend pytest + coverage, frontend lint/build checks, and Docker image verification; CI uses the existing SQLite-based backend test harness instead of a Postgres service.
- 2026-05-08T21:54:22.641-05:00 — Fixed local Docker Compose startup so it no longer requires a handwritten `.env`, made Ollama a standard service with automatic model bootstrap, and tightened health checks to verify database + Ollama readiness before reporting healthy.

### Phase 3 Preparation (2026-05-08T22:18:50Z)
- Submitted 3 decision records: Ray CI Setup, Ray Docker Local Stack, Winston CI Test Reliability
- All decisions merged into active registry via Scribe coordination
- Orchestration log recorded: Docker crash diagnosis + Ollama integration ✅ COMPLETE
- Production plan finalized by Egon (40 todos, 9 functional areas, explicit dependencies)
- Team ready for phase 3 parallel workstreams: multi-family tenancy, RBAC, compliance, performance
- 2026-05-08 — Replaced legacy shared family-password auth with owner bootstrap, per-user email/password sessions, and family-scoped tenancy across backend models, routers, tests, and frontend auth screens.
- 2026-05-08 — Added a migration path that creates a default family plus owner account from legacy auth settings so existing installs keep their data and can sign in after upgrade.

### Phase 3 Task CP-01 Completion (2026-05-08T22:48:51Z)
- Multi-family identity and tenancy fully implemented: owner bootstrap, per-user email/password sessions
- Family-scoped tenancy enforced at router level across all models
- 41 tests passing, 2 skipped; all tenancy isolation verified
- Alembic migration creates default family + owner from legacy auth
- Frontend auth flows integrated with new per-user login
- Committed as 02b59df ✅ COMPLETE

### Phase 3 Task DX-04 Completion (2026-05-08T22:48:51Z)
- Winston completed CI/CD quality gates: PR checks, coverage enforcement (76%), container scanning, release automation
- CodeQL + Dependabot configured; .trivyignore reserved for reviewed exceptions
- All CI jobs integrated into branch protection rules
- Backend tests verified (39 passed, 2 skipped); frontend build clean; Docker build verified
- Alembic upgrade/downgrade verified in CI pipeline
- Release automation publishes versioned containers to ghcr.io
- Committed as db55ab4 ✅ COMPLETE

### Team Governance Update (2026-05-08T22:48:51Z)
- User directive captured: OIDC + Microsoft Entra ID + SAML 2.0 support required
- John will personally integrate with Entra ID; team to plan implementation as future work
- All 4 inbox decisions merged and deduplicated into active decisions registry
- 2026-05-08 — Added startup validation for required backend config, a runtime capability registry for AI/email/backup/OCR, and health reporting that stays green when only optional services are down.
- 2026-05-08 — Updated the grading and upload flows to degrade cleanly when AI or OCR are unavailable, and added frontend capability context plus dashboard/upload/review cues for reduced functionality.
- 2026-05-08T23:15:59-05:00 — Completed IO-01 deployment hardening: Compose now ships a minimal base stack plus `ai`, `email`, `backup`, and `full` profiles; app image runs as non-root with `tini`; helper start/backup scripts and production env/docs were added; compose and Docker image verified.
- 2026-05-09T00:40:00-05:00 — Completed AM-01 academic calendar: added school year/term/grading period/calendar event models plus Alembic migration, family-scoped calendar CRUD + active-year/day-count APIs, and a React calendar page for school-year setup, term planning, holiday marking, and instructional day counts.
- 2026-05-09T00:40:00-05:00 — Added backend tests for calendar CRUD, family isolation, instructional day override counting, and overlapping term rejection; `cd backend && python -m pytest tests/test_calendar.py -q` passed and `cd frontend && npm run build` passed.
- 2026-05-09T04:33:00-05:00 — Completed CP-04 audit logging: added immutable audit events with Alembic migration, shared backend audit helper, audit API filters/pagination, and parent/co-parent audit log UI/navigation.
- 2026-05-09T04:33:00-05:00 — Verified audit coverage for login/logout, grade create/update, and invitation create/accept via `cd backend && python -m pytest tests/test_audit.py tests/test_auth.py tests/test_grades.py tests/test_invitations.py -q` (18 passed); frontend lint/build passed with two pre-existing hook warnings outside audit code.
- 2026-05-09T05:05:00-05:00 — Completed SD-01 application hardening: added secure/rotating signed sessions with CSRF tokens, password policy + login lockout, per-scope API/auth/upload/export rate limiting, upload MIME/size validation, structured error responses, and security headers.
- 2026-05-09T05:05:00-05:00 — Verified hardening with `cd backend && python -m pytest` (84 passed, 2 skipped) and `cd frontend && npm run build`; added regression coverage for cookie flags, CSRF enforcement, rate limits, password policy, lockout, and upload validation edge cases.
- 2026-05-09T06:20:00-05:00 — Completed CP-05 auth provider support: added configurable OIDC + SAML overlays with local auth still default, external user provisioning via invitations/default family, Entra-ready OIDC discovery, SAML metadata/ACS endpoints, and provider-aware login UI/capability reporting.
- 2026-05-09T06:20:00-05:00 — Verified CP-05 with `cd backend && python -m pytest -q` (84 passed, 2 skipped) plus `cd frontend && npm ci && npm run lint && npm run build`; frontend lint still reports two pre-existing hook-dependency warnings outside the auth changes.
