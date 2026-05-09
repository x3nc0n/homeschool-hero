# Ray — History

## Learnings

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
