# Egon — History

## Learnings

- 2026-05-09T15:00:00-05:00 — Cleared the remaining Dependabot backlog: merged #8, #9, #10, #12, #14, #15, and #20; closed #13 as a duplicate of #12; and closed #7, #11, and #16 after landing an equivalent dependency-alignment commit directly on `main`.
- 2026-05-09T15:00:00-05:00 — Verified that `pytest==9.0.3` and `pytest-asyncio==1.3.0` work with `asyncio_mode = auto`; CI also requires pinned `requirements.txt` versions to stay aligned with `backend/requirements-test.txt` because both files are installed in sequence.

- 2026-05-08T21:57:09.039-05:00 — Drafted the next-phase feature plan covering scheduled NAS backups, GitHub security scanning, scan-driven issue automation, guarded Squad auto-remediation, and the self-hosted v1.0 roadmap.
- 2026-05-08T21:57:09.039-05:00 — Replaced the conservative phased plan with a production-ready functional-area execution plan covering multi-family tenancy, RBAC, academic operations, compliance, data portability, graceful degradation, and self-hosted operations.
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

### Phase 3 Planning Complete (2026-05-08T22:18:50Z)
- Comprehensive production plan finalized: 40 structured todos across 9 functional areas
- Functional areas: multi-family tenancy, RBAC, academic operations, compliance, data portability, graceful degradation, self-hosted operations, performance optimization, security hardening
- Dependency graph validated; rollout strategy defined per area
- Orchestration log recorded: Production-ready build plan ✅ COMPLETE
- Team aligned on post-MVP direction; parallel execution model ready for phase 3

### Security Issue Triage (2026-05-09T07:14:47Z)
- Triaged 4 open security issues with squad member assignment
- **Decision:** Backend service security issues → Ray; test code quality issues → Winston (separation of concerns)
- #22 (insecure TLS protocol in backend/services/health.py) → squad:ray ✓
- #23, #24, #25 (redundant assignments in backend/tests/contracts.py) → squad:winston ✓
- Rationale: Ray owns production code hardening; Winston owns test code quality and maintainability

### Team Architecture Sync (2026-05-09T12:25:20Z)
- Ray completed 9 architectural decisions: AG-02 (submission versioning), AG-03 (grading hardening), AG-04 (gradebook model), AG-06 (performance strategy), AM-05 (attendance migration), CI fix (ROLLBACK_NOTES + TLS policy), DM-02 (exports), DM-03 (backups), IO-04 (observability).
- Ray fixed 3 CI root causes: 16 migration ROLLBACK_NOTES blocks, TLS security (minimum TLSv1_2), removed redundant test definitions. 210 tests passing.
- Venkman fixed ESLint 9.x peer conflict; 3 architectural decisions: RC-01 (report cards), UX-03 (search), ESLint pin decision.
- Winston submitted auto-patch policy decision (SD-04): limited auto-remediation to direct dependencies, human review for high-risk findings.
- All 14 inbox decisions merged to active registry; clear execution path defined for post-MVP production features.

### Dependency Update Cycle (2026-05-09T12:44:00Z)
- **Egon:** Reviewed and merged all 6 CI action bump PRs (#1–6) with clean version bumps in GitHub Actions workflows
- **Ray:** Reviewed 10 backend dependency PRs; auto-merge enabled on 8 (#7, #8, #10–12, #14–16); held #9 (pytest 9.x major breaking changes requiring migration) and #13 (duplicate of #12)
- **Venkman:** Reviewed 5 frontend dependency PRs; auto-merge on #20 (@types/node patch bump); closed #17–18 (React 19 major), #19 (router v7 major), #21 (tailwind v4 major) as requiring planned migration work
- **Coordinator:** Closed security issues #22–25 (fixes already on main from prior round)
- **Session outcome:** Dependency updates processed per team policy; major bumps held pending migration planning
