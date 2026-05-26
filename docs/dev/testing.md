---
title: Testing
description: How to run the Homeschool Hero test suite, test categories, coverage requirements, and how to write new tests.
---

# Testing

## Backend Test Suite

The backend uses **pytest** with SQLite as the test database. No running PostgreSQL instance is required.

### Quick run

```powershell
cd backend
python -m pytest -q
```

### With coverage report

```powershell
python -m pytest -q \
  --cov=backend \
  --cov-report=term-missing \
  --cov-report=xml:coverage.xml \
  --cov-fail-under=80
```

Coverage must stay at or above **80%**. CI enforces this floor.

### Transient state

The test harness stores ephemeral artifacts under `backend/.pytest-state`. This directory is created automatically and is safe to delete between runs.

## Test Categories

Tests are organized into three categories using pytest markers:

### Unit / API (default)

All tests not marked `integration` or `performance`. Covers:

- Router happy paths and error responses
- Schema validation
- Service and business logic
- RBAC and capability enforcement
- Auth flows (local, OIDC, SAML, JWT)

Run only unit/API tests:

```powershell
python -m pytest -q -m "not integration and not performance"
```

### Integration (`-m integration`)

Multi-step end-to-end workflows that span multiple services:

- Full auth flows (register → login → logout)
- Import and export pipelines
- Backup and restore validation
- Report card and transcript generation

Run integration tests:

```powershell
python -m pytest -q -m integration
```

### Performance (`-m performance`)

Large-dataset and cache-sensitive checks:

- Gradebook with many students and grades
- Dashboard aggregations
- Search across large datasets
- Export job throughput

Run performance tests:

```powershell
python -m pytest -q -m performance
```

## Test Structure

```
backend/tests/
├── conftest.py        # Shared fixtures (db session, auth clients, families, students)
├── contracts.py       # API endpoint contract definitions (routes + expected schemas)
├── helpers.py         # Test utility functions
├── test_auth.py       # Local authentication flows
├── test_students.py   # Student CRUD and RBAC
├── test_assignments.py
├── test_grades.py
├── test_gradebook.py
├── test_calendar.py
├── test_curriculum.py
├── test_authorization.py  # Capability and role enforcement
├── test_rbac_unified.py   # Unified RBAC across auth providers
├── test_integration.py    # Multi-step integration flows
├── test_performance.py    # Large-dataset performance checks
└── ...                # One file per router/service
```

## Writing New Tests

### Use existing fixtures

`conftest.py` provides:

- `db` — async SQLAlchemy session backed by in-memory SQLite
- `client` — async HTTP test client with a fresh family
- `parent_client`, `teacher_client`, `student_client` — pre-authenticated clients per role
- `student`, `subject`, `assignment` — convenience model factories

Use these fixtures rather than rolling your own setup.

### Add endpoint contracts

When introducing a new route, add its contract to `backend/tests/contracts.py`:

```python
EndpointContract(
    method="GET",
    path="/api/widgets",
    expected_status=200,
    auth_required=True,
)
```

The contract tests in `test_api_docs.py` verify that every registered route has a documented contract and that the OpenAPI schema stays consistent.

### Mark test categories

```python
import pytest

@pytest.mark.integration
async def test_full_grading_workflow(client):
    ...

@pytest.mark.performance
async def test_gradebook_large_family(client):
    ...
```

Tests without a marker run in the default unit/API category.

### Coverage requirements

New backend work should include tests for:

- **Router happy paths** — successful request, expected response shape
- **Validation failures** — malformed payloads return `422`
- **RBAC enforcement** — unauthorized roles receive `403`
- **Family isolation** — resources from another family are not visible
- **Regression cases** — any bug fix should include a test that would have caught it

## Frontend Build Verification

The frontend does not have a dedicated test runner beyond the production build check:

```powershell
cd frontend
npm run build
```

A successful build confirms there are no TypeScript compilation errors and that the Vite bundle is valid.

Optional lint check:

```powershell
npm run lint
```

## CI Matrix

CI runs the full backend suite on every pull request:

| Python version | Categories |
|---------------|------------|
| 3.11 | unit/API, integration, performance |
| 3.12 | unit/API, integration, performance |

CI artifacts:

- JUnit XML test results
- Coverage XML report
- Pull request summary comment with pass/fail counts and coverage delta
