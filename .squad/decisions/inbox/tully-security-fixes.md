# Tully Security Fixes

- **Date:** 2026-05-17T21:57:29.677-05:00
- **Requested by:** John

## Decision
- Sanitize control characters in backend log messages, correlation IDs, action labels, and structured detail payloads before formatting or emitting logs.
- Resolve upload destinations from normalized relative paths only, and reject absolute paths plus any parent-directory traversal before writing submission files.
- Redact all 5xx HTTP responses to the generic `internal_error` payload so stack traces and exception details stay in logs only.

## Impact
- Closes the backend CodeQL/Trivy findings for log injection, path injection, stack-trace exposure, and the vulnerable PyJWT pin.
- Keeps auth/security behavior fail-closed: suspicious upload paths are rejected, user-controlled log fields cannot forge entries, and clients never receive server exception details.
