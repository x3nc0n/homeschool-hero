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

### User Directive: Cross-Team Workflow (2026-05-15T07:10:38-05:00)
- **By:** John (via Copilot)
- **What:** The infra team (Spava-Corp) will open issues on x3nc0n/homeschool-hero that this squad must monitor and address. This squad can open issues on `Spava-Corp/homeschool-hero-azure` for them to address (e.g., infrastructure/deployment issues like #110).
- **Infra repo:** `Spava-Corp/homeschool-hero-azure`
- **Why:** User request — captured for team memory. Establishes cross-team workflow between app team (this repo) and infra team.

### Egon Breakglass Semantics Authority (2026-05-15T07:43:55-05:00)
- **Author:** Egon
- **Issue:** PR #109 review
- **Context:** The auth capabilities API now reports provider visibility separately from `AUTH_PROVIDER`, and `AUTH_BREAKGLASS_LOCAL` is presented as the switch that keeps local login available as an IdP-down fallback. In the reviewed implementation, `AUTH_BREAKGLASS_LOCAL=false` removes local auth from capability reporting, but the backend login route still accepts local credentials unconditionally.
- **Decision:** `AUTH_BREAKGLASS_LOCAL` must have one authoritative meaning across UI, backend enforcement, and operator documentation. Either the backend must reject `POST /api/auth/login` when local auth is disabled, or the capabilities surface must continue to report local auth as enabled whenever the backend route remains reachable. Do not ship a configuration flag that only hides the button while leaving the credential path active.
- **Impact:** Keeps SSO deployments honest: operators can rely on the config they set, audit expectations stay accurate, and there is no hidden mismatch between reported auth posture and actual reachable login paths. Aligns with the dual-axis RBAC model by preserving local-auth compatibility only when explicitly intended, not as an undocumented side channel.

### Egon PR #106 Review — Entra ID RBAC Middleware (2026-05-14T18:46:37-05:00)
- **Author:** Egon
- **PR:** #106 (feat(auth): Entra ID RBAC middleware, authored by Tully)
- **Verdict:** ✅ APPROVED
- **Context:** Adds Entra-specific bearer token validation: `tid` enforcement, v2.0 issuer contract, `roles` claim as authoritative for RBAC, groups overage safe handling, and OIDC identity resolution for DB family rehydration.
- **Security findings:** All fail-closed. Cross-tenant tokens rejected at 401. Groups never used for RBAC decisions. DB membership is always rehydrated — token claims cannot escalate privileges. Startup validation prevents misconfigured Entra deployments.
- **Impact:** Entra ID bearer-token API access is production-ready once merged. Teams using Entra can configure `JWT_TENANT_ID` to enable tenant-scoped validation.

### Ray Multi-Provider Capabilities (2026-05-15T07:10:40.494-05:00)
- **Author:** Ray
- **Context:** Homeschool Hero already supports local auth, OIDC, and SAML, plus a breakglass local-login path, but the capabilities payload still treated `AUTH_PROVIDER` as both the primary flow and the only visible external provider. That made the frontend hide configured secondary providers and left the auth capability contract out of sync with the actual multi-provider backend behavior.
- **Decision:** Treat `AUTH_PROVIDER` as the primary/default login flow only. Compute provider visibility independently: expose OIDC when `OIDC_CLIENT_ID` is present, expose SAML when its required metadata/entity/ACS settings are present, and keep local auth available by default through `AUTH_BREAKGLASS_LOCAL=true` while allowing operators to disable that fallback explicitly.
- **Impact:** The frontend can render all configured login options without losing the existing auth contract shape, while the backend still has a clear primary-provider concept for default UX. Multi-provider deployments now fail fast on incomplete secondary-provider config, and local breakglass visibility lines up with backend login enforcement instead of being a UI-only flag.

### Tully Breakglass Local Login (2026-05-15T07:10:40.494-05:00)
- **Author:** Tully
- **Context:** Homeschool Hero now supports OIDC and SAML alongside local auth, but operators still need a fail-safe path when an external identity provider is unavailable. The fallback must not bypass the unified RBAC model or silently turn protocol failures into backend 500s.
- **Decision:** Keep the existing local password login route available for pre-existing database accounts even when `AUTH_PROVIDER` is set to `oidc` or `saml`, and treat `AUTH_BREAKGLASS_LOCAL=true` as the operator signal to audit those successful local sign-ins with a WARNING log. For OIDC, convert callback token-exchange and ID-token parsing failures into user-safe login redirects via `/login?error=...` instead of surfacing server errors.
- **Impact:** Operators have an auditable breakglass path during IdP outages without granting any new roles or family scope beyond what the database already stores for the user. End users also get actionable OIDC failure feedback on the login screen instead of an opaque 500 response.

### Tully Entra RBAC Middleware (2026-05-14T18:25:38.883-05:00)
- **Author:** Tully
- **Issue:** #97
- **Context:** Production bearer-token auth needs to consume Microsoft Entra ID access tokens without bypassing the unified RBAC model or the database-backed family-scope rules added in PR #104.
- **Decision:** Keep the existing JWT/JWKS validation path, but add Entra-specific constraints on top of it: require `JWT_TENANT_ID`, validate the Entra `tid` claim, and require the configured issuer to match the tenant-scoped `https://login.microsoftonline.com/<tenant-id>/v2.0` format. For bearer sessions, treat the Entra `roles` claim as the only RBAC source of truth, treat `groups` as optional supporting data with overage-safe parsing, and resolve the local user through linked OIDC `external_id` first with normalized email fallback before rehydrating the selected `FamilyMembership` via `X-Family-Id`.
- **Impact:** The app can now accept Entra-issued API tokens without adding group-ID coupling or trusting token-supplied family-scope data. Operators get startup validation for tenant misconfiguration, and the test suite now covers tenant mismatch, OIDC external-ID resolution, and groups-overage behavior.

### Tully Frontend Auth Fixes (2026-05-14T22:20:11.663-05:00)
- **Author:** Tully
- **Issue:** #107
- **Context:** PR #108 exposed drift between backend auth-session serialization and the frontend capability-first auth layer. The SPA had to fall back to legacy RBAC synthesis because `/api/auth/me` omitted canonical `app_roles` and `effective_capabilities`, and that fallback over-granted `manage_security` to non-owner parents.
- **Decision:** Treat the backend auth session payload as the canonical RBAC contract for the frontend: always serialize `app_roles` and `effective_capabilities` from `AuthSession`, keep `manage_security` owner-parent only in any legacy fallback, and promote `view_own_progress` into the backend capability enum so student-facing route guards reference a real server-defined permission.
- **Impact:** Frontend gating now consumes the same RBAC data the backend enforces, reducing dead fallback paths and preventing UI exposure that contradicts server authorization. Student progress checks also have an explicit backend capability, which keeps the dual-axis RBAC model expressive without inventing client-only permissions.

### Tully PyJWT crit Header Rejection (2026-05-15T07:43:55-05:00)
- **Author:** Tully
- **Issue:** #105 (CVE-2026-32597)
- **Context:** GitHub issue #105 reports CVE-2026-32597 against PyJWT 2.10.1. The bearer-token path in `backend/services/auth_jwt.py` validates externally supplied JWTs, so unknown `crit` header extensions must be rejected fail-closed.
- **Decision:** Align `requirements.txt`, `requirements-prod.txt`, and `backend/requirements-test.txt` on PyJWT 2.12.0 and explicitly reject any bearer token that includes a `crit` header because homeschool-hero does not define any supported critical JWT extensions.
- **Impact:** Production, CI, and local test environments stop installing the vulnerable PyJWT release, and bearer auth remains fail-closed even if a future dependency drift reintroduces older library behavior.

### Venkman Frontend Entra Auth Gating (2026-05-14T21:02:10.172-05:00)
- **Author:** Venkman
- **Issue:** #107
- **Context:** The backend session model now carries AppRole and effective capability data for Entra/OIDC sign-in, but the SPA still gated routes and navigation by raw `FamilyRole` string checks. That would drift from backend authorization rules, especially for Entra-issued sessions whose access is determined by `app_roles` and `effective_capabilities`.
- **Decision:** Make the frontend auth layer capability-first. `AuthContext` should normalize `app_roles` and `effective_capabilities` into shared `hasRole`/`hasCapability` helpers, then synthesize legacy AppRole/capability fallbacks from `membership.role` when local auth sessions do not include RBAC fields. Route guards, navigation, and tab visibility should consume those helpers so OIDC and local auth follow the same UI gating rules.
- **Impact:** Frontend access checks now match the backend RBAC shape without requiring MSAL or a client-side OAuth implementation. Local email/password installs keep working because FamilyRole-based sessions are translated into the same helper API, reducing future drift between server auth decisions and visible UI affordances.

### Egon RBAC Hierarchy Redesign (2026-05-22T15:25:42.606-05:00)
- **Author:** Egon
- **Requested by:** John
- **Context:** The current unified RBAC implementation does not match the product hierarchy John wants. In `backend/services/rbac.py`, `AppRole.admin` only grants `manage_platform`, and `derive_effective_capabilities()` intersects family-role and app-role capability sets. For an admin user with `family_role='parent'`, `app_roles=['admin']`, and `is_owner=True`, that strips out the educational bundle and leaves only platform/security capabilities, which causes 403s on dashboard, students, gradebook, compliance, and imports flows. This also leaves `backend/services/authorization.py` too literal: `require_any_role()` only accepts exact app-role matches, so routes guarded as teacher-or-student deny admins even when the intended hierarchy is "admin implies everything below it."
- **Decision:** Replace the current narrower-wins app-role behavior with an explicit hierarchy: Admin = full educator access + student-view access + platform management; Parent/Teacher = one shared educator capability bundle for curriculum, grading, students, imports, compliance, and dashboard access; Student = limited student bundle only; Owner-only security remains family-scoped. Teach `require_any_role()` about role implication so `admin` implies `teacher` and `student`, but `teacher` and `student` do not imply `admin`. Make the admin capability set a superset: keep `_TEACHER_CAPABILITIES` as the educator bundle, define the student bundle as `_STUDENT_PROGRESS_CAPABILITIES | _READ_CAPABILITIES`, change `_APP_ROLE_CAPABILITIES` so `AppRole.teacher` = educator bundle, `AppRole.student` = student bundle, `AppRole.admin` = educator bundle + student bundle + `{Capability.manage_platform}`. Remove intersection-based capability derivation and instead compute effective capabilities by hierarchy/union: start from family-role bundle, union in app-role bundle(s), add `manage_platform` from admin, add `manage_security` only when the existing owner-parent rule is true. Preserve `Capability.manage_family` as the compatibility alias for `manage_household` / `manage_platform`.
- **Impact:** Admin users now pass teacher/student role guards automatically, educator flows keep working under the redesigned hierarchy, student-viewer scoping stays unchanged, endpoints like `/api/dashboard`, `/api/gradebook/scales`, compliance reports, and imports unblock for admins.

### Ray RBAC Implementation Guardrail (2026-05-22T15:25:42.606-05:00)
- **Author:** Ray
- **Requested by:** John
- **Context:** Implementing Egon's RBAC hierarchy redesign made `admin` a true superset and switched capability derivation to union-based grants. That broader educator bundle also means legacy `Capability.manage_family` compatibility checks now admit tutor sessions for household-scoped actions like student management and invitations.
- **Decision:** Keep the compatibility alias intact for migration, but treat audit-log access as a platform-admin surface. `backend/routers/audit.py` now requires `Capability.manage_platform` instead of the legacy `manage_family` alias so tutors do not inherit audit access from the educator bundle.
- **Impact:** Admins now pass teacher/student role guards automatically, educator flows keep working under the redesigned hierarchy, and student-viewer scoping stays unchanged. Audit logs remain restricted to platform administrators even while educator permissions expand elsewhere.

### Ray Role Derivation Fixes (2026-05-15T21:46:25.724-05:00)
- **Author:** Ray
- **Context:** Issue #112 review found that external-role auto-provisioning could fail open to `parent`, could infer `is_owner` from IdP admin claims, and could create `student_viewer` memberships without clarifying whether missing `student_id` was acceptable.
- **Decision:** Auto-provisioning now defaults empty or unmapped IdP roles to least-privilege `FamilyRole.student_viewer`, never infers `is_owner` from IdP claims, and allows `student_viewer` memberships with `student_id=None` because `FamilyMembership.student_id` is nullable; these memberships are treated as placeholder access until an explicit student linkage is granted.
- **Impact:** SSO users without recognized role claims cannot escalate to parent/admin-equivalent family access, owner authority stays DB-backed and admin-assigned only, and placeholder student viewers remain architecture-compatible without inventing synthetic student links.

### Tully OIDC Login Fix (2026-05-18T07:28:45.785-05:00)
- **Author:** Tully
- **Requested by:** John
- **Context:** A production HAR for `school.spaid.family` showed `GET /api/auth/oidc/login` ending as `200 text/html` with the SPA payload, even though the backend was handling the request and OIDC was enabled. The auth router only redirected cleanly for `OIDCConfigurationError`, leaving discovery/network/authlib failures to surface unpredictably while clients following redirects could appear to land directly on `index.html`.
- **Decision:** Treat OIDC login and callback initiation failures as fail-closed auth errors: log the exception, redirect to `/login?error=...`, and keep user-visible messages safe and actionable. Wrap OIDC login initiation failures in `backend/services/auth_oidc.py` so discovery/network errors become `OIDCConfigurationError` with meaningful messages. Add a public `/api/auth/oidc/verify` diagnostic that checks discovery reachability and reports whether the IdP metadata is usable.
- **Impact:** Users no longer loop into opaque SPA behavior when the IdP discovery URL is unreachable; they are redirected back to the login screen with a readable error. Infra can hit `/api/auth/oidc/verify` to distinguish config/discovery outages from frontend routing noise. The existing `/api/auth/oidc/login` success path still returns the upstream IdP redirect.

### Tully OIDC Role Derivation (2026-05-15T21:46:25.724-05:00)
- **Author:** Tully
- **Requested by:** John
- **Context:** OIDC external identities already arrive with normalized app roles in `identity.roles`, but the auto-provision default-family path was hard-coding `FamilyRole.parent` and `is_owner=False`. That broke RBAC expectations for admin, teacher, and student SSO users by ignoring their IdP-derived application roles.
- **Decision:** For default-family auto-provisioning only, normalize `identity.roles` through `settings.external_role_mappings`, derive `FamilyMembership.role` from app roles in `backend/services/rbac.py`, and allow ownership only for admin-derived parent memberships when the family has no accepted owner yet.
- **Impact:** Admin SSO users land as `parent`; the first accepted admin in the default family becomes owner. Teacher SSO users land as `tutor`. Student SSO users land as `student_viewer`. Empty or unmapped external roles log a warning and fail closed to the legacy default: `parent` plus `is_owner=False`. Invitation-based provisioning remains unchanged.

### Tully Security Fixes (2026-05-17T21:57:29.677-05:00)
- **Author:** Tully
- **Requested by:** John
- **Decision:** Sanitize control characters in backend log messages, correlation IDs, action labels, and structured detail payloads before formatting or emitting logs. Resolve upload destinations from normalized relative paths only, and reject absolute paths plus any parent-directory traversal before writing submission files. Redact all 5xx HTTP responses to the generic `internal_error` payload so stack traces and exception details stay in logs only.
- **Impact:** Closes the backend CodeQL/Trivy findings for log injection, path injection, stack-trace exposure, and the vulnerable PyJWT pin. Keeps auth/security behavior fail-closed: suspicious upload paths are rejected, user-controlled log fields cannot forge entries, and clients never receive server exception details.

### Venkman Service Worker Denylist (2026-05-18T07:55:09.535-05:00)
- **Author:** Venkman
- **Requested by:** John
- **Context:** The generated PWA service worker was treating every browser navigation as SPA territory. That let Workbox serve `index.html` for backend-owned navigation requests like `/api/auth/oidc/login` and `/api/auth/oidc/callback`, which breaks OIDC redirects and can also mask direct navigations to uploaded files or health endpoints.
- **Decision:** Add a Workbox navigation denylist in `frontend/vite.config.ts` for `/api/*`, `/uploads/*`, and `/health` so those requests bypass the SPA fallback. Mirror the same exclusions in the navigation runtime cache rule so backend navigations are never cached as app pages. Enable `skipWaiting` and `clientsClaim` so fixed service workers activate promptly on the next visit.
- **Impact:** Browser-driven OIDC login and callback navigations now reach the backend instead of loading the SPA shell. Direct navigation to uploaded files and health checks remains backend-owned. Existing users pick up the corrected service worker without waiting through an extra release cycle.

### Ray bcrypt 5.0 Upgrade Guardrail (2026-05-18)
- **Date:** 2026-05-18T16:38:51.741-05:00
- **Requested by:** John
- **Decision:** Do not rely on bcrypt 5.0 silent truncation behavior; enforce a 72-byte UTF-8 password limit before any local-auth bcrypt hash or check reaches the library. Apply the guardrail at the API schema layer for register, login, and invitation acceptance so clients get a validation error instead of a server error. Keep backend defensive checks in `hash_password()` / `verify_password()` and fail early during the legacy family-password migration when `FAMILY_PASSWORD` exceeds bcrypt's limit.
- **Impact:** PR #94 can merge safely once these guardrails are on main because local auth no longer depends on bcrypt 4.x truncation. Existing and future operators get a clear validation or startup error instead of unpredictable bcrypt exceptions when a password exceeds 72 UTF-8 bytes.

### Ray Student Management Capability (2026-05-24)
- **Date:** 2026-05-24T12:57:00.215-05:00
- **Requested by:** John
- **Decision:** Introduce a dedicated `manage_students` capability for student roster writes instead of reusing broad `manage_family` / `manage_household` checks. Grant `manage_students` to parent and co-parent family roles plus the admin app role; do not grant it to the teacher app role so tutors cannot edit the roster. Align the frontend student route and edit affordances with the same capability so admin-only sessions can reach `/students` and use the add-student flow.
- **Impact:** `backend\routers\students.py` now expresses the intended authorization directly for create/update/delete. `backend\services\rbac.py` keeps student-roster permissions separate from general household/platform management, which avoids accidental tutor access while preserving admin access. `frontend\src\context\AuthContext.tsx`, `frontend\src\App.tsx`, and `frontend\src\components\layout\AppShell.tsx` stay in sync with backend RBAC so UI visibility matches API authorization.

### Venkman ESLint upgrade (2026-05-18)
- **Date:** 2026-05-18T16:38:51.741-05:00
- **Requester:** John
- **Scope:** frontend dependency maintenance
- **Decision:** Upgrade `frontend` to `eslint@^10.4.0` and `@eslint/js@^10.0.1` together, and commit `frontend/.npmrc` with `legacy-peer-deps=true` as a temporary install compatibility shim.
- **Why:** Dependabot PR #92 (`@eslint/js` 10) conflicts with ESLint 9 because `@eslint/js@10.0.1` declares `peerOptional eslint@^10.0.0`. Dependabot PR #136 (`eslint` 10) should not land separately from the `@eslint/js` major bump because the flat config imports `@eslint/js` directly. `eslint-plugin-jsx-a11y@6.10.2` is still the latest release and only declares peer support through ESLint 9, but linting still passes with ESLint 10 in this repo. The `.npmrc` shim keeps `npm install` working without dropping accessibility lint coverage.
- **Validation:** `cd frontend && npm install`, `cd frontend && npm run lint`, `cd frontend && npm run build`.

### Egon GitHub Pages Documentation Site Structure (2026-05-24)
- **Date:** 2026-05-24
- **Author:** Egon (Lead)
- **Status:** Proposed
- **Decision:** Create a comprehensive GitHub Pages documentation site with six major sections: Getting Started, User Guides, Features, API Reference, Administration, and Developer Guide. Reorganize existing 16 documentation files into a clear hierarchy, identify critical content gaps (troubleshooting, RBAC/multi-family, email config, API webhooks, security/compliance), and implement using Jekyll + GitHub Pages for native GitHub workflow.
- **Implementation:** Phase 1 (restructuring + organization), Phase 2 (critical content gaps), Phase 3 (polish/optimization). Proposed sidebar structure organized 3 levels deep max. Success criteria: all 16 docs integrated, high-priority gaps filled, navigation responsive, first-time users find Getting Started within 2 clicks.
- **Key Decisions:** Single site for all audiences (simplifies deployment/search); docs-as-code in Git (version control + PR reviews); Jekyll + GitHub Pages (free, GitHub-native, minimal setup); hierarchical structure with deep nesting (supports diverse audiences); separate API reference (OpenAPI-driven).
- **Dependencies:** RBAC documentation depends on finalized role model; email provider choice affects configuration guide; GitHub Pages workflow requires setup.
- **Approval:** Pending review by John (user guides), Ray (API/dev sections), Venkman (UI/feature descriptions), Tully (admin/security sections).
- **Impact:** Creates searchable, organized documentation for parents, teachers, students, admins, and developers without confusion or buried content.

### Ray Curriculum Platform Alias (2026-05-25)
- **Date:** 2026-05-25T18:45:49.686-05:00
- **Requested by:** John
- **Decision:** Treat `manage_platform` as a compatibility alias for `manage_curriculum` checks. Calendar and term APIs already use `manage_curriculum`, and admin is the intended superset role. Azure/SSO sessions can present older or narrower capability payloads that include `manage_platform` but omit `manage_curriculum`, blocking term creation despite admin role.
- **Scope:** `backend\services\rbac.py`, `frontend\src\context\AuthContext.tsx`, `backend\tests\test_authorization.py`
- **Notes:** Compatibility bridge, not new source-of-truth capability model. Terms remain part of curriculum management rather than introducing a separate `manage_terms` permission.
- **Impact:** Admin users no longer blocked from term creation due to capability payload drift from older Azure/SSO identity providers.

### Venkman VitePress Docs Site Scaffold (2026-05-24)
- **Date:** 2026-05-24T14:56:36.726-05:00
- **Author:** Venkman
- **Context:** Repository had populated `docs/` directory with guides/reference but no static-site scaffold for GitHub Pages.
- **Decision:** Create standalone VitePress site rooted in `docs/`, keep all existing markdown files in place, deploy generated `.vitepress/dist` output to `x3nc0n.github.io/homeschool-hero` project site with GitHub Actions workflow. Use `/homeschool-hero/` base path and simple default nav/sidebar organizing current guides, architecture, and reference pages without moving files.
- **Impact:** Documentation can be previewed locally from `docs/` and published automatically to GitHub Pages while preserving compatibility with existing markdown content.

## Governance

- All meaningful changes require team consensus
- Document architectural decisions here
- Keep history focused on work, decisions focused on direction
