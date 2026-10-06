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
Authorization: ****** or Cookie session
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

---

# Security Amendment: Issue #411 — API Token Design Gaps

**Author:** Egon (Lead)  
**Date:** 2026-07-22T18:07:07-05:00  
**Status:** APPROVED — supersedes ambiguous clauses in the original decision  
**Supersedes:** Section 3.4 verification flow bullet 2; Section 3 constraint list; Sections 4 and 5 partially  
**Context:** Winston pre-implementation review identified five design gaps  

---

## Gap 1: `token_type=api_token` MUST require registered `jti`

**Ruling:** The original decision's "If not found in table → allow" applies ONLY to tokens WITHOUT `token_type: "api_token"` in their claims (i.e., external OIDC/JWKS JWTs).

**Amended verification flow** (replaces Section 3.4 bullet 2):

1. Decode JWT (HS256 via `JWT_SECRET`; JWKS for external).
2. Read `token_type` claim:
   - If `token_type == "api_token"`:
     - `jti` claim is **required** — missing `jti` → 401.
     - Look up `jti` in `api_tokens` table:
       - Not found → **401** ("API token is not registered").
       - `revoked_at IS NOT NULL` → **401** ("API token has been revoked").
       - `expires_at < now` (belt-and-suspenders with JWT `exp`) → **401**.
       - Found and active → update `last_used_at`, proceed.
   - If `token_type` is absent or any other value (external JWT):
     - **Skip** `api_tokens` table lookup entirely. Proceed with existing external JWT path.
3. Continue to `_resolve_bearer_session_claims` as before.

**Rationale:** An `api_token`-typed JWT that bypasses the DB creates an unrevocable credential. External JWTs are trusted via signature verification against JWKS — they have no reason to exist in `api_tokens`.

---

## Gap 2: GET/DELETE `/api/auth/api-tokens` authorization

**Ruling:** All three API token management endpoints share identical authorization:

| Endpoint | Method | Capability Required | Family Scope |
|----------|--------|-------------------|--------------|
| `/api/auth/api-tokens` | POST | `manage_security` | Caller's `family_id` only |
| `/api/auth/api-tokens` | GET | `manage_security` | Caller's `family_id` only |
| `/api/auth/api-tokens/{id}` | DELETE | `manage_security` | Caller's `family_id` only |

**Implementation:**
- Use `require_capabilities(Capability.manage_security, action='manage API tokens')` as a FastAPI dependency on all three routes.
- The query/delete MUST filter by `WHERE family_id = auth.family_id`. Never accept a client-supplied `family_id` parameter.
- Attempting to DELETE a token belonging to a different family → **404** (do not confirm existence).

**Cross-family access attempt → HTTP 404** (not 403, to avoid family enumeration).

---

## Gap 3: `manage_grading` is included as a delegatable capability

**Ruling:** YES — `manage_grading` is a valid delegatable capability for API tokens.

**Allowed delegated capabilities (complete list):**
```python
DELEGATABLE_CAPABILITIES = {
    "manage_curriculum",
    "manage_submissions",
    "manage_grading",
}
```

**Endpoints authorized by `manage_grading`:**

| Endpoint | Current Auth | Note |
|----------|-------------|------|
| `POST /api/grading/review/{job_id}` | `require_teacher()` | Must add capability check |
| `GET /api/grading/jobs` | `require_teacher()` | Must add capability check |
| `GET /api/grading/review-queue` | `require_teacher()` | Must add capability check |

**Implementation note for Ray:** The grading router currently uses `require_teacher()` (role-based). For API token compatibility, these endpoints MUST transition to `require_capabilities(Capability.manage_grading, action='...')`. Since `manage_grading` is already granted to `AppRole.teacher` and `FamilyRole.parent/co_parent/tutor`, this is not a behavioral change for interactive users — only an enablement for API tokens whose `effective_capabilities` include `manage_grading` via intersection.

**`manage_security` is explicitly NOT delegatable.** Attempting to include `manage_security` in a token's `capabilities` array → **400 Bad Request** with detail: "manage_security cannot be delegated to API tokens."

---

