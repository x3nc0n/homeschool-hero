# Winston — History Archive

This file contains entries from before 2026-06-09. For recent learnings, see history.md.

---

## Phase Summary (Early May 2026)

**Wave 3 Completion (2026-05-08):**
- SD-03: Auto-issue creation with dedup and routing (commit 9dbb725) ✅ COMPLETE
- IO-03: Migration rollbacks with preflight checks (commit bff7dc6) ✅ COMPLETE
- Ray completed 5 Wave 3 deliverables: CP-04, AM-01, CP-05, IO-01, SD-01
- All decisions archived and orchestration logs finalized

**Phase 1 Completion (2026-05-08T22:04:55Z):**
- Test infrastructure tasks 21-22: pytest contracts, async httpx clients, mocked dependencies ✅
- 33 tests passing: auth, CRUD, submissions, quizzes, review queue flows ✅
- All tests runnable before external dependencies deployed
- Ready for phase 2 integration and CI/CD integration

**Phase 3 Task DX-04 Completion (2026-05-08T22:48:51Z):**
- CI/CD quality gates fully implemented
- Backend coverage floor set to 76% with automated enforcement
- Container security scanning with Trivy enabled
- Release automation: version-tagged containers to ghcr.io
- All CI jobs integrated into main branch protection rules
- Alembic upgrade/downgrade verified
- Committed as db55ab4 ✅ COMPLETE

**Phase 3 Task CP-01 Progress (2026-05-08T22:48:51Z):**
- Ray completed multi-family tenancy work
- Tenancy isolation enforced at router level
- 41 tests passing (includes tenancy isolation tests)
- Alembic migration: default family + owner account setup
- Frontend auth flows integrated
- Committed as 02b59df ✅ COMPLETE

**Team Governance Update (2026-05-08T22:48:51Z):**
- User directive: OIDC + Microsoft Entra ID + SAML 2.0 authentication required
- John to integrate Entra ID
- Team to capture as future RBAC/SSO workstream

---

## Infrastructure & Testing (May 2026)

**DX-03 Comprehensive Test Matrix (2026-05-09T04:51:12-05:00):**
- Added integration, grading, edge-case, business-logic, and performance coverage
- Fixed restore backup listing service
- 210+ tests passing
- CI matrix: Python 3.11/3.12 backend by unit/integration/performance
- Coverage gate: 80%

**Team Architecture Sync (2026-05-09T12:25:20Z):**
- Ray: 9 architectural decisions (submission versioning, grading, gradebook, performance, etc.)
- Venkman: 3 decisions (report cards/PDF, unified search, ESLint)
- Winston: SD-04 (auto-patch policy)
- Security triage: 4 issues routed to Ray/Winston

**Dependency Cycle & Policy (2026-05-09T12:44:00Z):**
- Patch-only auto-merge enabled
- Major version bumps require planned migration work and sign-off
- Egon CI action review: 6 PRs merged
- Ray backend deps: 8 auto-merged, 2 held
- Venkman frontend deps: 1 auto-merged, 4 closed for planned sprints

---

## RBAC & Security Foundations (Mid-May 2026)

**PR #109 Merged & v0.9.2 Released (2026-05-15T14:09:23-05:00):**
- Breakglass enforcement fix (commit b1fd05c)
- 300 backend tests passing
- Issue #105 (PyJWT CVE-2026-32597) closed

**Breakglass Auth Implementation (2026-05-15T10:06:44-05:00):**
- Enforcement at POST /api/auth/login (not just capabilities hidden)
- AUTH_BREAKGLASS_LOCAL defaults to true
- SSO-only path covered by 403 regression test

**Multi-Provider Auth Tests (2026-05-15T07:10:40.494-05:00):**
- Added `backend/tests/test_multi_provider_auth.py`
- 4 tests pass against current behavior
- 7 intentionally skipped pending Ray/Tully implementation

**RBAC Negative-Security Coverage (2026-05-14T17:32:06-05:00):**
- Verified 11 RBAC negative-security cases
- 5 tests enforce current behavior
- 6 bearer/SAML hardening gaps as explicit skipped tests

