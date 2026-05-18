# Ray bcrypt 5.0 Upgrade Guardrail

- **Date:** 2026-05-18T16:38:51.741-05:00
- **Requested by:** John

## Decision
- Do not rely on bcrypt 5.0 silent truncation behavior; enforce a 72-byte UTF-8 password limit before any local-auth bcrypt hash or check reaches the library.
- Apply the guardrail at the API schema layer for register, login, and invitation acceptance so clients get a validation error instead of a server error.
- Keep backend defensive checks in `hash_password()` / `verify_password()` and fail early during the legacy family-password migration when `FAMILY_PASSWORD` exceeds bcrypt's limit.

## Impact
- PR #94 can merge safely once these guardrails are on main because local auth no longer depends on bcrypt 4.x truncation.
- Existing and future operators get a clear validation or startup error instead of unpredictable bcrypt exceptions when a password exceeds 72 UTF-8 bytes.
