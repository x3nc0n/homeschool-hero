# Ray CI setup decision

- Date: 2026-05-08T21:36:16.718-05:00
- Author: Ray
- Context: John requested GitHub Actions CI for push and pull request validation on `main`, and the current backend pytest suite already forces a SQLite test database in `backend/tests/conftest.py`.
- Decision: Use SQLite for the backend CI test job instead of provisioning PostgreSQL, while still installing `tesseract-ocr` and running verbose pytest with coverage from `backend/`.
- Impact: CI stays aligned with the existing Winston/Ray backend test strategy, remains faster to execute, and avoids introducing a database service the current suite does not exercise.
