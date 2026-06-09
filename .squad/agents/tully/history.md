# Tully — History

## Project Context
- **Project:** homeschool-hero — Open-source homeschool learning/grading/management platform
- **User:** John
- **Stack:** Python/FastAPI backend, Docker-deployable, OIDC/SAML/local auth
- **Auth architecture:** Dual-axis RBAC model (FamilyRole × AppRole → effective capabilities), narrower-wins precedence, fail-closed on unmapped roles
- **Key files:** backend/security.py, backend/services/authorization.py, backend/services/auth_oidc.py, backend/services/auth_saml.py, backend/services/auth_jwt.py, backend/services/rbac.py
- **Architecture doc:** docs/architecture/rbac-unified-model.md

## Learnings

- 2026-05-15T14:09:23-05:00 — **PR #109 MERGED & v0.9.2 RELEASED.** PyJWT crit-header fix (commit 720200f) merged and published. Frontend auth fixes (#107) integrated into merged PR #109. Breakglass local login, Entra RBAC middleware, and multi-provider capabilities now live on main.

- 2026-05-14T17:32:06-05:00 — `backend/security.py` now rehydrates bearer sessions from the database before authorization, so `FamilyMembership` stays authoritative for `family_role`, `is_owner`, and `student_id` and invalid `X-Family-Id` values fail with 403.
- 2026-05-14T17:32:06-05:00 — `backend/services/auth_jwt.py` must fail closed when family-role claims are missing; the safe fallback is `student_viewer`, while effective bearer authorization still depends on DB-backed membership context.
- 2026-05-14T17:32:06-05:00 — Unified RBAC capability logic lives in `backend/services/rbac.py`, and stale capability tables should be removed once superseded to avoid conflicting security behavior.
- 2026-05-14T18:25:38.883-05:00 — Entra bearer validation now lives in `backend/services/auth_jwt.py` + `backend/startup.py`: require `JWT_TENANT_ID`, enforce the tenant-scoped v2.0 issuer contract, and keep Entra `roles` authoritative while `groups` remain supporting-only data.
- 2026-05-14T18:25:38.883-05:00 — `backend/security.py` resolves Entra bearer callers by linked OIDC `external_id` first and normalized email second, with `X-Family-Id` selecting which accepted family membership is rehydrated for RBAC.

### JWT Bearer Security Hardening Completion (2026-05-14T22:32:06Z)
- Fixed all 4 critical/important security findings from PR #104 review:
  1. Bearer-token authorization trust for family context and owner status from JWT payloads → rehydrate from DB
  2. Forged `X-Family-Id` header injection → reject with 403
  3. `is_owner` claims in JWT → ignore and use DB-backed `FamilyMembership`
  4. Missing family-role claims → fail closed to `student_viewer`, remove dead `_ROLE_CAPABILITIES` table
- All backend tests pass: 273 passed/2 skipped
- Changes pushed to main branch
- Decision recorded: "Tully JWT Bearer Security Hardening (2026-05-14)" in decisions.md
- 2026-05-14T22:20:11.663-05:00 — `backend/schemas/auth.py` + `backend/routers/auth.py` must keep `/api/auth/me` aligned with `AuthSession` by returning canonical `app_roles` and `effective_capabilities`, or the frontend drops into legacy RBAC fallback.
- 2026-05-14T22:20:11.663-05:00 — `frontend/src/context/AuthContext.tsx` legacy capability synthesis must mirror backend fail-closed ownership rules: only owner-parents inherit `manage_security` when RBAC fields are absent.
- 2026-05-14T22:20:11.663-05:00 — `backend/services/rbac.py` is the canonical capability list; `view_own_progress` now belongs there for `student_viewer`/`student` access so frontend route guards and navigation can rely on a real backend-backed capability.
- 2026-05-15T07:10:40.494-05:00 — Breakglass local login lives at the existing `/api/auth/login` password flow: keep it available even when `AUTH_PROVIDER` advertises OIDC/SAML, but only successful logins against an existing database account proceed and they must emit a WARNING audit log when `AUTH_BREAKGLASS_LOCAL=true`.
- 2026-05-15T07:10:40.494-05:00 — OIDC callback failures should degrade back to `/login?error=...` instead of 500ing; wrap token-exchange and ID-token parsing failures in a user-safe `OIDCConfigurationError` so the router can redirect cleanly.
- 2026-05-15T07:43:55-05:00 — Bearer JWT validation is affected by PyJWT `crit`-header handling because `backend/services/auth_jwt.py` accepts externally supplied bearer tokens; keep PyJWT pinned/aligned at 2.12.0 across `requirements*.txt`, and fail closed on any token that presents a `crit` header because the app defines no supported critical JWT extensions.
- 2026-05-17T21:57:29.677-05:00 — `backend/services/logging_config.py` must sanitize control characters in log messages, correlation IDs, action names, and structured `details` values before formatting, or user-controlled headers/fields can forge log entries.
- 2026-05-17T21:57:29.677-05:00 — `backend/services/storage.py` now normalizes upload paths with `os.path.normpath` and rejects absolute or `..`-based destinations before writing, so submission uploads stay contained under the configured upload root.
- 2026-05-17T21:57:29.677-05:00 — `backend/main.py` should treat every 5xx response path as generic `internal_error` output; exception specifics belong only in logs, even when an `HTTPException` carries custom detail.
- 2026-05-18T07:28:45.785-05:00 — `backend/routers/auth.py` + `backend/services/auth_oidc.py` must fail closed on OIDC login/callback exceptions: log the diagnostic, redirect users back to `/login?error=...`, and keep `/api/auth/oidc/verify` public so infra can distinguish discovery outages from SPA redirect noise.
- 2026-05-18T07:28:45.785-05:00 — The SPA catch-all in `backend/main.py` is not winning route resolution for `/api/auth/oidc/login`; if OIDC initiation redirects to `/login`, clients that follow redirects will finish on the SPA `index.html`, which matches the HAR symptom.
### 2026-06-09 Security Awareness
- Security batch (#183, #178, #181, #180, #169-#175) resolved by Ray and Venkman
- Key patterns: fail-closed defaults, sanitization at data sinks, no sensitive info in responses/logs
- Frontend: render-site XSS sanitization. Backend: path validation, exception redaction, log sanitization

