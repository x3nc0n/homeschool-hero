### Ray Role Derivation Fixes (2026-05-15T21:46:25.724-05:00)
- **Author:** Ray
- **Context:** Issue #112 review found that external-role auto-provisioning could fail open to `parent`, could infer `is_owner` from IdP admin claims, and could create `student_viewer` memberships without clarifying whether missing `student_id` was acceptable.
- **Decision:** Auto-provisioning now defaults empty or unmapped IdP roles to least-privilege `FamilyRole.student_viewer`, never infers `is_owner` from IdP claims, and allows `student_viewer` memberships with `student_id=None` because `FamilyMembership.student_id` is nullable; these memberships are treated as placeholder access until an explicit student linkage is granted.
- **Impact:** SSO users without recognized role claims cannot escalate to parent/admin-equivalent family access, owner authority stays DB-backed and admin-assigned only, and placeholder student viewers remain architecture-compatible without inventing synthetic student links.

### Tully OIDC Login Fix (2026-05-18T07:28:45.785-05:00)
- **Author:** Tully
- **Requested by:** John
- **Context:** A production HAR for `school.spaid.family` showed `GET /api/auth/oidc/login` ending as `200 text/html` with the SPA payload, even though the backend was handling the request and OIDC was enabled. The auth router only redirected cleanly for `OIDCConfigurationError`, leaving discovery/network/authlib failures to surface unpredictably while clients following redirects could appear to land directly on `index.html`.
- **Decision:** Treat OIDC login and callback initiation failures as fail-closed auth errors: log the exception, redirect to `/login?error=...`, and keep user-visible messages safe and actionable. Wrap OIDC login initiation failures in `backend/services/auth_oidc.py` so discovery/network errors become `OIDCConfigurationError` with meaningful messages. Add a public `/api/auth/oidc/verify` diagnostic that checks discovery reachability and reports whether the IdP metadata is usable.
- **Impact:** Users no longer loop into opaque SPA behavior when the IdP discovery URL is unreachable; they are redirected back to the login screen with a readable error. Infra can hit `/api/auth/oidc/verify` to distinguish config/discovery outages from frontend routing noise. The existing `/api/auth/oidc/login` success path still returns the upstream IdP redirect.

### Tully OIDC Role Derivation (2026-05-15T21:46:25.724-05:00)
- **Author:** Tully
- **Requested by:** John
- **Context:** OIDC external identities already arrive with normalized app roles in `identity.roles`, but the auto-provision default-family path was hard-coding `FamilyRole.parent` and `is_owner=False`. That broke RBAC expectations for admin, teacher, and student SSO users by ignoring their IdP-derived application roles.
- **Decision:** For default-family auto-provisioning only, normalize `identity.roles` through `settings.external_role_mappings`, derive `FamilyMembership.role` from app roles in `backend/services/rbac.py`, and allow ownership only for admin-derived parent memberships when the family has no accepted owner yet.
- **Impact:** Admin SSO users land as `parent`; the first accepted admin in the default family becomes owner. Teacher SSO users land as `tutor`. Student SSO users land as `student_viewer`. Empty or unmapped external roles log a warning and fail closed to the legacy default: `parent` plus `is_owner=False`. Invitation-based provisioning remains unchanged.

### Tully Security Fixes (2026-05-17T21:57:29.677-05:00)
- **Author:** Tully
- **Requested by:** John
- **Decision:** Sanitize control characters in backend log messages, correlation IDs, action labels, and structured detail payloads before formatting or emitting logs. Resolve upload destinations from normalized relative paths only, and reject absolute paths plus any parent-directory traversal before writing submission files. Redact all 5xx HTTP responses to the generic `internal_error` payload so stack traces and exception details stay in logs only.
- **Impact:** Closes the backend CodeQL/Trivy findings for log injection, path injection, stack-trace exposure, and the vulnerable PyJWT pin. Keeps auth/security behavior fail-closed: suspicious upload paths are rejected, user-controlled log fields cannot forge entries, and clients never receive server exception details.