## Gap 4: Max-active-token enforcement (SQLite-safe)

**Ruling:** Do NOT use `SELECT FOR UPDATE`. The app supports SQLite where row-level locking does not exist.

**Strategy — count-then-insert with unique constraint:**

1. **Database constraint:** Add a `UNIQUE(family_id, name)` constraint on `api_tokens` table (enforces duplicate-name rejection at the DB level regardless of race conditions).

2. **Application-level count check:**
   ```
   count = SELECT COUNT(*) FROM api_tokens
            WHERE family_id = :fid AND revoked_at IS NULL AND expires_at > now()
   if count >= max_active_per_family:
       raise 409
   INSERT INTO api_tokens (...)
   ```

3. **Concurrency safety:** In the unlikely event of a race (two concurrent create requests), both will pass the count check but one may exceed the limit by 1 token. This is acceptable for a self-hosted single-family app. The unique name constraint ensures no duplicates, and the limit is a soft cap — list/revoke endpoints allow the owner to clean up.

4. **Testing approach:**
   - Unit test: Seed exactly `max - 1` tokens, create one more (succeeds), attempt another (fails with 409).
   - Do NOT write concurrent-race tests that depend on timing — they are flaky in CI. The unique name constraint is the correctness guarantee; the count check is UX.

**HTTP statuses for token creation errors:**

| Condition | Status | Detail |
|-----------|--------|--------|
| Duplicate name within family | **409 Conflict** | "A token named '{name}' already exists in this family." |
| Active token limit reached | **409 Conflict** | "Maximum active API tokens ({limit}) reached for this family." |
| Invalid/non-delegatable capability | **400 Bad Request** | "Invalid or non-delegatable capability: '{cap}'." |
| `expires_in_days` out of range | **422 Unprocessable Entity** | (standard Pydantic validation) |

---

## Gap 5: Capability intersection — exact code layer

**Ruling:** Intersection happens in `security.py::_resolve_bearer_session_claims`, BEFORE constructing the `SessionClaims` dict.

**Amended flow:**

1. `auth_jwt.py::_build_bearer_claims` reads `capabilities` claim from the JWT and stores it on a new field: `BearerSessionClaims.token_capabilities: list[str] | None` (default `None`).
   - For `token_type=api_token`: populated from the JWT `capabilities` claim.
   - For external JWTs: remains `None`.

2. `security.py::_resolve_bearer_session_claims`:
   - Resolves the membership row (existing behavior).
   - Constructs an `AuthSession` via `_auth_session_from_bearer_claims` (existing behavior).
   - **NEW:** If `bearer_claims.token_capabilities is not None`:
     - Compute role-derived `effective_capabilities` from the user's `family_role + app_roles + is_owner` (using `derive_effective_capabilities`).
     - Intersect: `final_caps = role_derived_caps ∩ set(bearer_claims.token_capabilities)`.
     - Store `final_caps` in the `SessionClaims['effective_capabilities']` field (or equivalent mechanism passed to `AuthSession`).
   - If `bearer_claims.token_capabilities is None` (external JWT): no intersection — derive capabilities from roles as normal.

3. `AuthSession.__post_init__` already respects a pre-populated `effective_capabilities` set (it only calls `derive_effective_capabilities` when the set is empty). So the intersection result flows through without change to downstream `has_capability()` checks.

**Why this layer:** `_resolve_bearer_session_claims` is the single point where we have BOTH the decoded token claims AND the database-resolved membership/role. It's after the DB lookup (so role-derived caps are available) and before the `SessionClaims` is cached on `request.state.session`.

**External JWT behavior preserved:** External JWTs never set `token_capabilities`, so they continue to derive full role-based capabilities as today.

---

## Summary of HTTP Status Codes (authoritative)

| Scenario | Status |
|----------|--------|
| Missing/invalid bearer token | **401** |
| `token_type=api_token` with missing `jti` | **401** |
| `token_type=api_token` with unregistered `jti` | **401** |
| `token_type=api_token` with revoked `jti` | **401** |
| Expired JWT (any type) | **401** |
| Valid token, user deactivated | **403** |
| Valid token, capability insufficient | **403** |
| Cross-family data access | **403** |
| DELETE/GET token belonging to different family | **404** |
| Create token: duplicate name | **409** |
| Create token: active limit exceeded | **409** |
| Create token: non-delegatable capability | **400** |
| Create token: invalid request body | **422** |

