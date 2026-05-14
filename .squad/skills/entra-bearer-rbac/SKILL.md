---
name: "entra-bearer-rbac"
description: "Validate Microsoft Entra bearer tokens while preserving DB-backed family RBAC rehydration."
domain: "authentication"
confidence: "high"
source: "earned"
---

## Context
Use this when Homeschool Hero needs to accept Microsoft Entra ID access tokens on API routes without letting raw JWT claims replace canonical family membership or capability computation.

## Patterns
- Keep signature, issuer, audience, and expiration checks in the shared JWT validator, then add Entra-specific `tid` validation with a configured `JWT_TENANT_ID`.
- Require the configured issuer to match `https://login.microsoftonline.com/<tenant-id>/v2.0` so startup fails fast on tenant drift.
- Treat the Entra `roles` claim as authoritative for RBAC; never derive app roles from `groups`.
- Parse `groups` only as supporting data, and handle Entra overage signals (`hasgroups`, `_claim_names`, `_claim_sources`) without failing or escalating privileges.
- Rehydrate bearer-family access from the database by resolving the user through linked OIDC `external_id` first, then normalized email, and use `X-Family-Id` to choose the family membership being authorized.

## Examples
- `backend/services/auth_jwt.py` validates `tid`, preserves Entra `roles`, and ignores `groups` for authorization decisions.
- `backend/security.py` resolves Entra bearer callers through OIDC-linked identities before rebuilding the request session from `FamilyMembership`.
- `backend/tests/test_rbac_unified.py` covers tenant mismatch, object-ID resolution, and groups-overage safety.

## Anti-Patterns
- Treating Entra `groups` as the RBAC source of truth.
- Accepting bearer requests without tenant validation or with a non-tenant-scoped Entra issuer.
- Trusting token claims for family membership instead of rehydrating from the database.
