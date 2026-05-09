# Testing

## Local commands

- Backend quick run:
  - `cd backend`
  - `python -m pytest -q`
- Backend with coverage:
  - `cd backend`
  - `python -m pytest -q --cov=backend --cov-report=term-missing --cov-report=xml:coverage.xml --cov-fail-under=80`
- Frontend build verification:
  - `cd frontend`
  - `npm run build`

## Test categories

- **Unit/API**: default backend suite for routers, schemas, services, auth, and business rules.
- **Integration** (`-m integration`): multi-step end-to-end workflows such as auth, import/export, backup/restore validation, and report-card generation.
- **Performance** (`-m performance`): large-dataset and cache-sensitive checks for gradebook, dashboard, search, and export paths.

Run categories directly:

- `python -m pytest -q -m "not integration and not performance"`
- `python -m pytest -q -m integration`
- `python -m pytest -q -m performance`

## Coverage requirements

- Backend coverage must stay at or above **80%**.
- CI enforces the coverage floor with `pytest-cov`.
- New backend work should include tests for:
  - router happy paths and validation failures
  - family isolation / RBAC
  - critical business logic
  - regression cases for bugs that were fixed

## Adding new tests

1. Prefer existing fixtures in `backend/tests/conftest.py`.
2. Add or extend endpoint contracts in `backend/tests/contracts.py` when new API routes are introduced.
3. Mark end-to-end flows with `@pytest.mark.integration`.
4. Mark large-dataset or timing-sensitive checks with `@pytest.mark.performance`.
5. Keep tests SQLite-safe and store transient artifacts under `backend/.pytest-state`.

## CI matrix

CI runs backend tests across:

- Python **3.11**
- Python **3.12**
- categories: **unit/API**, **integration**, **performance**

CI also publishes JUnit artifacts, coverage XML, and a pull-request summary comment for test results.
