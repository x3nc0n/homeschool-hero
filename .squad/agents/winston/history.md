# Winston — History

## Learnings

- Project: homeschool-hero — open-source homeschool platform for families
- User: John
- Critical test areas: grading accuracy (auto-grade must be reliable), file processing (various formats/quality), grade calculations
- Auto-grading has human review — tests should verify the review queue works correctly
- Docker deployment must be testable (compose up → smoke test)
- **GitHub Repository:** https://github.com/x3nc0n/homeschool-hero
- 2026-05-08T17:04:55.759-05:00 — Backend pytest infrastructure now runs against SQLite + httpx async clients from `backend/`, with shared fixtures for auth, seeded entities, uploads, and DB reset between tests.
- 2026-05-08T17:04:55.759-05:00 — API coverage now spans auth, students, subjects, assignments, submissions, grades, quizzes, and review queue flows; grading pipeline service tests are staged with mocks and marked pending where Ray's implementation is still stabilizing.
- 2026-05-08T17:04:55.759-05:00 — `/grades/history` and the averages endpoints are currently tracked with xfail coverage because the backend route ordering still needs to settle before those gradebook queries can be enforced.
- 2026-05-08T21:36:16.718-05:00 — CI-safe backend tests now keep SQLite uploads under `backend/.pytest-state`, reuse a session-scoped schema with per-test data cleanup, and avoid a shared module-level `TestClient`.
- 2026-05-08T21:36:16.718-05:00 — Grading pipeline tests now mock Tesseract/Ollama/OpenAI behavior directly and the backend grade history/average routes are ordered so CI can assert them without xfail.
- 2026-05-08 — DX-04 quality gates now verify Alembic upgrade/downgrade safety against PostgreSQL in CI, enforce a backend coverage floor of 76%, and clear `backend/.pytest-state` before pytest to avoid stale local SQLite state.
- 2026-05-08 — Security automation now includes PR-time Gitleaks, weekly/PR CodeQL analysis, weekly Dependabot updates, and Trivy image scanning with `.trivyignore` as the reviewed exception list.
- 2026-05-08 — Release automation now publishes version-tagged containers to `ghcr.io/x3nc0n/homeschool-hero` and creates GitHub Releases from generated notes.
- 2026-05-08 — The `main` branch protection now requires `Backend quality gate`, `Migration checks`, `Frontend checks`, `Container checks`, and `Secret scan` before merge.
- 2026-05-08 — CodeQL now primes both Python and JavaScript/TypeScript dependency graphs before weekly/PR analysis and runs the broader `security-extended` plus `security-and-quality` suites for FastAPI + React coverage.
- 2026-05-08 — Trivy now scans built images for both OS and library CVEs with `.trivyignore` as the reviewed exception file, while Gitleaks uses a repo-level `.gitleaks.toml` plus PR-time scanning and documented local pre-commit setup.
- 2026-05-08T23:15:58.975-05:00 — Security issue automation now artifacts CodeQL SARIF + Trivy JSON from the `Security` workflow, opens or refreshes `security`/`severity:*`/`squad` issues for HIGH+ findings, labels reviewed suppressions, and auto-closes resolved findings on later runs.
- 2026-05-08T23:15:59.056-05:00 — IO-03 added startup migration preflight/status logging, `MIGRATION_MODE` warn/apply behavior, a Python migration CLI plus `scripts/migrate.{ps1,sh}`, rollback-notes templates/docs, and CI migration lint + upgrade/downgrade verification.
- 2026-05-08T23:15:59.056-05:00 — Focused migration/startup tests passed (`backend/tests/test_startup.py`, `backend/tests/test_migrations.py`); broader backend imports remain blocked by a pre-existing FastAPI 204 response assertion in `backend/routers/calendar.py`.
- 2026-05-08T23:15:59.056-05:00 — Startup CLI smoke checks now confirm `python -m backend.cli migrations startup-check` honors `MIGRATION_MODE=warn` and reports pending revisions without serving stale-schema errors.
- 2026-05-08T23:53:08.7185788-05:00 — SD-04 added guarded security triage and auto-patch workflows plus shared Python helpers/tests so security issues are auto-labeled as `auto-patch-eligible` or `needs-human-review`, dependency-only patches get PRs only after mirrored CI gates pass, and auto-generated PRs are labeled `auto-patch`.
- 2026-05-08T23:53:08.7185788-05:00 — Security docs now describe auto-triage behavior, the `SQUAD_AUTO_PATCH_ENABLED` disable switch, and the approval policy that keeps critical/non-dependency findings out of auto-merge.

