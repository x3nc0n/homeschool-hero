# Tully JWT Security Fixes

- Date: 2026-05-14T17:32:06-05:00
- Author: Tully
- Context: Egon rejected PR #104 because bearer-token authorization trusted family context and owner status from JWT input instead of canonical family membership data.
- Decision: Rehydrate every bearer-backed family session from the database before authorization. Bearer requests now require an accepted `FamilyMembership` for the authenticated user and selected family, reject forged `X-Family-Id` values with 403, ignore `is_owner` claims in JWT payloads, and fail closed to `student_viewer` when family-role claims are absent. Remove the dead `_ROLE_CAPABILITIES` table so RBAC has one canonical capability source.
- Impact: JWT, OIDC, SAML, and local flows now follow the architecture rule that family scope and owner semantics are database-backed, while test coverage explicitly guards against family-header injection and owner-claim escalation.
