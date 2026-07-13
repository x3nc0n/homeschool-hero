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

### Decision 5: Simplify Attendance to Homeschool Minimums (2026-07-13)
**Context:** Issue #297. Manual testing (John) found the attendance model over-engineered for homeschooling — it carries public-school concepts (tardy, document-backed excuse workflow, clock check-in/out) that no US state requires of homeschool families. Full state-by-state research is in `docs/research/attendance-requirements.md`.
**Decision:** Adopt an instructional-day-boolean core model. Remove `tardy` and `excused` statuses, `check_in_time`/`check_out_time`, and the entire `AttendanceExcuse` sub-model. Make `instructional_hours` optional, surfaced only for families whose (optional) state profile requires hours (Buckets C/D). Add an optional `StateRequirementProfile` (state → required_days/required_hours) that drives a progress-toward-minimum widget; defaults, never enforcement. `AttendanceSummary` drops tardy/excused counts.
**Rationale:** ~40% of states (Bucket A) have zero attendance requirement; day-count states center on 180 days; only ~13 states require hours and none require clock times, tardy logging, or excuse documents. Defaulting to the universal minimum removes daily friction for the majority while remaining legally sufficient for all 50 states when paired with an optional state profile.
**Migration note:** Breaking schema change — `tardy`→`present`, `excused`→absent/non-instructional, drop check-in/out columns and the excuse table (export first), retain `instructional_hours` as nullable. Warrants a release note + data-export reminder.
**Status:** ACCEPTED — implementation tracked in follow-up issues (see #297).
