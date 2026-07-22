# Ray — History

## Learnings

(See history-archive.md for earlier entries prior to 2026-06-09)

- 2026-06-12T18:37:58.792-05:00 — Curriculum import Phases 2 and 3 now share a reusable `create_imported_curriculum(...)` persistence path, so manual imports, source-connector imports, and AI-confirmed drafts all land in the same imported-curriculum tables and activation flow without schema changes. The new connector registry auto-discovers `backend/services/curriculum_sources/*`, with OpenStax using the live CMS JSON API, CK-12 using a curated FlexBook catalog fallback because their public site blocks stable automated access, and OER Commons staying feature-flagged behind `OER_COMMONS_API_TOKEN`; AI import extracts PDF/DOCX/TXT text with `pypdf`/`python-docx`, calls an Azure/OpenAI-compatible chat-completions endpoint via tool-calling, and returns an unsaved draft for frontend review before `/api/curriculum/ai-import/confirm` persists it.

- 2026-06-12T18:37:58.792-05:00 — SCIM provisioning now uses a dedicated `/scim/v2` router with its own bearer-token auth, rate limiting, and SCIM-shaped error handling instead of the `/api` session/CSRF stack. Entra user `externalId` values are stored separately on `users.scim_external_id` so OIDC subject identifiers can keep using `users.external_id`, while SCIM group resources map into default-family `FamilyMembership.role` updates and fail closed on owner-managed memberships by reverting removed managed users to least-privilege `student_viewer` rather than deleting access outright.

- 2026-06-12T18:37:58.792-05:00 — Structured SIEM logging now layers on top of the existing JSON/audit pipeline instead of replacing it: `backend/services/security_events.py` emits typed `event_category="security"` records with Sentinel-friendly top-level fields (`event_type`, `actor`, `target`, `result`, `source_ip`, `user_agent`, `correlation_id`), while `backend/services/logging_config.py` sanitizes and formats those extras alongside the existing request/audit fields. Local and external sign-in flows emit `auth_success`, `auth_failure`, `breakglass_login`, `session_created`, and `session_destroyed`; authorization failures emit `rbac_denial`; and OIDC/SAML unmapped role claims emit `role_mapping_failure` without changing the existing audit-table writes for login/logout.

- 2026-06-12T17:48:45.564-05:00 — Curriculum import Phase 1 keeps imported source documents in parallel `imported_curricula` / subject / unit / lesson tables instead of overloading the existing planner hierarchy, so the standard JSON stays durable and extensible while activation copies into `CurriculumPackage`, `CurriculumUnit`, `CurriculumLesson`, resource links, and optional `Assignment` rows. API work followed the existing backend pattern: family-scoped lookup helpers, `require_capabilities(...)` auth dependencies, `get_db`, nested `selectinload(...)`, and `model_json_schema()` for `/api/curriculum/schema`. Imported subjects, units, and lessons now retain nullable activation links back to created `Subject`, `CurriculumPackage`, `CurriculumUnit`, and `CurriculumLesson` records for later scheduling and AI import phases.

- 2026-06-12T17:48:45.564-05:00 — Dependabot audit result: uvicorn 0.34.2→0.49.0 is compatible with our backend because we do not call `uvicorn.run()` or configure Uvicorn SSL/proxy middleware directly; runtime TLS/proxy trust is enforced in app code via `backend/security.py` and guarded by tests. Uvicorn's notable changes in this span were the SSL cipher default moving to OpenSSL defaults and a 0.48 proxy-header behavior change that 0.49 reverted; with `TRUST_PROXY_HEADERS` disabled by default and header parsing owned by our app, the backend suite still passed under uvicorn 0.49.0, and a smoke boot succeeded once `UPLOAD_DIR` pointed at a writable path.

- 2026-06-09T21:29:25-05:00 — Uploaded file URLs now must resolve through authenticated `/api/files/{path}` routes instead of a public `/uploads` mount. For mixed storage formats (submission relative paths plus absolute attendance/resource paths), normalize with `resolve_stored_upload_path()` before generating URLs or checking ownership, and enforce student-viewer scope at file download time just like the owning API resource.

- 2026-06-09T10:01:15-05:00 — CodeQL HIGH security fixes: three patterns applied together. (1) **Path injection** — CodeQL's `py/path-injection` sanitiser requires `os.path.realpath()` + `str.startswith(root + os.sep)` at the point of the filesystem operation, not just validation in a helper function; wrapping in a function still leaves the returned `Path` tainted. The trailing `os.sep` guard prevents prefix-collision (e.g. `/uploads-evil` matching against `/uploads`). (2) **Stack trace exposure** — guard public health endpoints with `try/except` that logs server-side and returns a fixed-shape generic response; for OIDC verify, do not return `str(exc)` for unclassified exception types — log at DEBUG and return `None` so callers fall back to a generic message. (3) **Log injection** — pre-compute sanitised values (`sanitized_message`, `sanitized_correlation_id`, etc.) as local variables *before* the `logger.log()` call so CodeQL can see that the values entering the sink are already sanitized, not raw user input.