### Venkman Service Worker Denylist (2026-05-18T07:55:09.535-05:00)
- **Author:** Venkman
- **Requested by:** John
- **Context:** The generated PWA service worker was treating every browser navigation as SPA territory. That let Workbox serve `index.html` for backend-owned navigation requests like `/api/auth/oidc/login` and `/api/auth/oidc/callback`, which breaks OIDC redirects and can also mask direct navigations to uploaded files or health endpoints.
- **Decision:** Add a Workbox navigation denylist in `frontend/vite.config.ts` for `/api/*`, `/uploads/*`, and `/health` so those requests bypass the SPA fallback. Mirror the same exclusions in the navigation runtime cache rule so backend navigations are never cached as app pages. Enable `skipWaiting` and `clientsClaim` so fixed service workers activate promptly on the next visit.
- **Impact:** Browser-driven OIDC login and callback navigations now reach the backend instead of loading the SPA shell. Direct navigation to uploaded files and health checks remains backend-owned. Existing users pick up the corrected service worker without waiting through an extra release cycle.

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

# Venkman ESLint upgrade

- Date: 2026-05-18T16:38:51.741-05:00
- Requester: John
- Scope: frontend dependency maintenance

## Decision

Upgrade `frontend` to `eslint@^10.4.0` and `@eslint/js@^10.0.1` together, and commit `frontend/.npmrc` with `legacy-peer-deps=true` as a temporary install compatibility shim.

## Why

- Dependabot PR #92 (`@eslint/js` 10) conflicts with ESLint 9 because `@eslint/js@10.0.1` declares `peerOptional eslint@^10.0.0`.
- Dependabot PR #136 (`eslint` 10) should not land separately from the `@eslint/js` major bump because the flat config imports `@eslint/js` directly.
- `eslint-plugin-jsx-a11y@6.10.2` is still the latest release and only declares peer support through ESLint 9, but linting still passes with ESLint 10 in this repo.
- The `.npmrc` shim keeps `npm install` working without dropping accessibility lint coverage.

## Validation

- `cd frontend && npm install`
- `cd frontend && npm run lint`
- `cd frontend && npm run build`

## Ray Security Hardening Batch

- Date: 2026-06-09T17:21:25-05:00
- Context: Issue batch #183, #178, #181, and #180 tightened CI supply-chain controls, migration configuration, reverse-proxy trust, and TLS edge headers.
- Decision:
  - Default backend behavior will **not** trust `X-Forwarded-*` headers; operators must explicitly set `TRUST_PROXY_HEADERS=true` when the app is deployed behind a trusted reverse proxy.
  - Alembic runtime database selection remains owned by `backend/migrations/env.py` via application settings, and `backend/alembic.ini` stays credential-free.
  - Nginx TLS termination includes explicit frame, MIME sniffing, CSP, referrer, and permissions headers as baseline edge hardening.
- Rationale:
  - Default-deny proxy header trust prevents spoofed client IP and scheme headers from weakening rate limiting or cookie security on direct app access.
  - Removing fallback credentials from Alembic avoids shipping a secret-like connection string in repo config while preserving existing migration behavior.
  - Edge security headers provide consistent browser-side protections even before requests hit the app.

# Security Triage: CodeQL Findings Wave 1 (2026-06-09)

**Author:** Egon (Lead)  
**Date:** 2026-06-09T09:58:09.392-05:00  
**Status:** COMPLETE — All 9 issues triaged and assigned  

---

## Summary

Processed 9 open security findings from CodeQL automated scanning (2026-06-08 run). All issues had the `squad` label but lacked individual `squad:{member}` assignment. Routing completed based on code domain and vulnerability type.

## Routing Logic

### Frontend Issues → Venkman (squad:venkman)
- **Domain:** React/TypeScript frontend code
- **Vulnerability type:** DOM-based XSS (js/xss-through-dom)
- **Issues:** #167, #168 (both FileUpload.tsx)

### Backend Issues → Ray (squad:ray)
- **Domain:** Python backend services/routers
- **Vulnerability types:**
  - **Log Injection** (py/log-injection): #169 → logging_config.py:164
  - **Path Traversal** (py/path-injection): #170–172 → storage.py (lines 97, 125, 126)
  - **Stack Trace Exposure** (py/stack-trace-exposure): #173–175 → main.py:567, auth.py:344, health.py:23

## Findings Summary