---

## Implementation Green Light

**Status: GREEN — Ray may proceed.**

All five design gaps are resolved. This amendment plus the original decision document constitute the complete specification. Ray should reference both when implementing.

**Priority order for implementation:**
1. `BearerSessionClaims.token_capabilities` field + `_build_bearer_claims` population (Gap 5)
2. `jti` validation logic branched on `token_type` (Gap 1)
3. Capability intersection in `_resolve_bearer_session_claims` (Gap 5)
4. `api_tokens` table with `UNIQUE(family_id, name)` constraint (Gap 4)
5. Token service with count-based limit enforcement (Gap 4)
6. Router: POST/GET/DELETE with `require_capabilities(Capability.manage_security)` (Gap 2)
7. Grading router migration to `require_capabilities(Capability.manage_grading)` (Gap 3)
8. Tests covering all status codes above

---

# Design Decision: Bulk Assignment Import Workflow

**Date:** 2026-10-06T10:13:08-05:00  
**Author:** Egon  
**Status:** COMPLETE  
**Outcome:** Design document finalised in docs/design/bulk-assignment-import.md

## Summary

Implemented a safe, preview-first bulk assignment import workflow with backend models, API endpoints, frontend wizard, and comprehensive security testing. Upload `.txt`, `.md`, `.docx`, or `.pdf`; extract text; parse with AI into structured drafts; resolve references; clarify missing fields; preview/edit; and confirm transactional creation.

## Key Implementation Details

- **Backend:** DBsession persistence via `BulkAssignmentImportSession` model; draft rows stored separately; AI extraction reuses existing curriculum import stack.
- **Frontend:** Embedded Assignments-page wizard with sr-only file input (Android-safe) + drag/drop; upload defaults reduce clarifications; row skipping preserved on confirm.
- **Security:** All endpoints require `Capability.manage_curriculum`; LLM never supplies trusted IDs; RBAC enforced; 20 security tests passed.
- **API Deviations:** Create-draft returns metadata (`source_content_type`, `source_size_bytes`, `revision`, `expires_at`, `created_at`, `updated_at`) plus empty items; GET endpoint returns full editable list; AI-unavailable is 503 with specific error code.

---

# Ray Backend Implementation Notes — Bulk Assignment Import

**Date:** 2026-10-06T10:16:18.437-05:00  
**Author:** Ray  
**Status:** COMPLETE  
**Outcome:** 46 tests passed

## Deviations / Contract Clarifications

- Create draft returns the design response plus persisted metadata fields needed by the frontend confirm flow: `source_content_type`, `source_size_bytes`, `revision`, `expires_at`, `created_at`, and `updated_at`.
- Create draft intentionally returns `items: []`; `GET /api/assignment-import-sessions/{session_id}` returns the full editable item list. This keeps upload responses smaller and matches the design note that create may omit items.
- AI-unavailable response is `503` with `{"detail":"AI assignment import is unavailable","code":"ai_import_unavailable"}`.

The authoritative design doc API section was updated to reflect these clarifications.

---

# Venkman Frontend Implementation — Bulk Assignment Import

**Date:** 2026-10-06T10:16:18-05:00  
**Author:** Venkman  
**Status:** COMPLETE  
**Outcome:** Build/lint/test pass

## Implementation Decisions

- Implemented the frontend as an embedded Assignments-page wizard instead of adding a new route, keeping assignment creation context in one place.
- Used Android-safe native file input (`sr-only` + ref-click) for the picker, plus drag/drop for desktop.
- Added optional upload defaults for subject, students, grading period, and due date so parents can reduce clarification questions without changing the backend contract.
- Treat row removal as "skip on confirm" by unselecting items, preserving backend draft rows and avoiding an undocumented delete-row patch contract.
- Display AI-unavailable 503 responses as an admin-configuration message and keep the regular assignment form available.

---
