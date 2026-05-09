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
- 2026-05-09T23:39:29-05:00 — Completed AM-02 daily scheduling and planner views: added family-scoped schedule, schedule block, and schedule override models plus Alembic migration; implemented schedule CRUD, recurring/override agenda and week APIs, conflict detection, and planner UI with student selector, weekly grid, daily agenda, block editor, and override controls.
- 2026-05-09T23:39:29-05:00 — Verified AM-02 with `cd backend && python -m pytest -q` (98 passed, 2 skipped), `cd frontend && npm run lint && npm run build` (one pre-existing CalendarPage hook warning), and `python -m alembic -c backend\\alembic.ini upgrade head` against SQLite test settings.
- 2026-05-08T23:52:13-05:00 — Completed AG-01 assignment domain upgrade: expanded assignments with category/grading period/weight/max score/recurrence/rubric/attachments/history metadata, added per-student AssignmentTarget records with status tracking, and wired submission/grade flows to update target progress.
- 2026-05-08T23:52:13-05:00 — Verified AG-01 with `cd backend && python -m pytest -q` (94 passed, 2 skipped) and `cd frontend && npm run build`; assignment CRUD/filtering/backward-compat regression coverage now includes multi-student targets, pagination, grading periods, and target status sync.
- 2026-05-09T04:58:00-05:00 — Completed IO-04 observability surfaces: added structured backend logging with correlation IDs and request timing, optional `/api/metrics` monitoring, grading/backup lifecycle logging, and a dashboard activity + system health summary widget.
- 2026-05-09T04:58:00-05:00 — Verified IO-04 with `cd backend && python -m pytest -q` (94 passed, 2 skipped) plus `cd frontend && npm run build`; added regression coverage for correlation IDs, request logging, slow-request warnings, and metrics payloads.

### Wave 3 Summary (2026-05-08T22:32:57Z)
- CP-04: Audit logging with immutable append-only events (commit 5c359f9) ✅ COMPLETE
- AM-01: Academic calendar with date-based storage (commit 9460c72) ✅ COMPLETE
- CP-05: OIDC/SAML auth with email-first identity matching (commit 00d67d4) ✅ COMPLETE
- IO-01: Production Docker with optional service profiles (commit c1790b2) ✅ COMPLETE
- SD-01: Application hardening with CSRF/rate-limiting (commit 1fad126) — 84 tests passing ✅ COMPLETE
- All 5 Wave 3 deliverables merged; decisions recorded in decisions.md; orchestration logs finalized
- 2026-05-09T23:39:29-05:00 — Completed AM-03 curriculum packages + resource library: added curriculum package/unit/lesson/resource persistence with Alembic migration, family-scoped CRUD/clone/link APIs, and tutor-capable curriculum/resource management UI pages plus clone workflow.
- 2026-05-09T23:39:29-05:00 — Verified AM-03 with cd backend && python -m pytest -q (98 passed, 2 skipped), targeted curriculum/calendar/authorization coverage, and cd frontend && npm run lint && npm run build; frontend lint still reports one pre-existing CalendarPage hook warning outside AM-03.
- 2026-05-10T05:20:00-05:00 — Completed AM-05 attendance tracking: added attendance record/excuse models, family-scoped attendance APIs for daily bulk entry, instructional hours, excuses/approvals, day-week-term-year summaries, and school-year hour totals with audit logging on attendance edits.
- 2026-05-10T05:20:00-05:00 — Delivered attendance UI surfaces: new Attendance page for bulk status marking, color-coded monthly attendance calendar, instructional time logging, excuse attachment/approval workflows, plus dashboard attendance snapshot cards for rate and hours.
- 2026-05-10T05:20:00-05:00 — Verified AM-05 with `cd backend && python -m pytest -q` (115 passed, 1 skipped), `cd backend && python -m pytest tests\\test_attendance.py -q` (3 passed), `python -m alembic -c backend\\alembic.ini upgrade head` against async SQLite test settings, and `cd frontend && npm run lint && npm run build`; frontend lint still reports the pre-existing CalendarPage hook warning outside attendance changes.
- 2026-05-09T05:32:57-05:00 — Completed AG-02 submission hardening: enforced family-scoped upload validation for PDF/JPEG/PNG/HEIC/TIFF/WEBP with 25 MB defaults, deterministic storage paths plus file metadata capture, and submission version history with preserved prior versions and current-version grading rules.
- 2026-05-09T05:32:57-05:00 — Verified AG-02 with python -m pytest backend\tests -q (115 passed, 1 skipped), python -m alembic -c backend\alembic.ini upgrade head, and cd frontend && npm run lint && npm run build; frontend lint still reports one pre-existing CalendarPage hook warning outside AG-02.