### Frontend (2 issues)
| Issue | Type | Location | Impact | Remediation |
|-------|------|----------|--------|-------------|
| #167 | js/xss-through-dom | FileUpload.tsx:321 | HIGH: DOM text reinterpreted as HTML | Use textContent, contextual escaping, or React safe methods |
| #168 | js/xss-through-dom | FileUpload.tsx:319 | HIGH: DOM text reinterpreted as HTML | Use textContent, contextual escaping, or React safe methods |

### Backend (7 issues)

#### Log Injection (1 issue)
| Issue | Type | Location | Impact | Remediation |
|-------|------|----------|--------|-------------|
| #169 | py/log-injection | logging_config.py:164 | HIGH: Unsanitized user input in logs | Remove newlines/CR from input; use structured logging |

#### Path Traversal (3 issues)
| Issue | Type | Location | Impact | Remediation |
|-------|------|----------|--------|-------------|
| #170 | py/path-injection | storage.py:125 | HIGH: User-controlled path construction | Normalize with os.path.normpath(); validate safe directory |
| #171 | py/path-injection | storage.py:126 | HIGH: User-controlled path construction | Normalize with os.path.normpath(); validate safe directory |
| #172 | py/path-injection | storage.py:97 | HIGH: User-controlled path construction | Normalize with os.path.normpath(); validate safe directory |

#### Stack Trace Exposure (3 issues)
| Issue | Type | Location | Impact | Remediation |
|-------|------|----------|--------|-------------|
| #173 | py/stack-trace-exposure | main.py:567 | HIGH: Stack trace exposed to user | Log server-side; return generic error response |
| #174 | py/stack-trace-exposure | auth.py:344 | HIGH: Stack trace exposed to user | Log server-side; return generic error response |
| #175 | py/stack-trace-exposure | health.py:23 | HIGH: Stack trace exposed to user | Log server-side; return generic error response |

## Grouping & Comments

**Frontend (DOM-XSS):** #167 and #168 grouped as affecting the same component (FileUpload.tsx) and vulnerability class.

**Backend (Path Traversal):** #170–172 all located in storage.py service; grouped with common remediation strategy.

**Backend (Stack Trace):** #173–175 spread across main.py, auth.py, and health.py but share the same information-disclosure pattern; grouped with unified remediation approach.

## Team Assignments

- **Venkman:** #167–168 (frontend XSS hardening in FileUpload component)
- **Ray:** #169–175 (backend security: log injection, path validation, error handling)

## Next Steps

- Ray reviews and prioritizes backend fixes (7 issues).
- Venkman reviews and prioritizes frontend fixes (2 issues).
- Both teams post resolution PRs with test coverage for each remediation.
- All items removed from squad triage inbox once resolved.

# Security Fix Decisions — 2026-06-09

**Author:** Ray (Backend Dev)  
**Date:** 2026-06-09T10:01:15-05:00  
**Issues closed:** #169, #170, #171, #172, #173, #174, #175

---

## Context

CodeQL flagged 7 HIGH-severity vulnerabilities across three CWE categories. All were in existing backend code. Fixes were kept surgical — no behaviour change for correctly-behaving requests.

---

## Decision 1 — Path Injection (CWE-22) in `storage.py`

**Problem:** `_resolve_safe_upload_destination()` used `Path.resolve()` + `Path.relative_to()` to validate upload destinations. CodeQL's `py/path-injection` query did not recognise `relative_to()` as a sanitiser; the returned `Path` object was still tracked as user-tainted by its dataflow engine, causing lines 97, 125, 126 to be flagged.

**Decision:** Replace `(upload_root_path / candidate).resolve()` + `relative_to()` with `os.path.realpath(os.path.join(root_real, normalized))` + `destination.startswith(root_real + os.sep)`. This is the exact pattern CodeQL's Python sanitiser library recognises. The `+ os.sep` suffix is kept to prevent prefix-collision (e.g. `/uploads-extra` matching a root of `/uploads`). The existing `..`-component check is retained as defence-in-depth.

---

## Decision 2 — Stack Trace Exposure (CWE-209) in health endpoints

