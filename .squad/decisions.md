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

### Security Issue Triage (2026-05-09)
- **Author:** Egon
- **Decision:** Assigned 4 open security issues using role-based routing: real production security vulnerabilities → Ray (backend code owner); code quality issues in test code → Winston (test maintainability).
- **Assignments:** #22 (Insecure TLS, backend/services/health.py:110) → Ray; #23-25 (Redundant assignments, backend/tests/contracts.py) → Winston.
- **Impact:** Clear role boundaries enforce accountability; appropriate expertise applied to each issue; consistent routing for future security/quality triage.

### Ray AG-02 Submission Versioning (2026-05-09)
- **Author:** Ray
- **Context:** Submission uploads need deterministic storage, resubmission history, and single current version controlling grading/review.
- **Decision:** Keep version history on `submissions` table with `submission_version`, `parent_submission_id`, and `is_current`; store files under family/student/assignment/submission folders; only grade/review on current version.
- **Impact:** Backup/export layout stays predictable, prior uploads remain viewable, grading logic safely ignores superseded work.

### Ray AG-03 Grading Hardening (2026-05-09)
- **Author:** Ray
- **Context:** Grading pipeline needs OCR/AI outage resilience, operator state visibility, and answer-key-assisted scoring.
- **Decision:** Keep grading orchestration on `grading_jobs` with validated status machine; store answer keys separately per assignment; combine answer-key scoring with AI confidence; route timeout/circuit-breaker failures to manual review.
- **Impact:** Resilient grading behavior, precise pipeline progress visibility, audit records capture both automated and human steps.

### Ray AG-04 Gradebook Model (2026-05-09)
- **Author:** Ray
- **Context:** Weighted gradebooks need configurable category weights, drop-lowest rules, letter grades, GPA mapping, subject-specific modes.
- **Decision:** Keep `Assignment` as record, add subject-level grading mode (`points` vs `percentage`), persist `GradeCategory` and `GradeScale` per family, calculate running grades on demand via service.
- **Impact:** Existing grading CRUD stays backward compatible, families can override scales per subject, gradebook views stay current.

### Ray AG-06 Performance Strategy (2026-05-09)
- **Author:** Ray
- **Context:** Gradebook, compliance, pacing endpoints recomputed expensive payloads; assignment/grade search lacked indexes.
- **Decision:** Use app-local TTL caching with explicit prefix invalidation, add conditional GET headers, ship composite/partial/PostgreSQL full-text indexes aligned to dominant query patterns.
- **Impact:** Hot read paths cheaper without changing API semantics; stale results bounded by explicit invalidation + TTLs; production gains new index coverage via Alembic.

### Ray AM-05 Attendance Migration Graph (2026-05-09)
- **Author:** Ray
- **Context:** Parallel wave work created multiple `20260510_001500` migrations, blocking `alembic upgrade head`.
- **Decision:** Assign unique revision IDs to parallel migrations (notifications, submission_versioning, attendance_tracking); add `20260510_001600` merge revision for convergence.
- **Impact:** Operators use `upgrade head` without manual targeting; future parallel migrations remain unblocked.

### Ray CI Fix (2026-05-09)
- **Author:** Ray
- **Decision:** Four policies: (1) All migrations require `ROLLBACK_NOTES` string-literal block; (2) No-op downgrades exempt only merge revisions; (3) All SSL contexts set `context.minimum_version = ssl.TLSv1_2`; (4) No duplicate function definitions in test helpers.
- **Impact:** 210 backend tests pass, migration lint passes with 0 errors, CI green on next push. All new migrations must follow ROLLBACK_NOTES policy.

### Ray Docker Capability Fix (2026-05-09)
- **Author:** Ray
- **Context:** `docker compose up` failed because hardened shared defaults dropped all Linux capabilities, blocking PostgreSQL from creating `PGDATA` on first boot. Clean Postgres validation exposed migration issues reproducible only on PostgreSQL.
- **Decision:** Keep shared hardening defaults, add minimal `cap_add` permissions only to `db` service, require clean PostgreSQL compose validation when Docker or migration changes touch startup. Migration scripts must stay PostgreSQL-safe for enum creation, seed inserts, and expression indexes.
- **Impact:** Local compose startup maintains security posture without breaking database initialization; backend changes now pass real PostgreSQL boot path instead of SQLite-only validation.

