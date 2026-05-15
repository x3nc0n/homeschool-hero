# Tully — History

## Project Context
- **Project:** homeschool-hero — Open-source homeschool learning/grading/management platform
- **User:** John
- **Stack:** Python/FastAPI backend, Docker-deployable, OIDC/SAML/local auth
- **Auth architecture:** Dual-axis RBAC model (FamilyRole × AppRole → effective capabilities), narrower-wins precedence, fail-closed on unmapped roles
- **Key files:** backend/security.py, backend/services/authorization.py, backend/services/auth_oidc.py, backend/services/auth_saml.py, backend/services/auth_jwt.py, backend/services/rbac.py
- **Architecture doc:** docs/architecture/rbac-unified-model.md

## Learnings
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
