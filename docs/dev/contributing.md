---
title: Contributing
description: How to contribute to Homeschool Hero — PR process, commit conventions, branching, and code style.
---

# Contributing

Thank you for contributing to Homeschool Hero! This page covers the pull request process, commit conventions, and code style expectations.

## Branching

Work on a feature branch off `main`:

```powershell
git checkout main
git pull
git checkout -b feat/my-feature
```

Branch naming conventions:

| Prefix | Use for |
|--------|---------|
| `feat/` | New features |
| `fix/` | Bug fixes |
| `docs/` | Documentation changes |
| `refactor/` | Code refactoring without behavior change |
| `chore/` | Build, tooling, dependency updates |
| `test/` | Adding or improving tests |

## Commit Conventions

Use **conventional commits**:

```
<type>(<scope>): <short summary>

[optional body]

[optional footer]
```

Types: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`, `perf`

Scope is optional but helpful — use the affected module (e.g., `students`, `auth`, `gradebook`).

Examples:

```
feat(students): add student deletion endpoint

fix(auth): reset failed login count on successful login

docs(api): add endpoints reference page

test(grades): add family isolation test for grade history
```

Keep the subject line under 72 characters and in the imperative mood ("add", "fix", "update" — not "added" or "adds").

## Pull Request Process

1. **Open the PR against `main`** with a clear title and description.
2. **Fill in the PR template** — describe what changed, why, and how to test it.
3. **Ensure CI passes** — all backend tests (Python 3.11 and 3.12), coverage ≥ 80%, frontend build.
4. **Request a review** from a maintainer.
5. **Address review feedback** with additional commits or fixups.
6. A maintainer squash-merges the PR once approved.

### Checklist before opening a PR

- [ ] Backend tests pass: `cd backend && python -m pytest -q`
- [ ] Coverage is at or above 80%: `python -m pytest -q --cov=backend --cov-fail-under=80`
- [ ] Frontend build passes: `cd frontend && npm run build`
- [ ] New endpoints have tests covering happy path, validation errors, and RBAC
- [ ] Any new migration includes `ROLLBACK_NOTES` and a real `downgrade()`
- [ ] Documentation updated if the change affects user-visible behavior or the API surface

## Code Style

### Python

- **Python 3.12** with type annotations throughout.
- **async/await** for all route handlers and database operations.
- **Pydantic v2** models for request/response schemas.
- Use `from __future__ import annotations` at the top of every module.
- Format with **Black** (line length 120). Import order with **isort** (Black-compatible profile).
- Prefer explicit type hints over `Any`. Avoid `# type: ignore` except where unavoidable.
- Keep routers thin — move business logic to `backend/services/`.

### FastAPI conventions

- Declare `response_model` on every route decorator.
- Use `Depends(get_db)` for database sessions and `Depends(get_auth_session)` for authentication.
- Protect endpoints with `require_capabilities()` or `require_any_role()` from `backend.services.authorization`.
- Raise `HTTPException` for all error conditions. Never return raw error strings.
- Always filter queries by `family_id`. Multi-family isolation is non-negotiable.

### TypeScript / React

- **TypeScript strict mode** — no implicit `any`.
- React functional components with hooks — no class components.
- Use the `AuthContext` from `frontend/src/context/AuthContext.tsx` to check capabilities and roles in the UI.
- Keep API calls in service modules (`src/api/`) rather than inline in components.
- Follow the shadcn/ui component patterns already established in the codebase.

### General

- Comment code that needs clarification; do not comment self-evident logic.
- Delete dead code rather than commenting it out.
- Prefer small, focused commits over large omnibus changes.

## Migrations

Any change that adds, removes, or alters database columns must include an Alembic migration. See [Migrations](/migrations) for the full policy, including the `ROLLBACK_NOTES` requirement and the destructive-change review process.

Quick reference:

```powershell
cd backend
python -m backend.cli migrations create -m "describe_change"
python -m backend.cli migrations lint
python -m backend.cli migrations upgrade head
python -m backend.cli migrations downgrade -1   # verify downgrade works
python -m backend.cli migrations upgrade head   # re-apply
```

## Reporting Issues

Open a GitHub issue with:

- A clear title and description of the problem.
- Steps to reproduce.
- Expected vs. actual behavior.
- Relevant log output or screenshots.

For security vulnerabilities, please do not open a public issue — follow the security disclosure process described in `SECURITY.md`.

## Project Repository

[https://github.com/x3nc0n/homeschool-hero](https://github.com/x3nc0n/homeschool-hero)
