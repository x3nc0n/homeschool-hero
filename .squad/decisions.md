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

### Egon Dependabot Sweep (2026-05-09)
- **Author:** Egon
- **Context:** Eleven open Dependabot PRs remained after earlier CI failures. After the direct version-bump PRs landed, the remaining backend range-only PRs no longer merged cleanly and would have left CI install conflicts unless the pinned requirements files were aligned too.
- **Decision:** Merged #8, #9, #10, #12, #14, #15, and #20; closed #13 as a duplicate of #12; and applied a direct follow-up alignment on `main` for `pytest-asyncio`, `pydantic-settings`, and `APScheduler`, then closed #7, #11, and #16 as superseded.
- **Impact:** The Dependabot queue is clear, `pytest 9.0.3` plus `pytest-asyncio 1.3.0` are validated with `asyncio_mode = auto`, and CI dependency installs remain consistent because `requirements.txt`, `requirements-prod.txt`, and `backend/requirements-test.txt` now agree on shared package versions.

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

### Ray Azure Scaffold Decision (2026-05-09)
- **Author:** Ray
- **Context:** The Azure architecture doc labels the database subnet as a PostgreSQL private-endpoint subnet, but Azure Database for PostgreSQL Flexible Server private access is implemented through delegated subnet + private DNS wiring rather than a standalone private endpoint resource.
- **Decision:** In the initial `Spaidoso/homeschool-hero-azure` scaffold, model PostgreSQL private access with a delegated `db` subnet and the PostgreSQL private DNS zone, while keeping the reusable private-endpoint module for Blob, Key Vault, Redis, Azure OpenAI, and Document Intelligence.
- **Impact:** The scaffold stays aligned with the architecture's private-networking intent while remaining compatible with the supported Azure Flexible Server deployment model and allowing `az bicep build` validation to pass across the repo.

### User Directive: RBAC Hardening for OIDC and SAML (2026-05-14)
- **By:** John (via Copilot)
- **What:** RBAC model must be shored up for OIDC and SAML 2.0 authentication protocols. Likely applies to local auth too, but the complexity lives on the SSO protocol side (role extraction from tokens/assertions, mapping external roles to internal capabilities).
- **Why:** User request — captured for team memory.

### Egon RBAC Triage (2026-05-14)
- **Author:** Egon
- **Context:** Triaged RBAC gaps across local auth, OIDC, SAML 2.0, and bearer-token access without duplicating issue #97.
- **Decision:** Created 6 issues with dependency ordering:
  1. #98 — Define a unified RBAC model across local auth, OIDC, and SAML
  2. #99 — Add configurable external role mapping for IdP-authenticated users
  3. #100 — Extract and normalize RBAC claims from OIDC tokens
  4. #101 — Extract and normalize RBAC attributes from SAML assertions
  5. #102 — Build provider-agnostic RBAC dependencies and enforce 401/403 semantics
  6. #103 — Add JWT bearer token validation for API clients with shared RBAC enforcement
- **Dependency order:** #98 (unified model) → #99 (mapping config) → #100, #101 (external role extraction) → #102 (unified deps) → #103 (bearer token).
- **Notes:** #97 remains the Entra-specific contract and should be referenced, not duplicated. Main tension is reconciling `Admin/Teacher/Student` with existing `FamilyRole` + capability model. External role assertions fail closed when no valid mapping exists.
- **Impact:** Provides architectural structure for SSO integration work across all three protocol families.

### Egon RBAC Unified Model Architecture (2026-05-14)
- **Author:** Egon
- **Context:** Issue #98 defining the canonical role model and conflict-resolution rules for OIDC, SAML, and local auth.
- **Decision:** Keep `FamilyMembership` and `FamilyRole` as the persisted family-scoping model, add a normalized `AppRole` layer (`admin`, `teacher`, `student`) for OIDC/SAML/JWT claims, and keep capabilities as the canonical enforcement surface. `Admin` must not map to the current `parent` bundle; instead, split legacy `manage_family` into household-vs-platform capability buckets so SSO `Admin` stays IT-configuration-only while local-auth families remain backward compatible.
- **Key rules:** `FamilyRole`, `is_owner`, and `student_id` stay authoritative for family scope. IdP app roles stay authoritative for external-role intent. When they conflict, the narrower result wins. Local auth synthesizes app roles from stored family role to avoid breaking existing families.
- **Reference:** `docs/architecture/rbac-unified-model.md` (created by Egon during task execution).
- **Impact:** Provides canonical architecture for issue #98 implementation and downstream issues #99-#103.

### Winston RBAC Test Scaffolding (2026-05-14)
- **Author:** Winston
- **Context:** Egon defining the unified RBAC architecture; team needs executable test expectations in place now.
- **Decision:** Anchor provisional RBAC spec tests to provider-agnostic behavior rather than concrete implementation details. Cover the same access matrix for local sessions, OIDC, and SAML, plus role extraction, external role mapping, precedence conflicts, JWT bearer semantics, and backward compatibility with `FamilyRole` and cookie sessions. Keep the suite fully skipped until unified RBAC contracts land so it documents expectations without destabilizing CI.
- **Implementation:** 34 skipped test cases in `backend/tests/test_rbac_unified.py`.
- **Impact:** Egon and Ray have a concrete acceptance-test checklist for issues #97-#103 before implementation is complete. Winston can later replace skipped bodies with real setup/assertions without redefining the intended security behavior.