- 2026-05-10T06:05:00-05:00 — Completed AM-04 lesson plans and pacing guides: added family-scoped lesson plan and pacing target APIs with curriculum-driven schedule generation, bulk status updates, pacing calculations, assignment generation, and the supporting Alembic migration.
- 2026-05-10T06:05:00-05:00 — Delivered lesson planning frontend surfaces: new Lesson Plans page, navigation entry, dashboard pacing snapshot, and API/type wiring; verified with cd backend && python -m pytest -q (119 passed, 1 skipped), cd frontend && npm run build, and python -m alembic -c backend\\alembic.ini upgrade head.
- 2026-05-09T00:40:13-05:00 — Completed DM-01 import ecosystem: added family-scoped import jobs, CSV/JSON validation + execution APIs, dry-run error reporting, progress tracking, template downloads, and audit-logged bulk import support for students, subjects, assignments, grades, attendance, and curriculum packages.
- 2026-05-09T00:40:13-05:00 — Delivered Imports frontend workflow with upload, dry-run validation, progress polling, template links, and row-level fix suggestions; verified with cd backend && python -m pytest -q (133 passed, 1 skipped) and cd frontend && npm run build.
- 2026-05-09T00:40:13-05:00 — Completed AG-03 grading hardening: added answer keys with family-scoped assignment APIs, deterministic answer-key comparison, grading job status-machine tracking, retry/backoff + timeout handling, AI circuit-breaker fallback, and per-step grading persistence for OCR/AI/manual review data.
- 2026-05-09T00:40:13-05:00 — Delivered grading UX updates for answer-key editing, upload progress/status visibility, and richer review-queue overrides/confidence details; verified with `cd backend && python -m pytest -q` (133 passed, 1 skipped), `cd frontend && npm run build`, and `DATABASE_URL=sqlite+aiosqlite:///./backend/.pytest-state/alembic-validate.db python -m alembic -c backend\\alembic.ini upgrade head`.
- 2026-05-09T00:41:00-05:00 — Re-verified DM-01 import ecosystem on main: `cd backend && python -m pytest -q` passed (133 passed, 1 skipped) and `cd frontend && npm run build` passed after confirming the import workflows, templates, validation, and progress UI remained green.
- 2026-05-09T01:11:50-05:00 — Completed AG-05 review workflow and collaboration: added dedicated review item/comment persistence with Alembic migration, family-scoped `/api/reviews` queue/detail/action/bulk APIs, reviewer assignment/comment threads, notification hooks, and audit coverage for review actions.
- 2026-05-09T01:11:50-05:00 — Delivered updated review UI with sortable/filterable queue, batch approve/assign flows, dedicated detail page, side-by-side submission/OCR review, approval/reject/regrade controls, and comment collaboration; verified with `cd backend && python -m pytest -q` (145 passed, 1 skipped), `cd frontend && npm run build`, and `python -m alembic -c backend\\alembic.ini upgrade head` against SQLite test settings.
- 2026-05-10T01:35:00-05:00 — Completed AM-06 state compliance framework: added family/state-aware compliance rules + status models, seeded TX/CA/VA/NY/FL rules via Alembic, built backend compliance evaluation/notification APIs, and delivered compliance dashboard plus family-state/custom-rule settings UI.
- 2026-05-10T01:35:00-05:00 — Verified AM-06 with `cd backend && python -m pytest -q` (145 passed, 1 skipped), `cd frontend && npm run build`, targeted `cd backend && python -m pytest tests\\test_compliance.py -q` (5 passed), and fresh SQLite migration validation via `DATABASE_URL=sqlite+aiosqlite:///./backend/.pytest-state/alembic-compliance-validate.db python -m alembic -c backend\\alembic.ini upgrade head`.
- 2026-05-10T01:11:50-05:00 — Completed AG-04 assessments and gradebook: added family-scoped grade scales, weighted grade categories with drop-lowest support, subject grading modes, and a new gradebook API for detailed views, summaries, trends, recalculation, and category/scale management.
- 2026-05-10T01:11:50-05:00 — Delivered gradebook frontend updates: subject settings now edit weighted categories and grading mode, family settings manage grade scales, and the gradebook page shows subject summary cards, GPA, category-grouped assignments, and trend charts.
- 2026-05-10T01:11:50-05:00 — Verified AG-04 with `cd backend && python -m pytest -q` (145 passed, 1 skipped), `DATABASE_URL=sqlite+aiosqlite:///./backend/.pytest-state/alembic-gradebook.db python -m alembic -c backend\\alembic.ini upgrade head`, and `cd frontend && npm run build`.
- 2026-05-09 — Completed AG-06 assignment and grade performance optimization: added composite/partial/full-text indexes plus Alembic migration, introduced TTL cache + conditional GET handling for gradebook/compliance/pacing, removed critical lazy-load/N+1 regressions, and standardized pagination for grades/submissions/history/notifications.
- 2026-05-09 — Verified AG-06 with `cd backend && python -m pytest -q` (152 passed, 1 skipped) and `cd frontend && npm run build`; added regression coverage for cache invalidation, index presence, and pagination edge cases.
- 2026-05-10T02:07:44-05:00 — Completed RC-02 transcript generation: added transcript/transcript-entry models + Alembic migration, family-scoped transcript generation/detail/list/update/finalize/PDF APIs, cumulative and weighted GPA calculations with honors/AP credit weighting, and transcript PDF output suitable for official records.
- 2026-05-10T02:07:44-05:00 — Delivered transcript frontend workflow with transcript list/detail screens, GPA summary cards, draft editing for credits/honors/AP/course labels, PDF export, and draft-to-final controls; verified with `cd backend && python -m pytest -q` (158 passed, 1 skipped), `cd backend && python -m pytest tests\\test_transcripts.py -q` (3 passed), `cd frontend && npm run build`, and `DATABASE_URL=sqlite+aiosqlite:///./backend/.pytest-state/alembic-transcripts-validate.db python -m alembic -c backend\\alembic.ini upgrade head`.
- 2026-05-09T08:35:00-05:00 — Completed IO-05 TLS/maintenance operations hardening: added backend maintenance-mode persistence + admin APIs, scheduled maintenance enforcement with admin bypass, HTTPS redirect/HSTS controls, Nginx TLS configs, Compose TLS override, self-signed cert generation script, and maintenance/TLS operator docs.
- 2026-05-09T08:35:00-05:00 — Delivered maintenance-aware frontend behavior with a friendly maintenance page, Family Settings maintenance controls, and dashboard TLS indicators; verified with `cd backend && python -m pytest -q` (181 passed, 1 skipped), `cd frontend && npm run build`, and `DATABASE_URL=sqlite+aiosqlite:///./backend/.pytest-state/alembic-maintenance-validate.db python -m alembic -c backend\\alembic.ini upgrade head`.
- 2026-05-10T07:45:00-05:00 — Completed DM-02 export and portability packages: added export jobs with Alembic migration, family-scoped `/api/exports` create/status/download/list/delete APIs, JSON/CSV/ZIP packaging for full/incremental/entity exports, and self-contained bundles that include metadata, tabular exports, PDFs, and attachment files.
- 2026-05-10T07:45:00-05:00 — Delivered Exports UI with format/entity/date selection, export history, processing status, secure download/delete actions, and an Export Everything family-backup flow; verified with `cd backend && python -m pytest -q` (162 passed, 1 skipped), `python -m alembic -c backend\\alembic.ini upgrade head` against SQLite validation settings, and `cd frontend && npm run build`.
- 2026-05-10T08:30:00-05:00 — Completed DM-03 backups to NAS: added backup jobs with Alembic migration, family-scoped `/api/backups` trigger/history/detail/config/status APIs, startup NAS mount validation, cron-based scheduling, SQLite/pg_dump database capture, uploads copy, DM-02 export bundling, optional restic snapshots, and backup success/failure notifications.
- 2026-05-10T08:30:00-05:00 — Delivered Backup Settings UI with NAS/restic schedule status, manual backup trigger, and backup history; updated Docker backup profile to run the Python backup worker against a bind-mounted backup path; verified with `cd backend && python -m pytest -q` (167 passed, 1 skipped), `python -m alembic -c backend\\alembic.ini upgrade head` against SQLite validation settings, and `cd frontend && npm run build`.
- 2026-05-09T01:50:00-05:00 — Completed IO-02 health checks and status center: added health/status regression coverage, Docker Compose probing via `/api/health`, and a new Status Center page with live service indicators, backup visibility, disk usage, uptime/version data, and 30-second refresh.
- 2026-05-09T01:50:00-05:00 — Verified IO-02 with `cd backend && python -m pytest -q` (181 passed, 1 skipped) and `cd frontend && npm run build`.

