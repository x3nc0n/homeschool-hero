# Database migrations

Homeschool Hero uses Alembic for schema changes. Startup now performs migration preflight checks before serving requests:

- verifies database connectivity
- logs the current revision, head revision, pending revisions, and timing
- auto-applies pending migrations when `MIGRATION_MODE=apply` (default)
- warns without applying when `MIGRATION_MODE=warn`
- blocks startup if migration execution fails

## Common commands

Use either the Python CLI or the wrapper scripts:

```bash
python -m backend.cli migrations status
python -m backend.cli migrations upgrade head
python -m backend.cli migrations downgrade -1
python -m backend.cli migrations create -m "add_attendance_table"
python -m backend.cli migrations lint
python -m backend.cli migrations verify
```

```powershell
.\scripts\migrate.ps1 status
.\scripts\migrate.ps1 upgrade head
.\scripts\migrate.ps1 downgrade -1
.\scripts\migrate.ps1 create -m "add_attendance_table"
```

```bash
./scripts/migrate.sh status
./scripts/migrate.sh upgrade head
./scripts/migrate.sh downgrade -1
./scripts/migrate.sh create -m "add_attendance_table"
```

## Rollback discipline

Every migration file must include a `ROLLBACK_NOTES` block that explains:

1. what `downgrade()` restores or removes
2. whether any data is deleted, rewritten, or left unrecoverable
3. backup/export steps operators should take before rollback

CI enforces migration linting so migrations without rollback notes, with placeholder TODO text, with missing downgrade functions, or with invalid filenames fail validation.

## Rollback procedure

1. Inspect status: `python -m backend.cli migrations status`
2. Take a database backup or snapshot before any downgrade.
3. Review the migration file's `ROLLBACK_NOTES`.
4. Downgrade one revision: `python -m backend.cli migrations downgrade -1`
5. Re-run smoke tests and `python -m backend.cli migrations status`
6. If rollback must be reversed, upgrade again: `python -m backend.cli migrations upgrade head`

## Data-conversion guidance

Schema changes that rewrite data need explicit forward and backward plans.

- Prefer reversible transforms that keep the source column until the new shape is verified.
- If a transform is destructive, export the affected rows before upgrade and link that recovery plan in `ROLLBACK_NOTES`.
- For large backfills, log expected duration and consider chunked updates so operators can estimate rollback windows.
- If rollback cannot restore data automatically, say so plainly in `ROLLBACK_NOTES` and in the PR description.
