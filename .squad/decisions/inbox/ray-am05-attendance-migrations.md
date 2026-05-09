# Ray Decision Inbox — AM-05 Attendance Migration Graph

- **Date:** 2026-05-10
- **Author:** Ray
- **Context:** Parallel wave work introduced multiple `20260510_001500` migrations from the same `20260510_000100` base, which blocked `alembic upgrade head` while AM-05 attendance needed a new migration.
- **Decision:** Assign unique revision IDs to the parallel `notifications`, `submission_versioning`, and `attendance_tracking` migrations and add a `20260510_001600` merge revision so production/test upgrades converge on one deterministic Alembic head.
- **Impact:** Operators can keep using `python -m alembic -c backend\\alembic.ini upgrade head` without manual branch targeting, and future backend features can continue shipping parallel migrations without breaking upgrade automation.