**Problem:** `build_simple_health_payload()` is called from both `main.py:health_alias()` and `routers/health.py:health()`. Any uncaught exception in that call chain would have propagated to FastAPI's global handler — which does return a generic response — but CodeQL's `py/stack-trace-exposure` query traced service-check exception strings (e.g. `str(exc)` in capabilities probing) as flowing into the response.

**Decision:** Wrap both call sites in `try/except Exception`; log the full exception server-side with `logger.exception()`; return a minimal fixed-shape 503 body `{'status': 'error', 'ready': False}`. This is belt-and-suspenders: the global handler already sanitises, but the explicit guard breaks the taint chain and is also more resilient to future changes.

---

## Decision 3 — Stack Trace Exposure (CWE-209) in OIDC verify endpoint

**Problem:** `_oidc_provider_error_detail()` in `auth_oidc.py` had a catch-all `detail = str(exc).strip(); return detail or None` that could expose raw exception messages (e.g. connection strings, internal hostnames) for any unclassified exception via the `/auth/oidc/verify` JSON response.

**Decision:** Remove the `str(exc)` fallback. Unclassified exceptions now log at `DEBUG` level (full context for operators) and return `None`, causing callers to fall back to the existing generic message. Known exception types (`OAuthError`, `httpx.HTTPStatusError`, `httpx.RequestError`) continue to return structured, safe descriptions — those were already safe.

---

## Decision 4 — Log Injection (CWE-117) in `logging_config.py`

**Problem:** CodeQL's `py/log-injection` query flags any user-controlled value that reaches `logger.log()` without a recognised sanitiser at the call site. Although `_sanitize_log_text()` and `_coerce_details()` were called inside the `extra={}` dict literal passed directly to `logger.log()`, CodeQL did not trace through those calls as sanitisers when they appeared as inline expressions inside the argument.

**Decision:** Pre-compute `sanitized_message`, `sanitized_correlation_id`, `sanitized_action`, `sanitized_details` as local variables *before* the `logger.log()` call. The dataflow engine can now see that only sanitised values enter the log sink. Functionally identical — no change to log output.

---

## Test impact

- 359 tests pass, 1 skipped, 1 xfailed (null-byte path rejection marked `xfail` because OS behaviour varies).
- No existing tests modified; all new security regression tests added by John in `test_security_hardening.py` and `test_logging_monitoring.py` now pass.

# Decision: XSS Sanitization at Render Site (not just setter)

**Author:** Venkman  
**Date:** 2026-06-09T10:01:15-05:00  
**Issues closed:** #167, #168  
**Commit:** b3ef0b5

## Decision

When a value derived from DOM/file-input sources flows through React state into an HTML attribute that is an XSS sink (`src`, `data`, `href`, etc.), the sanitization/validation check **must appear at the render callsite**, not only inside the event handler that sets the state.

## Rationale

CodeQL's `js/xss-through-dom` taint analysis does not "see through" React `useState` — a guard inside `onFileChange` is invisible to the taint path ending at JSX attributes in the render. The result is a true-positive-ish finding: the code is technically safe at runtime (because `URL.createObjectURL` always returns `blob:` URLs), but the security invariant is not statically verifiable.

## Pattern Applied

```tsx
// BAD — sanitization invisible to taint analysis at render site
const objectUrl = URL.createObjectURL(picked)
if (!objectUrl.startsWith('blob:')) return  // guard buried in handler
setPreviewUrl(objectUrl)
// ... later in JSX:
<img src={previewUrl} />  // CodeQL still flags this

// GOOD — sanitization explicit at render callsite
const safePreviewUrl = previewUrl.startsWith('blob:') ? previewUrl : ''
<img src={safePreviewUrl} />  // taint path is broken here
```

## Scope

This pattern should be applied to **any** tainted value (user input, file input, DOM text, URL parameters) that flows through state into: `src`, `href`, `data`, `action`, `formAction`, or any attribute that browsers may treat as a navigable/executable URL.

## Files Changed

- `frontend/src/components/features/FileUpload.tsx` — added `safePreviewUrl` computed at render time, replaced `previewUrl` in `img src` and `object data` attributes.


## Governance

- All meaningful changes require team consensus
- Document architectural decisions here
- Keep history focused on work, decisions focused on direction
