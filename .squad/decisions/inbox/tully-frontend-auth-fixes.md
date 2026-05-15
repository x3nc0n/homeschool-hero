# Tully Frontend Auth Fixes

- **Date:** 2026-05-14T22:20:11.663-05:00
- **Author:** Tully
- **Issue:** #107

## Context
PR #108 exposed drift between backend auth-session serialization and the frontend capability-first auth layer. The SPA had to fall back to legacy RBAC synthesis because `/api/auth/me` omitted canonical `app_roles` and `effective_capabilities`, and that fallback over-granted `manage_security` to non-owner parents.

## Decision
Treat the backend auth session payload as the canonical RBAC contract for the frontend: always serialize `app_roles` and `effective_capabilities` from `AuthSession`, keep `manage_security` owner-parent only in any legacy fallback, and promote `view_own_progress` into the backend capability enum so student-facing route guards reference a real server-defined permission.

## Impact
Frontend gating now consumes the same RBAC data the backend enforces, reducing dead fallback paths and preventing UI exposure that contradicts server authorization. Student progress checks also have an explicit backend capability, which keeps the dual-axis RBAC model expressive without inventing client-only permissions.
