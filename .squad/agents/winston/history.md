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

### Phase 1 Completion (2026-05-08T22:04:55Z)
- Test infrastructure tasks 21-22 completed successfully: pytest contracts, async httpx clients, mocked dependencies ✓
- 33 tests passing: auth, CRUD, submissions, quizzes, review queue flows ✓
- All tests runnable before external dependencies (Postgres, Tesseract, Ollama) deployed
- Ready for phase 2 integration (tasks 23-24) and CI/CD integration
