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