### Ray DM-02 Export Packages (2026-05-09)
- **Author:** Ray
- **Context:** DM-02 needs JSON, CSV, ZIP export packages for dataset representation, spreadsheet review, portability.
- **Decision:** Multi-entity CSV exports as ZIP bundles (one CSV per entity + metadata); ZIP exports add full JSON snapshot, PDFs, attachments.
- **Impact:** Families choose lightweight tabular export without losing structure; full ZIP remains portable.

### Ray DM-03 NAS Backup Runtime (2026-05-09)
- **Author:** Ray
- **Context:** DM-03 needs scheduled NAS backups over SMB/NFS; Docker containers can't mount shares without host setup.
- **Decision:** Treat `BACKUP_TARGET` as container path, add `BACKUP_MOUNT_SOURCE` for Docker bind mount, validate writability on startup, auto-enable restic when binary and `BACKUP_ENCRYPTION_KEY` present.
- **Impact:** Operators point Docker at host-mounted NAS, backups fail fast when missing/read-only, runtime falls back to plain copies.

### Ray IO-04 Observability Surfaces (2026-05-09)
- **Author:** Ray
- **Context:** Operators need basic troubleshooting without external stack.
- **Decision:** Standard Python logging with JSON output outside tests, correlation IDs in middleware, authenticated `/api/metrics` endpoint, recent activity in dashboard.
- **Impact:** Request/grading/backup activity traced with consistent fields; slow endpoints and failed jobs visible in logs and UI.

### Venkman ESLint 9.x Pin (2026-05-09)
- **Author:** Venkman
- **Context:** CI failing with ERESOLVE peer-dependency conflict; `eslint-plugin-jsx-a11y@6.10.2` excludes `eslint@^10`.
- **Decision:** Downgrade `eslint` and `@eslint/js` from `^10.x` to `^9.9.0`; ESLint 9.9.0 has needed flat-config helpers.
- **Impact:** Frontend CI unblocked, `npm ci` resolves cleanly, `npm run lint` and `npm run build` pass.

### Venkman RC-01 Report Cards (2026-05-09)
- **Author:** Venkman
- **Context:** RC-01 needs printable report cards reusing AG-04 gradebook and AM-05 attendance without separate reporting pipeline.
- **Decision:** Generate from live data per grading period, persist drafts/finals as `report_cards` + `report_card_entries`, use ReportLab for deterministic server-side PDF rendering.
- **Impact:** Families get draft/final cards and printable PDFs from one backend workflow; tests validate PDF bytes plus immutability.

### Venkman UX-03 Unified Search (2026-05-09)
- **Author:** Venkman
- **Context:** UX-03 needs one search experience across family-scoped entities while supporting SQLite tests and RBAC.
- **Decision:** Normalize search behind `/api/search` returning entity type, title, snippet, link, timestamps, facet counts. Use PostgreSQL full-text in prod, SQLite-compatible case-insensitive in tests, enforce family/student scope before return.
- **Impact:** Frontend relies on one consistent API, production search scales with indexes, tests stay deterministic.

### Winston SD-04 Auto-Patch Policy (2026-05-09)
- **Author:** Winston
- **Context:** Security sync creates normalized GitHub issues; SD-04 adds triage and patch generation.
- **Decision:** Limit auto-remediation to direct dependency version bumps. Route CodeQL, base-image, transitive, ambiguous findings to needs-human-review. Require CI gate pass before PR opening, never auto-merge critical/non-dependency without sign-off.
- **Impact:** Clear audit trail, low-risk fixes proposed quickly, reviewers keep control over high-risk remediation.

### Ray CI Fixes (2026-05-09)
- **Author:** Ray
- **Context:** Main branch CI still failed after code tests passed because Gitleaks flagged a high-entropy sample `SECRET_KEY` in `.env.example`, and Trivy could not find the locally built `homeschool-hero:ci` image after Buildx setup.
- **Decision:** Standardize example secrets on explicit allowlisted placeholder values (for example `change-me-in-production`) and require `docker build --load` in CI jobs that build with Buildx and then hand the image to local-daemon tools such as Trivy.
- **Impact:** Secret scan and container scan stay aligned with policy intent, and future CI edits should preserve placeholder-safe sample values plus local image loading whenever downstream steps expect `docker images` visibility.

## Governance

- All meaningful changes require team consensus
- Document architectural decisions here
- Keep history focused on work, decisions focused on direction
