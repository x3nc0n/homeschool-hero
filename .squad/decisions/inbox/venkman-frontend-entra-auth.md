# Venkman Frontend Entra Auth Gating

- **Date:** 2026-05-14T21:02:10.172-05:00
- **Author:** Venkman
- **Issue:** #107

## Context
The backend session model now carries AppRole and effective capability data for Entra/OIDC sign-in, but the SPA still gated routes and navigation by raw `FamilyRole` string checks. That would drift from backend authorization rules, especially for Entra-issued sessions whose access is determined by `app_roles` and `effective_capabilities`.

## Decision
Make the frontend auth layer capability-first. `AuthContext` should normalize `app_roles` and `effective_capabilities` into shared `hasRole`/`hasCapability` helpers, then synthesize legacy AppRole/capability fallbacks from `membership.role` when local auth sessions do not include RBAC fields. Route guards, navigation, and tab visibility should consume those helpers so OIDC and local auth follow the same UI gating rules.

## Impact
Frontend access checks now match the backend RBAC shape without requiring MSAL or a client-side OAuth implementation. Local email/password installs keep working because FamilyRole-based sessions are translated into the same helper API, reducing future drift between server auth decisions and visible UI affordances.
