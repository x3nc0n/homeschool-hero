# Winston CI Test Reliability

- **Date:** 2026-05-08T21:36:16.718-05:00
- **Context:** GitHub Actions test runs need the backend suite to pass without PostgreSQL, Tesseract, Ollama, or OpenAI services.
- **Decision:** Keep the backend pytest suite SQLite-first in CI, store upload artifacts under `backend/.pytest-state`, mock OCR/AI service calls in tests, and keep static `/grades/history` and average routes ahead of `/{grade_id}` so coverage stays deterministic.
- **Impact:** CI can execute `cd backend && python -m pytest -v` without external service containers, while review-queue tests remain safe to skip only when no review jobs are seeded.
