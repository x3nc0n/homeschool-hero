# Release Decision: v0.15.0 — UI Overhaul (PR #305)

**Date:** 2026-07-10T21:01:47Z  
**Author:** Coordinator  
**Status:** COMPLETE

## Summary

PR #305 "UI Overhaul via Impeccable" was merged to main via squash commit (32dbd7c). Version v0.15.0 was tagged and released.

## Decisions

- Merge strategy: squash commit (clean history, single changeset)
- Release promotion: v0.15.0 tagged on main; GitHub Release created; GHCR image published (ghcr.io/x3nc0n/homeschool-hero:v0.15.0 and :latest)
- Dependabot PRs: 14 PRs flagged for auto-merge (squash, delete-branch); #267 rebased to start the cascade
- Skipped for later: #268 (Tailwind 3→4), #288 (action-gh-release), #289 (checkout 6→7) — all have failing tests and need dedicated migrations

## Rationale

- Squash merge keeps main clean while preserving PR history for reference
- Auto-merge on safe dependabot bumps reduces manual overhead
- Blocking high-risk migrations (Tailwind, action versions) until they can be properly scoped and tested

---

# Decision: Skip Tailwind CSS 3→4 Migration (PR #268)

**Date:** 2026-07-10T21:01:47Z  
**Author:** Coordinator  
**Status:** PENDING MIGRATION

## Decision

PR #268 (tailwindcss 3→4) is **flagged but not merged**. The upgrade is a breaking change and introduces test failures that require a dedicated migration effort.

## Rationale

- Tailwind 4 is a major version with breaking changes to config and class names
- Current PR #268 has failing tests and is not production-ready
- Scope creep: bundling with v0.15.0 release would delay other dependency bumps
- Dedicated migration PR will ensure thorough refactoring, testing, and documentation

## Next Steps

- Create a new PR for Tailwind 4 migration targeting post-v0.15.0
- Coordinate with Venkman on component class name changes
- Add migration guide to squad decisions for future reference

---

# Decision: Android File Input Pattern — sr-only over display:none

**Date:** 2026-07-10T21:01:47Z  
**Author:** Venkman  
**Context:** PR #298 reconciliation onto main after PR #305 merge

## Decision

All file/camera <input> elements in the frontend **must** use className="sr-only" (not display:none / Tailwind hidden) and be triggered via ef.current?.click() from a plain <Button onClick>.

The old pattern of <Label htmlFor="..."><Input className="hidden" .../><Button tabIndex={-1}>...</Button></Label> is **deprecated** for file inputs.

## Rationale

Android Chrome and WebView silently ignore display:none file inputs — the OS file/camera picker never opens. sr-only keeps the input reachable in the DOM while remaining visually hidden, making it work on Android without breaking other platforms.

## Scope

rontend/src/components/features/FileUpload.tsx is the reference implementation. Apply this pattern to any future file-input component in the project.

## Related

- PR #296 / PR #298 — original Android upload bug report and fix
- PR #305 — UI overhaul that introduced step-lock; created the merge conflict
- Skill: .squad/skills/android-file-input/SKILL.md

---

# Decision: PR #298 Reconciliation — Android Fix onto Overhaul

**Date:** 2026-07-10T21:01:47Z  
**Author:** Venkman  
**PR:** #298, #305

## Context

PR #298 ("Fix assignment turn-in file upload & camera on Android") was opened against the original FileUpload.tsx, but PR #305 (UI overhaul) merged a refactored FileUpload.tsx first. A merge conflict resulted, requiring reconciliation.

## Decision

**Resolve by combining both changes**: main's step-lock + canvas security logic + #298's Android sr-only inputs + ref.current.click() buttons. The Label/hidden-Input pattern is dropped in favor of sr-only + direct button click handling.

## Rationale

- Both PRs improve FileUpload.tsx: #305 adds step progression logic and security hardening; #298 fixes Android file picker
- Combining ensures users get both security improvements and platform compatibility
- sr-only pattern is more robust than hidden for input accessibility across all platforms

## Result

- Force-push to squad/296-android-upload with combined changes
- Build + lint passed
- Auto-merge enabled; PR merged into main

---



# Design Decision: Issue #411 — Headless Auth for AI Curriculum Import & Grading Upload

