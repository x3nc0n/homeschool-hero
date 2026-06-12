# Ray decision — SCIM 2.0 endpoint for Entra ID

- Date: 2026-06-12T18:37:58.792-05:00
- Author: Ray
- Requested by: John Spaid
- Issue: #141

## Decision
- Expose SCIM under `/scim/v2` as a separate integration surface with its own bearer-token auth, rate limiting, and SCIM-formatted error/metadata responses instead of reusing the `/api` cookie + CSRF flow.
- Store Entra provisioning identifiers on a dedicated `users.scim_external_id` field so SCIM lifecycle state does not overwrite OIDC/SAML login identifiers that already use `users.external_id`.
- Model SCIM groups as default-family role mappings (`scim_groups`) that drive `family_memberships.role`; managed users without an assigned group fall back to least-privilege `student_viewer`, and owner-managed memberships are immutable from SCIM to preserve the existing DB-backed owner authority decision.

## Impact
- Entra can provision users and role/group changes incrementally without waiting for role claims in the OIDC token.
- Existing OIDC sign-in remains compatible because SCIM and login identity references no longer collide.
- Audit coverage now includes SCIM user/group mutations, and operators must explicitly enable SCIM with `SCIM_ENABLED=true` plus `SCIM_BEARER_TOKEN`.
