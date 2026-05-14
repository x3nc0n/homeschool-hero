---
name: "jwt-session-rehydration"
description: "Rehydrate bearer-token family sessions from DB-backed membership before authorization."
domain: "authentication"
confidence: "high"
source: "earned"
---

## Context
Use this when a stateless bearer token can select a tenant, family, workspace, or other scoped container. Token claims may prove identity and app-role intent, but family-scoped authorization must still come from canonical membership records.

## Patterns
- Validate the JWT first, then load the selected family membership from the database before building the request session.
- Treat `family_role`, `is_owner`, `student_id`, and other scope-defining fields as database-backed, not token-backed.
- Reject bearer requests with 403 when the authenticated user has no accepted membership for the requested family or tenant.
- Fail closed when optional family-role claims are missing; prefer the most restrictive fallback if a temporary in-memory role is still required.
- Keep one canonical RBAC capability table and remove superseded maps once authorization logic migrates.

## Examples
- `backend/security.py` rehydrates bearer sessions through `FamilyMembership` before route authorization.
- `backend/services/auth_jwt.py` ignores `is_owner` claims and falls back to `student_viewer` when family-role claims are absent.
- `backend/tests/test_rbac_unified.py` covers forged `X-Family-Id` headers and forged owner claims.

## Anti-Patterns
- Trusting `X-Family-Id` or equivalent scope headers without a membership lookup.
- Accepting owner/admin family powers directly from bearer-token claims.
- Leaving dead capability maps in place after the RBAC engine changes.