**Author:** Egon (Lead)  
**Date:** 2026-07-22T18:08:28-05:00  
**Status:** APPROVED — ready for implementation  
**Issue:** [#411](https://github.com/x3nc0n/homeschool-hero/issues/411)  
**Ceremony:** Design Review (security-sensitive)

---

## 1. Endpoints Requiring Headless Access

| Endpoint | Capability Required | Purpose |
|----------|-------------------|---------|
| `POST /api/curriculum/ai-import` | `manage_curriculum` | Draft AI curriculum from upload/URL |
| `POST /api/curriculum/ai-import/confirm` | `manage_curriculum` | Confirm and persist AI-generated curriculum |
| `POST /api/curriculum/import` | `manage_curriculum` | Direct JSON curriculum import |
| `POST /api/curriculum/sources/{source_id}/import/{item_id}` | `manage_curriculum` | Import from external source |
| `POST /api/submissions` | `manage_submissions` | Upload student work for grading |

**No new capability is needed.** Existing RBAC (`manage_curriculum`, `manage_submissions`) is sufficient. The missing piece is a headless credential that can carry these capabilities without an interactive browser session.

---

## 2. Design Decision: Option A — Self-Issued Family-Scoped API Token

**Chosen over Option B** (Entra SP) because:
- Zero external IdP dependency (matches self-hosted simplicity goal)
- Near-zero new verification code — existing `auth_jwt.py` bearer path handles HS256 with `JWT_SECRET`
- Single config file change in deployment (no Azure infra)

**Chosen over Option C** (breakglass local user) because:
- Tokens are stateless (no CSRF dance, no cookie management)
- Scoped capabilities (not full admin session)
- Clean programmatic lifecycle (issue → use → revoke)

---

## 3. Credential Design (Contracts)

### 3.1 Token Issuance

**New endpoint:**
```
POST /api/auth/api-tokens
Authorization: Bearer <session> or Cookie session
```

**Authorization to issue:** Caller must have `manage_security` capability (family owner only) AND the target `family_id` must match the caller's family. This ensures only the family owner can mint tokens for their own family.

**Request body:**
```json
{
  "name": "curriculum-importer",
  "capabilities": ["manage_curriculum"],
  "expires_in_days": 90
}
```

**Constraints on issuance:**
- `capabilities` MUST be a non-empty subset of: `manage_curriculum`, `manage_submissions`, `manage_grading`
- `expires_in_days` MUST be 1–365 (default: 90)
- Maximum 10 active tokens per family (prevents token sprawl)
- Token name must be unique within the family (for revocation UX)

**Response:**
```json
{
  "id": "<uuid>",
  "name": "curriculum-importer",
  "token": "<jwt>",
  "expires_at": "2026-10-20T18:08:28Z",
  "capabilities": ["manage_curriculum"],
  "family_id": 1
}
```

The `token` field is shown **only once** at creation time (write-only; not retrievable later).

### 3.2 Token Representation (JWT Claims)

```json
{
  "sub": "<owner-user-id>",
  "family_id": 1,
  "email": "<owner-email>",
  "roles": ["Teacher"],
  "jti": "<uuid>",
  "iss": "homeschool-hero",
  "aud": "homeschool-hero",
  "exp": 1729450108,
  "iat": 1721674108,
  "token_type": "api_token",
  "capabilities": ["manage_curriculum"]
}
```

**Key points:**
- `roles: ["Teacher"]` maps through `external_role_mappings` → `AppRole.teacher`
- `family_id` is baked into the token (not client-supplied via header)
- `jti` enables revocation lookup
- `token_type: "api_token"` distinguishes from OIDC/external JWTs
- `sub` is the family owner's `user_id` — the token acts as the owner

### 3.3 Token Storage (DB)

**New table: `api_tokens`**

| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID PK | Same as JWT `jti` |
| `family_id` | FK → families | |
| `created_by_user_id` | FK → users | Audit trail |
| `name` | VARCHAR(100) | Unique per family |
| `token_hash` | VARCHAR(255) | SHA-256 of the raw JWT (for lookup/audit, NOT for verification) |
| `capabilities` | JSON | `["manage_curriculum"]` |
| `expires_at` | TIMESTAMP | |
| `revoked_at` | TIMESTAMP NULL | NULL = active |
| `last_used_at` | TIMESTAMP NULL | Updated on use |
| `created_at` | TIMESTAMP | |

### 3.4 Token Verification Flow

The existing bearer path already works. Enhancement:

1. `authenticate_bearer_token` decodes the JWT (HS256 via `JWT_SECRET`)
2. **NEW:** After decode, check `jti` against `api_tokens` table:
   - If `revoked_at IS NOT NULL` → 401
   - If token not found in table → allow (supports external JWTs from OIDC)
   - If found and active → update `last_used_at`, proceed
3. `_resolve_bearer_session_claims` resolves `family_id` + `sub` → `FamilyMembership` row
4. **NEW:** If `token_type == "api_token"`, intersect token `capabilities` with role-derived capabilities (defense in depth — token can only use the caps it was issued with, even if the user's role grants more)

### 3.5 Cross-Family Prevention

**Three layers of defense:**
1. `family_id` is **embedded in the signed JWT** — cannot be altered by the client
2. `_get_authenticated_membership_row` requires a valid `FamilyMembership` row matching both `user_id` AND `family_id`
3. API token `capabilities` are scoped — even if a user belongs to multiple families, each token is bound to exactly one

### 3.6 Expiry and Revocation

| Mechanism | Implementation |
|-----------|---------------|
| Expiry | Standard JWT `exp` claim, enforced by PyJWT `decode()` |
| Explicit revocation | `DELETE /api/auth/api-tokens/{id}` — sets `revoked_at` |
| List tokens | `GET /api/auth/api-tokens` — returns metadata (never the token itself) |
| Secret rotation | Changing `JWT_SECRET` invalidates ALL self-issued tokens (nuclear option) |
| Last-used tracking | Updated on each successful auth — enables admin to identify stale tokens |

**Revocation check latency:** Direct DB lookup on `jti` per request. For a self-hosted single-family app, this is negligible. No cache needed initially.

---

## 4. Required Deliverables

### Code Changes

| File | Change | Owner |
|------|--------|-------|
| `backend/models.py` | Add `APIToken` model | Ray |
| `backend/migrations/versions/YYYYMMDD_HHMMSS_api_tokens.py` | Alembic migration for `api_tokens` table | Ray |
| `backend/routers/auth.py` | Add `POST /api/auth/api-tokens`, `GET /api/auth/api-tokens`, `DELETE /api/auth/api-tokens/{id}` | Ray |
| `backend/services/auth_jwt.py` | Add `jti` revocation check after decode; add capability intersection for `token_type=api_token` | Ray |
| `backend/services/api_tokens.py` | Token minting service (signs JWT, stores metadata) | Ray |
| `backend/config.py` | Add `API_TOKEN_MAX_PER_FAMILY` (default 10), `API_TOKEN_MAX_EXPIRY_DAYS` (default 365) | Ray |
| `.env.example` | Add `API_TOKEN_MAX_PER_FAMILY=10`, `API_TOKEN_MAX_EXPIRY_DAYS=365`; document that `JWT_ENABLED=true` + `JWT_SECRET` are required for API tokens | Ray |

### Configuration Changes (Deployment)

For API tokens to work in production:
```env
JWT_ENABLED=true
JWT_SECRET=<random-64-char-secret>
JWT_ALGORITHM=HS256
JWT_ISSUER=homeschool-hero
JWT_AUDIENCE=homeschool-hero
```

### Documentation

| Doc | Content |
|-----|---------|
| `docs/api-tokens.md` | End-user guide: how to create, use, rotate, revoke API tokens |
| `docs/automation-guide.md` | Script examples: curl for curriculum import, CI/CD integration |
| Issue #411 comment | Link to merged PR + docs |

### Tests

| Test File | Coverage |
|-----------|----------|
| `backend/tests/test_api_tokens.py` | Mint, use, expire, revoke, capability scoping, cross-family rejection, max-token limit, duplicate name, invalid capabilities |
| `backend/tests/test_auth_external.py` | Extend: bearer path with `token_type=api_token` + revocation check |
| `backend/tests/test_curriculum_ai_import.py` | Extend: headless import via API token (integration) |

---

## 5. Risks and Edge Cases

| Risk | Mitigation |
|------|-----------|
| `JWT_SECRET` leaked | Token hash stored in DB enables audit of which tokens were issued; rotation invalidates all; add to `.gitleaks.toml` pattern |
| Token used after user deactivated | `_get_authenticated_membership_row` checks `User.is_active` — deactivated user → 403 |
| Token issued with `manage_submissions` used for grading review | Capability intersection limits token to issued capabilities only |
| Family deleted | Cascade delete on `api_tokens.family_id` FK |
| Clock skew on self-hosted | PyJWT `leeway` parameter (default 0) — document that host clock must be synced |
| Token stored in plaintext by user | Docs warn to treat as password; token shown only once; can be revoked |
| Existing external JWT users (Option B future) | `jti` check is a no-op for tokens not in `api_tokens` table — external OIDC/JWKS tokens still work |

---

## 6. Acceptance Criteria (Reviewer Gate)

For Egon to approve the implementation PR:

1. ✅ `POST /api/auth/api-tokens` requires `manage_security` capability (owner-only)
2. ✅ Token `family_id` is embedded in JWT, never read from request header
3. ✅ Revoked tokens return 401 immediately (not on next expiry)
4. ✅ Capability intersection enforced — token cannot exceed its issued scope
5. ✅ Cross-family test: token for family A returns 403 when family B's data is queried
6. ✅ Token shown only at creation time; `GET` endpoint returns metadata only
7. ✅ Max token limit enforced (10 per family)
8. ✅ Alembic migration is reversible (downgrade drops table)
9. ✅ `.env.example` documents all new settings with safe defaults
10. ✅ No secrets in test fixtures or committed files
11. ✅ Tests cover: happy path, expired, revoked, wrong family, invalid capabilities, max limit

---

## 7. Assignment Decision

**Reassign from Venkman → Ray.**

Rationale: This is 100% backend Python work (auth service, JWT signing, DB migration, RBAC). Venkman (Frontend Dev) was assigned by the auto-triage bot's generic heuristic. There is no frontend UI component in the initial scope (admin token management UI can be a follow-up).

**Action items:**
- Remove `squad:venkman` label from #411
- Add `squad:ray` label
- Remove `go:needs-research` label (research complete)
- Add `status:ready` label

---

## 8. Implementation Sequence

1. **Migration + Model** — `APIToken` table
2. **Service** — `api_tokens.py` (mint, verify, revoke)
3. **JWT enhancement** — `jti` revocation check + capability intersection
4. **Router** — CRUD endpoints under `/api/auth/api-tokens`
5. **Config** — New settings + `.env.example`
6. **Tests** — Unit + integration
7. **Docs** — `api-tokens.md` + `automation-guide.md`

Branch: `squad/411-headless-api-tokens` (from `dev`)

