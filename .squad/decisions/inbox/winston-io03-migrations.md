# Winston IO-03 migration decisions

- Date: 2026-05-08
- Requested by: John

## Proposed team-relevant decisions

1. Keep `MIGRATION_MODE=apply` as the default startup behavior so stale schemas never serve traffic silently, but allow `MIGRATION_MODE=warn` for operator-controlled maintenance windows.
2. Require every Alembic migration file to include non-placeholder `ROLLBACK_NOTES`; CI should fail migrations that omit rollback guidance, filename conventions, or a downgrade path.
3. Keep CI migration verification at the operator workflow level: lint migrations, upgrade from baseline to head, downgrade one revision, then upgrade back to head.
