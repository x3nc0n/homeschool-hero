# Ray — History

## Learnings

- 2026-05-24T12:57:00.215-05:00 — Fixed parent/admin student creation issue by introducing dedicated `manage_students` capability. Granted to parent, co-parent, and admin roles (not tutor). Updated `backend\routers\students.py` CRUD endpoints and frontend auth context, App.tsx, AppShell.tsx. 339 tests pass; frontend build green. Decision: "Ray Student Management Capability" logged to decisions.md.

- 2026-05-24T12:57:00.215-05:00 — Student roster writes are controlled in `backend\routers\students.py`; the safe RBAC pattern is a dedicated `manage_students` capability granted to parent/co-parent family roles and the admin app role, while frontend access must align in `frontend\src\context\AuthContext.tsx`, `frontend\src\App.tsx`, and `frontend\src\components\layout\AppShell.tsx` so admin-only sessions can see and use the student add flow without giving tutors household-edit rights.

- 2026-05-22T20:25:42.606Z — Scribe merged Ray RBAC Implementation and related RBAC fix decisions to decisions.md. Session complete: admin hierarchy now enforced, audit logs gated on manage_platform, role-derivation defaults to student_viewer. Orchestration log recorded. 334 tests passing validates implementation.

- 2026-05-15T07:10:40.494-05:00 — Auth capabilities now separate the primary login method (`AUTH_PROVIDER`) from provider visibility: OIDC shows when `OIDC_CLIENT_ID` is set, SAML shows when all SAML settings are present, and `AUTH_BREAKGLASS_LOCAL` controls whether local auth stays exposed as the fallback option.

- 2026-05-25T18:45:49.686-05:00 — Academic term and school-year writes in `backend\routers\calendar.py` use `manage_curriculum`, not a separate `manage_terms` capability. To preserve the admin-superset rule for Azure/SSO sessions that only surface legacy `manage_platform`, keep a compatibility alias from `manage_curriculum` to `manage_platform` in both `backend\services\rbac.py` and `frontend\src\context\AuthContext.tsx`; backend coverage lives in `backend\tests\test_authorization.py`.

- 2026-05-26T00:00:58-05:00 — Released v0.10.2 (commit 65286c6, tagged, pushed). Terms creation fix deployed: `manage_platform` → `manage_curriculum` alias resolves term-creation blocking for SSO/Azure admin sessions. Investigated and fixed underlying capability payload drift. Issue #139 resolved. 340 tests passing.

## Summary

Project: homeschool-hero — open-source homeschool platform for families
GitHub: https://github.com/x3nc0n/homeschool-hero

**Current Status:** 340 backend tests passing; v0.10.2 released with terms-creation fix; RBAC unified across local, OIDC, SAML, and JWT bearer auth; student creation authorization fixed; frontend and backend auth gating synchronized.

See history-archive.md for Wave 1–4 detailed task history (phases 1–3 MVP completion, Wave 3 production workstreams, Wave 4 RBAC implementation, CI operations).

