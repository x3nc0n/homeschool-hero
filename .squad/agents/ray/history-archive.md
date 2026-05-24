# Ray — History Archive

## Archived Phases and Tasks (2026-05-08 through 2026-05-09T00:41:00)

### Learnings (Project Context)
- Project: homeschool-hero — open-source homeschool platform for families
- User: John; Core concerns: file upload/storage, OCR, AI-grading, grade DB
- Auto-grading: upload → OCR → AI grades → parent review
- GitHub: https://github.com/x3nc0n/homeschool-hero
- 2026-05-08T09:11:31 — GitHub repo created; initial setup with .gitignore and README

### Phase 1 Completion (2026-05-08T22:04:55Z)
- Tasks 1-8: Docker scaffolding, async FastAPI, SQLAlchemy models, Alembic initial migration, auth/session middleware ✓
- CRUD APIs: students, subjects, assignments, grades, quizzes, submission uploads
- 33 tests passing; frontend integrated against stable endpoints
- All APIs contract-tested and production-ready for phase 2

### Phase 2 Completion (2026-05-08T22:30:00Z)
- Tasks 17-19: OCR preprocessing, AI grading (Ollama/OpenAI), background worker daemon ✓
- Grading pipeline active: upload → OCR → AI grading with confidence routing
- Low-confidence grades route to manual review
- Ollama/OpenAI failover implemented

### Task 25: Docker Polish + Integration (2026-05-08T23:50:20Z)
- Multi-stage Dockerfile with optimized layers
- Frontend SPA bundled into backend container
- Alembic migrations auto-run on startup; health endpoint configured
- Docker Compose with volume mounts and health monitoring
- Commit: aa9555d — MVP fully containerized
- Added GitHub Actions CI: backend pytest, frontend lint/build, Docker image verification

### Phase 3 Preparation (2026-05-08T22:18:50Z)
- Submitted 3 decision records: Ray CI Setup, Ray Docker Local Stack, Winston CI Test Reliability
- Decisions merged into active registry
- Production plan finalized (40 todos, 9 functional areas)

### Phase 3 Task CP-01 Completion (2026-05-08T22:48:51Z)
- Multi-family tenancy: owner bootstrap, per-user email/password sessions ✓
- Family-scoped tenancy enforced across all models/routers
- 41 tests passing, 2 skipped; tenancy isolation verified
- Migration path for legacy auth → default family + owner
- Frontend auth flows integrated with new per-user login
- Commit: 02b59df

### Task: Startup Validation & Graceful Degradation (2026-05-08)
- Added startup config validation and capability registry
- Health reporting stays green when optional services down
- Grading/upload flows degrade when AI/OCR unavailable
- Frontend capability context and reduced-functionality cues

### Task: IO-01 Deployment Hardening (2026-05-08T23:15:59Z)
- Docker Compose profiles: minimal base + ai/email/backup/full options
- App runs as non-root with tini
- Helper scripts: start/backup/migration CLI
- Production env/docs added; Compose and Docker verified

### Wave 3 Production Tasks (2026-05-09T00:40:00 through 2026-05-09T01:11:50)
- **AM-01 Academic Calendar:** school year/term/grading period models; family-scoped calendar CRUD; active-year/day-count APIs; React calendar page (98 tests passing)
- **CP-04 Audit Logging:** immutable audit events; audit API filters/pagination; parent/co-parent audit UI (18 tests passing for audit suite)
- **SD-01 Application Hardening:** secure sessions with CSRF; password policy/login lockout; rate limiting; upload validation; security headers (84 tests passing, 2 skipped)
- **CP-05 Auth Provider Support:** configurable OIDC + SAML overlays; local auth default; Entra-ready OIDC discovery; SAML metadata/ACS endpoints (84 tests passing, 2 skipped)
- **AM-02 Daily Scheduling:** schedule/schedule block/override models; recurring/override agenda; weekly/daily views; conflict detection (98 tests passing, 2 skipped)

### Wave 3 Production Tasks Continued (2026-05-09T02-04:58)
- **AM-03 Curriculum Packages:** curriculum/unit/lesson/resource models; family-scoped CRUD/clone/link; tutor management UI (98 tests passing, 2 skipped)
- **AG-01 Assignment Domain Upgrade:** category/grading period/weight/max score/recurrence/rubric/attachments; per-student AssignmentTarget records (94 tests passing, 2 skipped)
- **IO-04 Observability Surfaces:** structured logging with correlation IDs; optional `/api/metrics` endpoint; dashboard activity + health widget (94 tests passing, 2 skipped)
- **AM-05 Attendance Tracking:** attendance record/excuse models; bulk entry APIs; instructional hours tracking; day/week/term/year summaries; audit logging (115 tests passing, 1 skipped)
- **AG-02 Submission Hardening:** file format validation (PDF/JPEG/PNG/HEIC/TIFF/WEBP); deterministic storage; submission version history (115 tests passing, 1 skipped)

