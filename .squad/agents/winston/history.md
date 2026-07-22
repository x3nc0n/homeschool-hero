# Winston — History

## Learnings

- 2026-07-22T18:07:07.184-05:00 — **Issue #411 Test Spec — Headless API Token Acceptance Coverage.** Ray is implementing family-scoped revocable API tokens for Issue #411. Test spec required per acceptance criteria (11 gates): RBAC enforcement (family owner `manage_security`), family-scoped JWT embedding, immediate revocation via JTI lookup, capability intersection in bearer auth, cross-family rejection (token for family A → 403 on family B query), metadata-only list endpoint, max token limit enforcement (10 per family), reversible Alembic migration, no secrets in test fixtures, and happy path + edge cases (expired, revoked, wrong family, invalid capabilities). Test framework: `backend/tests/test_api_tokens.py` for unit tests, extend `backend/tests/test_auth_external.py` for bearer path with `token_type=api_token`, extend `backend/tests/test_curriculum_ai_import.py` for headless integration (curriculum import via API token). Deliverable: 12+ test cases spanning issuance, usage, expiry, revocation, RBAC, cross-family, limit enforcement. Coverage estimate: 15 tests total (8 unit, 4 bearer/revocation, 3 integration).

- 2026-06-12T17:18:11.955-05:00 — **School Year Setup Wizard test spec added** in `backend/tests/test_calendar_setup_wizard.py`. Pattern match: backend API tests use async `httpx` clients from `tests/conftest.py`, `tests.contracts` payload helpers, and `require_route(...)` to skip contract specs until a route exists. Coverage decision: keep currently supported setup behaviors live (date-order validation, event-range validation, leap-day/mid-year/summer-session creation, tutor-vs-student-viewer RBAC), but mark overlap and unreasonable-range guardrails as `xfail` because issue #164 requires them and the current calendar API does not enforce them yet. Edge cases called out for Ray/Venkman: leap-year `2028-02-29`, January mid-year starts, short summer sessions, and a future `POST /api/calendar/school-years/{school_year_id}/holiday-presets` bulk-add path for federal/state presets that is currently staged as skipped acceptance coverage.

- 2026-06-09T10:03:03-05:00 — **Security regression tests written** for Ray and Venkman's security fixes. 20 new tests added: 10 path traversal unit tests in `test_security_hardening.py` (covering `..`, absolute paths, URL-encoded `..`, double-encoded `..`, null bytes, valid paths), 6 stack trace exposure tests (auth and health routes via `app.dependency_overrides` and module-level monkeypatching), and 7 log injection tests in `test_logging_monitoring.py` (bind_context sanitization, ConsoleFormatter, JsonFormatter single-line enforcement, details dict injection). Key patterns: use `app.dependency_overrides[dep]` (not module-level monkeypatch) to override FastAPI `Depends()` in tests; monkeypatching module imports works for functions called directly but NOT for captured `Depends()` references. Null byte path test marked `xfail` — platform-dependent and targets Ray's fix. 38 pass + 1 xfail against security files; 359 passed full suite.

- 2026-06-12T17:48:45.564-05:00 — **Curriculum Import Phase 1 anticipatory tests added** in `backend/tests/test_curriculum_import.py`. Pattern match: staged feature specs can stay useful by combining test-local contract models (Pydantic with `extra='forbid'`) for payload/schema validation that passes today, plus route-aware async API specs that call `_resolve_route(...)` and skip cleanly until Ray lands the endpoints. Edge cases captured now: invalid grade levels, nested lessons outside units, duplicate subject names, special characters, long descriptions, and 1000+ lesson payload size pressure. Coverage gaps/decisions noted for team follow-up: empty-curriculum behavior, cross-family 403 vs 404 semantics, activation idempotency, calendar/date assignment rules, and concurrency guarantees.

- 2026-06-12T23:15:42Z — **Curriculum test suite staged and ready.** 8 schema validation tests PASSING (JSON contract validation, nested structure enforcement, size limits). 16 integration tests SKIPPED pending Ray's `/api/curriculum/*` endpoints (PR #229). Full test harness operational with no code blockers. Ready to unskip once Ray's backend merges and product team locks 5 pending curriculum contract decisions: (1) empty curriculum behavior, (2) cross-family access semantics, (3) activation repeat/idempotency, (4) activation calendar linkage, (5) import size/concurrency guarantees.

---

## Archived Entries

Earlier work on pytest infrastructure, RBAC foundations, security regression testing, and CI/CD automation is documented in `history-archive.md`.

## Recent Activity Summary

**Issue #411 — Headless Auth Token Test Spec (2026-07-22)**
- Design review approved; Ray assigned for implementation
- 15 test cases required across unit, bearer, and integration layers
- Test framework prepared for API token lifecycle (issue, use, revoke, expire)
- Cross-family and capability isolation tests specified

**Curriculum Test Suite (2026-06-12)**
- Phase 1 anticipatory tests: schema validation (8 tests passing), integration (16 skipped)
- Pending Ray's implementation and product team contract decisions
- Edge cases documented for follow-up

**Security Testing (2026-06-09)**
- Path traversal, stack trace exposure, and log injection regression tests
- 359 full suite tests passing; 38 security-focused tests validated