**RBAC Test Scaffolding (2026-05-14T13:57:23-00:00):**
- 34 skipped test cases in `backend/tests/test_rbac_unified.py`
- Coverage: local session, OIDC, SAML access matrices, role extraction, role mapping, conflict resolution, JWT bearer, FamilyRole/cookie backward compatibility
- Tests anchor to provider-agnostic behavior as acceptance spec

**JWT Security Hardening (2026-05-14T22:32:06Z):**
- Orchestrated Tully JWT security hardening (PR #104)
- All 4 findings fixed: family-injection, is_owner claims, dead code, fail-closed default
- 273 tests passed/2 skipped

---

## Backend Infrastructure (Early May 2026)

**Pytest Infrastructure (2026-05-08T17:04:55.759-05:00):**
- Runs against SQLite + httpx async clients
- Shared fixtures for auth, seeded entities, uploads, DB reset

**API Coverage (2026-05-08T17:04:55.759-05:00):**
- Auth, students, subjects, assignments, submissions, grades, quizzes, review queue
- Grading pipeline service tests staged with mocks

**Gradebook Endpoints (2026-05-08T17:04:55.759-05:00):**
- /grades/history and averages endpoints tracked as xfail
- Backend route ordering still settling

**CI-Safe Backend Tests (2026-05-08T21:36:16.718-05:00):**
- SQLite uploads under `backend/.pytest-state`
- Session-scoped schema with per-test data cleanup
- No shared module-level TestClient

**Grade Pipeline Mocking (2026-05-08T21:36:16.718-05:00):**
- Tesseract/Ollama/OpenAI behavior mocked directly
- Grade history/average routes ordered for CI assertion

**Security, Release & CI Automation (2026-05-08):**
- DX-04: Quality gates verify Alembic, 76% coverage floor, clear pytest state
- Gitleaks, CodeQL, Dependabot, Trivy automation
- Release publishes to ghcr.io with generated notes
- Main branch protection: code, migration, frontend, container, secret checks
- CodeQL: primes dep graphs, runs security-extended + security-and-quality
- Trivy: scans OS and library CVEs with `.trivyignore` exceptions

**Security Automation (2026-05-08T23:15:58.975-05:00):**
- CodeQL SARIF + Trivy JSON artifacts
- Auto-issue creation, security/severity labels
- Reviewed suppressions and auto-close on resolution

**Migration Infrastructure (2026-05-08T23:15:59.056-05:00):**
- IO-03: Startup preflight, MIGRATION_MODE, Python CLI, scripts
- Rollback notes templates/docs
- CI migration lint + upgrade/downgrade verification
- Focused migration/startup tests passing
- FastAPI 204 response assertion blocker in calendar.py

**Security & Auto-Patch Policy (2026-05-08T23:53:08.7185788-05:00):**
- SD-04: Auto-triage, auto-patch workflows
- Security issues auto-labeled: auto-patch-eligible vs needs-human-review
- Dependency-only patches: PRs after mirrored CI gates
- Auto-generated PRs labeled auto-patch
- Docs: auto-triage behavior, SQUAD_AUTO_PATCH_ENABLED switch, approval policy

---

## Student Documentation (2026-05-09T13:37:25.539-05:00)

- Student guide created at `docs/student-guide.md`

---

## Additional RBAC & Contract Specs (May-June 2026)

**RBAC Unified Test Suite (2026-05-14T08:57:23-05:00):**
- Added `backend/tests/test_rbac_unified.py` as skipped spec suite
- Coverage: local sessions, OIDC, SAML, role mapping, conflict resolution, backward compatibility

**Curriculum Import Anticipatory Tests (2026-06-12T17:48:45.564-05:00):**
- Added `backend/tests/test_curriculum_import.py`
- Test-local Pydantic contract models with `extra='forbid'`
- Route-aware async API specs with `_resolve_route(...)`
- Edge cases: invalid grade levels, nested structure, special characters, size limits
- Coverage gaps noted for team follow-up

**Curriculum Test Suite Staged (2026-06-12T23:15:42Z):**
- 8 schema validation tests PASSING
- 16 integration tests SKIPPED pending Ray's endpoints
- Ready to unskip once product team locks 5 pending curriculum contract decisions
