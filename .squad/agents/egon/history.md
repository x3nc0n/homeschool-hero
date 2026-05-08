# Egon — History

## Learnings

- Project: homeschool-hero — open-source homeschool platform for families
- User: John — mildly IT-inclined parent audience
- Core features: assignment tracking, PDF/photo upload, quizzes, tests, grade tracking, auto-grading with human review
- Deployment: Docker or self-hosted web server
- Students don't use the platform directly — they complete work on paper and upload scans/photos
- Target audience: parents managing homeschool curriculum
- **GitHub Repository:** https://github.com/x3nc0n/homeschool-hero

### Architecture Decisions (2026-05-08)
- **Stack:** Python 3.12 + FastAPI (backend), React 18 + Vite + shadcn/ui (frontend), PostgreSQL 16 (DB)
- **ORM:** SQLAlchemy 2.0 + Alembic migrations
- **OCR:** Tesseract (pytesseract) — free, local, no API keys
- **AI Grading:** Ollama (default, local) with optional OpenAI fallback
- **Task Queue:** DB-based job table (no Redis/Celery for MVP)
- **Auth:** Single family password, bcrypt hash, session cookie
- **Deployment:** docker-compose with 3 services: app, db, ollama
- **Confidence threshold:** 0.8 for auto-approve vs human review
- **File storage:** Local filesystem via Docker volume at /data/uploads/
- **Key file:** `docs/architecture.md` — source of truth for MVP implementation
- **Work breakdown:** 25 tasks across Ray (backend), Venkman (frontend), Winston (tests)

### Phase 1 Completion (2026-05-08T22:04:55Z)
- All four agents completed MVP workstreams in parallel
- Ray: Backend foundation (CRUD APIs, auth, migrations) ✓ 33 tests passing
- Venkman: Frontend SPA (10 pages, protected routes) ✓ Build passing
- Winston: Test infrastructure (async pytest, mocked dependencies) ✓ 33 tests passing
- Scribe archived decisions.md (4 entries merged, inbox cleared)
- Next phase: background job queue (tasks 17-19), integration tests (23-24)