### Ray RBAC Implementation (2026-05-14)
- **Date:** 2026-05-14T08:57:23-05:00
- **Author:** Ray
- **Related issues:** #98, #99
- **Context:** The accepted unified RBAC architecture requires backend authorization to separate persisted family membership from provider-neutral application roles while preserving local-auth compatibility.
- **Decision:** Implement Phase 1 with a provider-neutral `AppRole` layer (`admin`, `teacher`, `student`), environment-driven external role mappings (`ROLE_MAPPING_ADMIN`, `ROLE_MAPPING_TEACHER`, `ROLE_MAPPING_STUDENT`), and effective capability calculation that combines family-role capabilities with app-role grants using narrower-wins precedence.
- **Details:** Keep `FamilyRole` canonical for invitations, ownership, and student scoping. Split legacy `manage_family` into `manage_household` and `manage_platform`, while preserving `manage_family` as a compatibility alias for existing route guards. Synthesize app roles for local auth from family roles to preserve current behavior. Accept multiple external aliases per app role through comma-separated settings and deny explicitly supplied unmapped external roles. Store normalized `app_roles` and computed `effective_capabilities` on `AuthSession` so route enforcement reads one effective capability set.
- **Impact:** Local cookie-session authorization remains backward compatible, external role normalization is configurable for upcoming OIDC/SAML extraction work, and future route migration can move from `manage_family` to explicit household/platform checks without breaking current callers.

### Ray OIDC/SAML Role Extraction (2026-05-14)
- **Date:** 2026-05-14T09:30:46-05:00
- **Author:** Ray
- **Related issues:** #100, #101
- **Context:** The unified RBAC model and configurable external role mapping already exist, but the OIDC and SAML login flows were still provisioning identities without extracting provider role evidence into normalized app roles.
- **Decision:** Extract external role evidence at the protocol boundary and store normalized app-role names on `ExternalIdentity.roles` before provisioning. For OIDC, read the configurable `OIDC_ROLES_CLAIM`, fall back to `OIDC_GROUPS_CLAIM` only when the roles claim is absent or empty, map fallback groups through `OIDC_GROUP_ROLE_MAP`, and ignore Entra groups overage indicators with a warning. For SAML, read the configurable `SAML_ROLE_ATTRIBUTE` first, then the common Microsoft and generic role/group attribute names, and normalize all collected values through the shared external-role mapping layer.
- **Impact:** The auth router can now pass provider-normalized app roles directly into session construction, preserving external `admin`/`teacher`/`student` intent through `AuthSession.app_roles`. Unknown external values stay fail-safe by logging and being skipped, while startup validation now catches invalid `OIDC_GROUP_ROLE_MAP` JSON before the app boots.

### Ray Provider-Agnostic RBAC Enforcement + JWT Bearer Validation (2026-05-14)
- **Date:** 2026-05-14T09:30:46-05:00
- **Author:** Ray
- **Related issues:** #102, #103
- **Context:** Unified RBAC architecture and local/OIDC/SAML role extraction exist, but route enforcement lacked provider-neutral gates and JWT bearer validation for stateless API clients.
- **Decision:** (1) Add explicit app-role dependencies: `require_admin()`, `require_teacher()`, `require_student()`, `require_any_role(*roles)`; (2) Resolve auth source: bearer token first (if `JWT_ENABLED`), then signed cookie; (3) Preserve 401 (missing/invalid credentials) vs 403 (valid auth, lacks required role); (4) JWT validation: symmetric `JWT_SECRET` or asymmetric `JWT_JWKS_URL` (5-min cache), validate issuer/audience/expiration/family; (5) Build bearer-backed `AuthSession` directly from claims, no session record required.
- **Impact:** Local, OIDC, SAML, and JWT bearer share same RBAC surface. Maintenance, backup, grading, curriculum, and read flows enforce app-role intent. Operators configure either `JWT_SECRET` or `JWT_JWKS_URL` when `JWT_ENABLED=true`.

### Tully JWT Bearer Security Hardening (2026-05-14)
- **Author:** Tully
- **Context:** Egon rejected PR #104 because bearer-token authorization trusted family context and owner status from JWT input instead of canonical family membership data.
- **Decision:** Rehydrate every bearer-backed family session from the database before authorization. Bearer requests now require an accepted `FamilyMembership` for the authenticated user and selected family, reject forged `X-Family-Id` values with 403, ignore `is_owner` claims in JWT payloads, and fail closed to `student_viewer` when family-role claims are absent. Remove the dead `_ROLE_CAPABILITIES` table so RBAC has one canonical capability source.
- **Impact:** JWT, OIDC, SAML, and local flows now follow the architecture rule that family scope and owner semantics are database-backed, while test coverage explicitly guards against family-header injection and owner-claim escalation.

## Governance

- All meaningful changes require team consensus
- Document architectural decisions here
- Keep history focused on work, decisions focused on direction