### Phase 1 Completion (2026-05-08T22:04:55Z)
- Test infrastructure tasks 21-22 completed successfully: pytest contracts, async httpx clients, mocked dependencies ✓
- 33 tests passing: auth, CRUD, submissions, quizzes, review queue flows ✓
- All tests runnable before external dependencies (Postgres, Tesseract, Ollama) deployed
- Ready for phase 2 integration (tasks 23-24) and CI/CD integration

### Phase 3 Task DX-04 Completion (2026-05-08T22:48:51Z)
- CI/CD quality gates fully implemented: PR checks for code, migrations, frontend, container, secrets
- Backend coverage floor set to 76% with automated enforcement
- Container image security scanning with Trivy enabled; HIGH/CRITICAL failures block merge
- Dependabot automation configured for weekly dependency updates
- CodeQL analysis runs on PRs and weekly; all security checks automated
- Release automation publishes `v*` tagged containers to ghcr.io with release notes
- Alembic upgrade/downgrade verified in PostgreSQL test database
- Backend tests: 39 passed, 2 skipped; frontend build passed; Docker build verified
- All CI jobs integrated into main branch protection rules
- Committed as db55ab4 ✅ COMPLETE

### Phase 3 Task CP-01 Progress (2026-05-08T22:48:51Z)
- Ray completed multi-family tenancy work: owner bootstrap, per-user email/password sessions, family-scoped models
- Tenancy isolation enforced at router level; tenant-scoped filters in every API
- 41 tests passing (includes new tenancy isolation tests); 2 skipped
- Alembic migration: creates default family + owner account from legacy FAMILY_PASSWORD
- Frontend auth flows integrated with new per-user login
- Committed as 02b59df ✅ COMPLETE

### Team Governance Update (2026-05-08T22:48:51Z)
- User directive: OIDC + Microsoft Entra ID + SAML 2.0 authentication required
- John will integrate Entra ID; team to capture as future RBAC/SSO workstream
- All inbox decisions consolidated and merged into active registry

### Wave 3 Summary (2026-05-08T22:32:57Z)
- SD-03: Auto-issue creation with dedup and routing (commit 9dbb725) ✅ COMPLETE
- IO-03: Migration rollbacks with preflight checks (commit bff7dc6) ✅ COMPLETE
- Ray completed 5 Wave 3 deliverables: CP-04, AM-01, CP-05, IO-01, SD-01
- All decisions archived and orchestration logs finalized

### DX-03 Comprehensive test matrix (2026-05-09T04:51:12-05:00)
- Added dedicated integration, grading, edge-case, business-logic, and expanded lesson-plan/performance coverage across backend tests.
- Fixed restore backup listing (`backend/services/restore_service.py`) and validated full backend suite: 210 passed, 1 skipped; frontend build passed.
- CI now runs a Python 3.11/3.12 backend matrix by unit/integration/performance, enforces an 80% coverage gate, and posts PR test summaries; docs/testing.md documents the workflow.

### Team Architecture Sync (2026-05-09T12:25:20Z)
- Ray submitted 9 architectural decisions: AG-02 (submission versioning), AG-03 (grading hardening), AG-04 (gradebook model), AG-06 (performance strategy), AM-05 (attendance migration), DM-02 (exports), DM-03 (backups), IO-04 (observability), CI fix (ROLLBACK_NOTES + TLS 1.2).
- Venkman submitted RC-01 (report cards/ReportLab PDF), UX-03 (unified search), ESLint 9.x pin decision.
- Winston submitted SD-04 (auto-patch policy): limits auto-remediation to direct dependencies; routes CodeQL/base-image/transitive/ambiguous findings to needs-human-review.
- Security triage completed: #22 (Insecure TLS in health.py) → Ray; #23-25 (redundant test assignments) → Winston test code quality.
- All 14 inbox decisions merged to active registry; clear execution path for post-MVP production features.

### Dependency Cycle & Test Policy (2026-05-09T12:44:00Z)
- Egon completed CI action review: 6 PRs merged with clean YAML version bumps
- Ray reviewed backend deps: 8 auto-merged, 2 held (pytest 9.x major for migration, #13 duplicate governance)
- Venkman reviewed frontend deps: 1 auto-merged, 4 closed (React 19, router v7, tailwind v4 major bumps for planned sprints)
- Security triage outcome: 4 issues closed (fixes on main from prior); #22 assigned to Ray, #23-25 assigned to Winston for test code quality remediation
- **Policy reminder:** Patch-only auto-merge; major version bumps require planned migration work and explicit team sign-off
