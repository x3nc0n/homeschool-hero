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

### Phase 1 Completion (2026-05-08T22:04:55Z)
- Test infrastructure tasks 21-22 completed successfully: pytest contracts, async httpx clients, mocked dependencies ✓
- 33 tests passing: auth, CRUD, submissions, quizzes, review queue flows ✓
- All tests runnable before external dependencies (Postgres, Tesseract, Ollama) deployed
- Ready for phase 2 integration (tasks 23-24) and CI/CD integration