### Wave 3 Production Tasks Continued (2026-05-09T04:33-08:35)
- **AG-03 Grading Hardening:** answer keys per assignment; status-machine tracking; retry/backoff + timeout handling; AI circuit-breaker fallback (133 tests passing, 1 skipped)
- **DM-01 Import Ecosystem:** import jobs; CSV/JSON validation + execution; dry-run error reporting; progress tracking; template downloads; audit-logged bulk import (133 tests passing, 1 skipped)
- **AG-05 Review Workflow:** review item/comment persistence; family-scoped review queue/detail/action/bulk APIs; reviewer assignment/comment threads; audit coverage (145 tests passing, 1 skipped)
- **AM-06 State Compliance Framework:** family/state-aware compliance rules; TX/CA/VA/NY/FL seeded rules; compliance evaluation/notification APIs; dashboard + settings UI (145 tests passing, 1 skipped)
- **AG-04 Assessments & Gradebook:** grade scales; weighted categories with drop-lowest; subject grading modes; gradebook API for views/summaries/trends (145 tests passing, 1 skipped)
- **IO-05 TLS/Maintenance Operations:** maintenance-mode persistence; admin APIs; HTTPS redirect/HSTS controls; Nginx configs; self-signed cert script (181 tests passing, 1 skipped)

### Wave 3 Production Tasks Continued (2026-05-09T05:05-08:35)
- **AG-06 Performance Optimization:** composite/partial/full-text indexes; TTL cache + conditional GET; N+1 removals; standardized pagination (152 tests passing, 1 skipped)
- **DM-02 Export Packages:** export jobs; JSON/CSV/ZIP formats; full/incremental/entity exports; self-contained bundles (162 tests passing, 1 skipped)
- **DM-03 Backups to NAS:** backup jobs; NAS mount validation; cron scheduling; SQLite/pg_dump capture; optional restic snapshots (167 tests passing, 1 skipped)
- **IO-02 Health Checks & Status Center:** health/status regression coverage; Docker Compose probing; status center page with service indicators (181 tests passing, 1 skipped)
- **DX-01 OpenAPI & Integration Docs:** /api/openapi.json metadata; grouped tags; Swagger UI + ReDoc; integration/development guides (167 tests passing, 1 skipped)
- **DM-04 Restore Drills & Retention:** restore validation/execution; selective service restore; retention runtime/cleanup; backup manifest updates (pre-existing export failures noted)

### Wave 3 Production Tasks Completed (2026-05-09T04:19:50)
- **DX-02 i18n Foundation:** react-i18next with English fallback + partial Spanish; localized app shell/dashboard/auth/settings; persisted language selector; backend locale negotiation (187 tests passing, 1 skipped)

### Wave 3 Production Tasks Continued (2026-05-09T05:20-07:45)
- **RC-02 Transcript Generation:** transcript/transcript-entry models; cumulative + weighted GPA with honors/AP weighting; transcript PDF output (158 tests passing, 1 skipped)
- **AM-04 Lesson Plans & Pacing Guides:** family-scoped lesson plan + pacing target APIs; curriculum-driven schedule generation; pacing calculations; assignment generation (119 tests passing, 1 skipped)

## Summary
Completed 25+ Wave 3 production workstreams spanning academic operations, grading systems, compliance, data management, observability, deployment, and internationalization. Test coverage grew from 33 to 187+ passing tests across all areas. All production migrations validated; Docker and CI pipelines verified. Ready for final consolidation and team architecture decisions.

## Archived Phases and Tasks (2026-05-14 through 2026-05-22)

