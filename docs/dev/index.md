---
title: Developer Guide
description: Overview of the Homeschool Hero developer guide — local setup, testing, and contributing.
---

# Developer Guide

This guide covers everything you need to run Homeschool Hero locally, write and run tests, and contribute changes.

## Tech Stack

| Layer | Technology |
|-------|------------|
| Backend | Python 3.12 + FastAPI |
| Frontend | React 18 + Vite + TypeScript |
| UI | shadcn/ui (Tailwind CSS) |
| Database | PostgreSQL 16 (SQLite for tests) |
| ORM | SQLAlchemy 2.0 + Alembic |
| File storage | Local filesystem (`/data/uploads/`) |
| OCR | Tesseract (pytesseract) — optional |
| AI grading | Ollama (local) or OpenAI API — optional |
| Containerization | Docker Compose |

## Quick Links

- [Local Setup](./setup.md) — prerequisites, environment configuration, running the stack
- [Testing](./testing.md) — test categories, commands, coverage requirements
- [Contributing](./contributing.md) — PR process, commit conventions, code style

## Repository Layout

```
homeschool-hero/
├── backend/              # FastAPI application
│   ├── main.py           # App entry point
│   ├── config.py         # Settings (env vars via Pydantic)
│   ├── database.py       # Async SQLAlchemy engine + session
│   ├── models/           # SQLAlchemy ORM models
│   ├── schemas/          # Pydantic request/response schemas
│   ├── routers/          # API route handlers
│   ├── services/         # Reusable business logic
│   ├── migrations/       # Alembic migration scripts
│   └── tests/            # pytest test suite
├── frontend/             # React + Vite SPA
│   └── src/
│       ├── components/   # UI components
│       ├── context/      # React context (auth, etc.)
│       └── pages/        # Route-level page components
├── docs/                 # VitePress documentation site
├── docker-compose.yml
├── Dockerfile
└── .env.example
```

## Key Design Principles

- **Family isolation is mandatory.** Every database query must filter by `family_id`. Never expose data across family boundaries.
- **Thin routers, rich services.** Routers handle HTTP concerns; business logic lives in `backend/services/`.
- **Capability-based access control.** Use `require_capabilities()` or `require_any_role()` from `backend.services.authorization` for protected endpoints — never roll ad-hoc permission checks.
- **Async throughout.** All route handlers and database calls use `async/await`. Use async SQLAlchemy sessions via FastAPI dependency injection.
- **Pydantic response models.** Every router should declare a `response_model` so the OpenAPI schema stays accurate.

## Architecture Reference

See [MVP Architecture](/architecture) and [Architecture Decisions](/architecture-decisions) for design rationale. The [Unified RBAC Model](/architecture/rbac-unified-model) covers the capability system in depth.