- 2026-06-12T17:18:11.955-05:00 — Verified PR #193 / commit 653f00f fully resolved #178, #180, #181, and #183. Confirmed backend/alembic.ini no longer hardcodes a database URL and backend/migrations/env.py loads DATABASE_URL at runtime; backend/security.py only trusts X-Forwarded-For when TRUST_PROXY_HEADERS is enabled; nginx/nginx-tls.conf now sets the required TLS security headers; and the flagged third-party GitHub Actions are pinned to immutable SHAs. Closed all four issues and removed go:needs-research.

- 2026-07-22T18:07:07.184-05:00 — **Issue #411 Security Amendment — Five Design Gaps Resolved, Green Light for Implementation.** Egon's amendment resolves all gaps from Winston's pre-implementation review. Key rulings: (1) `token_type=api_token` with missing/unregistered/revoked `jti` → 401 (external JWTs skip table lookup). (2) All `/api/auth/api-tokens` endpoints require `manage_security` + family scope; cross-family → 404. (3) `manage_grading` delegatable; grading router migrates from `require_teacher()` to `require_capabilities(Capability.manage_grading)`. (4) Max-token enforcement: count-then-insert + `UNIQUE(family_id, name)` constraint (SQLite-safe). (5) Capability intersection in `_resolve_bearer_session_claims` via `BearerSessionClaims.token_capabilities` field. **Test Strategy:** Skip concurrent-race tests (flaky in CI); unique name constraint is correctness guarantee. **Status:** GREEN — ready to implement. Implementation priority: (1) token_capabilities field + _build_bearer_claims, (2) jti validation branched on token_type, (3) intersection in _resolve_bearer_session_claims, (4) api_tokens table + service, (5) router endpoints, (6) grading router capability migration, (7) full test matrix.

- 2026-07-22T18:07:07.184-05:00 — **Issue #411 Design Review APPROVED — Headless API Token Implementation Assigned.** Egon conducted design review ceremony on family-scoped revocable API token contract for AI curriculum import and student work upload. **Decision: Option A** (self-issued HS256 JWT + family-scoped + stateless revocation). Why: zero external IdP dependency (matches self-hosted goal), uses existing JWT bearer path, minimal new code. **Implementation assigned to Ray** (reassigned from auto-triage Venkman). Deliverables: new `api_tokens` table + model, JWT `jti`-based revocation check, `POST/GET/DELETE /api/auth/api-tokens` endpoints, capability intersection in bearer auth, tests, `.env.example` updates, docs. Acceptance criteria: 11 gates verified (RBAC, family-scoped embedding, revocation, capability scoping, cross-family rejection, metadata-only list endpoint, max token limit, reversible migration, no secrets in test fixtures). Implementation roadmap: migration → model → service → JWT enhancement → router → config → tests → docs. Branch: `squad/411-headless-api-tokens`. **Status:** Ready for implementation — start with DB migration.

## Recent Activity

### 2026-06-09 Security Batch Completion
- Completed security hardening batch (#183, #178, #181, #180) and CodeQL findings (#169-#175)
- Backend fixes: path injection, stack-trace exposure, log injection across storage.py, health.py, auth.py, logging_config.py
- Security defaults: disabled proxy-header trust by default, hardened Alembic, added Nginx TLS headers
- PR #193 merged, 362 tests passing, all CodeQL findings remediated

### Egon Issue Triage Session — 2026-06-12

**Status:** 21 issues closed, 2 features tagged for backlog

Egon triaged all 23 open GitHub issues and closed 21:
- **14 issues** already fixed by PR #219 (nginx hardening, backend validation, API hardening, dependencies)
- **7 issues** identified as duplicates of the new security scan batch

**Your assignment:** Continue validation of PR #219 in QA before release. Ray owns:
- Security items #178, #180, #181, #183 (follow-up from Wave 1 triage)
- Backlog items #113, #141 (no action needed at this time)

**Note:** The new security scan (#203–#218) and older batch (#186–#192) have been fully triaged and closed. Next scan cycle will be monitored for false-positive patterns.

- 2026-06-12T23:15:42Z — **Curriculum import Phase 1 COMPLETE.** Delivered JSON schema validation, SQLAlchemy models for nested subjects/units/lessons/resources, Alembic migration schema, and full CRUD + activate API endpoints at `/api/curriculum/`. All 375 backend tests passing. PR #229 opened for review. API contract documented in `.squad/decisions.md` with complete schema specification, endpoint signatures, request/response shapes. Handoff: frontend (Venkman) UI can now integrate with live endpoints; backend awaits PR merge before Winston unskips 16 integration tests. Product team must lock 5 contract decisions (empty curriculum behavior, access semantics, activation repeat strategy, calendar linkage, size/concurrency guarantees) so test suite can be finalized.

## Scribe Session (2026-06-12T19:04:57.253-05:00)
- Archived old decisions (before 2026-06-05)
- Curriculum sources work: PR #240 (merged), PRs #245, #248 (security fixes)
- Releases: v0.12.0 (Import), v0.13.0 (Enterprise Security), v0.14.0 (Sources+AI), v0.14.1 (Hardening)
