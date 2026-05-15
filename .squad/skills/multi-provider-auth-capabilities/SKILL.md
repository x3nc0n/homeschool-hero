---
name: "multi-provider-auth-capabilities"
description: "Separate the primary auth provider from visible login options and breakglass local fallback."
domain: "authentication"
confidence: "high"
source: "earned"
---

## Context
Use this when the app can support more than one login method at the same time, but still needs a single default flow for UX or routing decisions.

## Patterns
- Treat the configured primary provider as the default login flow, not as the sole source of truth for which providers are available.
- Compute provider visibility from each provider's own configuration readiness instead of from `AUTH_PROVIDER`.
- Model breakglass local auth explicitly with a separate flag so UI visibility and backend enforcement stay aligned.
- Validate partially configured secondary providers at startup so visible buttons do not lead to dead auth flows.
- Keep the frontend contract stable by returning both `current_provider` and per-provider booleans plus an aggregated `available_providers` list.

## Examples
- `backend/services/capabilities.py` now reports local, OIDC, and SAML independently while preserving the existing auth payload shape.
- `backend/startup.py` validates secondary-provider configuration whenever those providers are exposed.
- `backend/routers/auth.py` uses `AUTH_BREAKGLASS_LOCAL` to decide whether local login remains callable when OIDC or SAML is primary.

## Anti-Patterns
- Using `AUTH_PROVIDER` to hide otherwise configured providers.
- Advertising a provider in capabilities while its backend route is still blocked by a separate primary-provider gate.
- Adding a breakglass toggle that only affects the frontend and not the backend login path.