### Wave 4 RBAC Implementation (2026-05-14T08:57 through 2026-05-22T15:25)
- **Issues #98–#103 (Unified RBAC):** Ray implemented phase 1 with provider-neutral `AppRole` layer, environment-driven external role mappings, effective capability calculation preserving backward compatibility.
- **OIDC/SAML Role Extraction:** Ray added role extraction at protocol boundary, `OIDC_ROLES_CLAIM` primary with `OIDC_GROUPS_CLAIM` fallback, `SAML_ROLE_ATTRIBUTE` selection with Microsoft attribute support.
- **Provider-Agnostic Enforcement + JWT Bearer:** Ray added explicit role dependencies (`require_admin`, `require_teacher`, `require_student`), bearer-token prioritization, symmetric/asymmetric JWT validation with JWKS caching, provider-neutral auth source resolution.
- **Bearer Security Hardening:** Tully rehydrated bearer-backed sessions from database, rejected forged family-context, ignored owner claims in JWT, kept database-backed family scope as canonical.
- **Frontend Auth Gating:** Venkman made auth layer capability-first, normalized `app_roles`/`effective_capabilities` in AuthContext, synthesized legacy fallbacks for local auth, route guards keyed off capabilities/AppRoles.
- **RBAC Hierarchy Redesign:** Egon replaced narrower-wins with explicit hierarchy: Admin = full educator + student + platform; Parent/Teacher = educator bundle; Student = student bundle; Owner-only security remains family-scoped.
- **Implementation Guardrail:** Ray kept compatibility alias, gated audit-log access to `manage_platform` to exclude tutor escalation.
- **Role Derivation Fixes:** Ray defaulted unmapped external roles to least-privilege `student_viewer`, never inferred `is_owner` from IdP, allowed `student_viewer` with `student_id=None`.
- **Breakglass Semantics:** Tully clarified `AUTH_BREAKGLASS_LOCAL` authorization: backend rejects `/api/auth/login` when disabled, capabilities report local auth accurately.
- **Multi-Provider Capabilities:** Ray separated `AUTH_PROVIDER` (primary flow) from visibility: expose OIDC/SAML based on config presence, local auth by default with `AUTH_BREAKGLASS_LOCAL`.
- **Breakglass Local Login:** Tully kept local password route available as fallback even when primary provider set to OIDC/SAML, convert OIDC failures to user-safe redirects.
- **OIDC Login Fix:** Tully wrapped OIDC discovery/network failures in `OIDCConfigurationError`, added `/api/auth/oidc/verify` diagnostic.
- **OIDC Role Derivation:** Tully normalized `identity.roles` through external mappings, derived `FamilyRole` from app roles, allowed first admin to become owner in default-family auto-provisioning.
- **Security Fixes:** Tully sanitized control characters in logs, resolved upload paths from normalized relative paths only, redacted 5xx HTTP responses.
- **Service Worker Denylist:** Venkman added Workbox navigation denylist for `/api/*`, `/uploads/*`, `/health` to preserve backend ownership and OIDC redirect flow.
- **Dependencies:** Upgraded bcrypt, PyJWT 2.12.0 (CVE-2026-32597), ESLint 10 with `.npmrc` legacy-peer-deps shim.
- **Test Coverage:** 334–339 tests passing; RBAC unified spec tests with 34 skipped cases awaiting implementation.
- **Decisions:** 8 merged (RBAC Implementation, OIDC/SAML Extraction, Enforcement+JWT, Breakglass Semantics, Multi-Provider, Breakglass Login, OIDC Login Fix, OIDC Role Derivation).
- **Key Commits:** Multiple PRs merging unified RBAC across all providers; CI green with 339 tests passing.

### CI Fixes & Operations (2026-05-09 through 2026-05-18)
- **Migration Lint:** Added ROLLBACK_NOTES blocks to 16 migration files; fixed lesson_plans_alias.py no-op downgrade.
- **Security:** Set TLSv1_2 minimum in backend/services/health.py; updated PyJWT to 2.12.0.
- **Test Quality:** Removed duplicate function definitions in backend/tests/contracts.py.
- **Docker Capability:** Restored PostgreSQL startup with minimal `cap_add` on db service.
- **CI Fixes:** Changed high-entropy secrets to allowlisted placeholders, added `--load` flag for Buildx+Trivy.
- **Admin Guide:** Created docs/admin-guide.md with 2400+ word runbooks.
- **Azure Scaffold:** Cloned Spaidoso/homeschool-hero-azure with 30-file Bicep structure; PostgreSQL private access via delegated subnet.
- **Dependency Review:** 10 backend PRs reviewed; 8 auto-merged; pytest 9.x major held pending migration assessment.
- **Commit:** eba9332 (210 tests, 0 lint errors), 7833329 (Docker capability), 6889c31 (CodeQL/Buildx/Trivy), 809f38f (Azure scaffold).
