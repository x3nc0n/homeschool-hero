# Ray SD-01 Hardening

## Context
- Backend auth already used signed cookies, but session security, CSRF protection, lockout controls, and rate limiting were incomplete.
- The backend also needed safer validation/error behavior for uploads and malformed payloads without adding deployment-only dependencies.

## Decision
- Keep the signed-cookie session model, but harden it with secure cookie flags, SameSite=Lax, separate CSRF cookies, expiry-aware rotation, and structured security middleware.
- Use an in-process scoped rate limiter for auth/upload/export/general API traffic so limits can key off the current signed session or client IP without introducing new infrastructure.
- Enforce password policy and account lockout in the auth layer, and centralize request validation hardening plus upload MIME/size checks in backend validation/middleware paths.

## Impact
- Sensitive state-changing endpoints now require matching CSRF tokens, authenticated traffic gets consistent security headers, and abusive request patterns are throttled before handler logic runs.
- Registration/login/upload failures now return structured non-leaky error payloads, while backend tests cover the new protections end-to-end.
