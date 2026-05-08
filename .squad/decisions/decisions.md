# Decisions Log

## Project: homeschool-hero

### Decision 1: Multi-stage Docker Build (2026-05-08)
**Context:** MVP needs efficient containerization for local and production deployment.
**Decision:** Implemented multi-stage Dockerfile with separate build (dependencies) and runtime (minimal image) stages.
**Rationale:** Reduces image size, improves build caching, faster deployments.
**Status:** IMPLEMENTED (Task 25)

### Decision 2: Frontend SPA Bundling (2026-05-08)
**Context:** Need single-port deployment for simplified parent experience and easier infrastructure.
**Decision:** Bundle React frontend build artifacts into FastAPI backend container, serve as static files.
**Rationale:** Simplifies deployment (one container), reduces complexity for non-technical parents, eliminates nginx orchestration overhead.
**Status:** IMPLEMENTED (Task 25)

### Decision 3: Alembic Auto-Migration (2026-05-08)
**Context:** Schema management must be seamless during container startup.
**Decision:** FastAPI app auto-runs Alembic migrations on startup via database.py initialization.
**Rationale:** Eliminates manual migration steps, ensures database is always in sync with code, improves MVP deployment reliability.
**Status:** IMPLEMENTED (Task 25)

### Decision 4: Health Endpoint Integration (2026-05-08)
**Context:** Docker Compose needs way to verify application readiness.
**Decision:** Added /health GET endpoint returning 200 OK with app status.
**Rationale:** Enables Docker Compose health checks, improves container orchestration reliability.
**Status:** IMPLEMENTED (Task 25)