- 2026-05-10T08:20:00-05:00 — Completed DX-01 OpenAPI and integration docs: added enriched /api/openapi.json metadata with grouped tags, generated examples, standard auth/error documentation, Swagger UI at /api/docs, ReDoc at /api/redoc, and new integration/development guides plus README/environment reference refresh.
- 2026-05-10T08:20:00-05:00 — Verified DX-01 with cd backend && python -m pytest -q (167 passed, 1 skipped) and cd frontend && npm run build; also hardened export attachment path resolution so the full backend suite stays green while validating the new API docs surfaces.

- 2026-05-09T03:15:16-05:00 — Completed DM-04 restore drills and retention policies: added restore validation/execution/selective services and `/api/restore` endpoints, safety snapshots + restore notifications/audit logging, retention runtime/cleanup controls, and backup manifest/retention updates needed for restore compatibility.
- 2026-05-09T03:15:16-05:00 — Delivered restore management UI with backup validation, confirmation-gated full/selective restore workflows, retention settings, cleanup controls, and progress feedback; verified with `cd backend && python -m pytest tests\\test_restore.py tests\\test_backups.py -q` (7 passed) plus `cd frontend && npm run build`, while full `cd backend && python -m pytest -q` still reports the pre-existing export download failures seen outside DM-04.
- 2026-05-09T04:19:50-05:00 — Completed DX-02 i18n foundation: wired react-i18next/i18next with English fallback + partial Spanish resources, localized the main app shell/dashboard/auth/settings chrome, added a persisted language selector, and started backend locale negotiation with Accept-Language parsing plus keyed/localized error payloads and response locale/date-format headers.
- 2026-05-09T04:19:50-05:00 — Verified DX-02 with cd frontend && npm run test:i18n, cd frontend && npm run build, and cd backend && python -m pytest -q (187 passed, 1 skipped).
