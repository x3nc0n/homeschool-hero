---
title: Operations & Maintenance
description: Maintenance mode, backups, database management, health checks, upgrades, and day-to-day operations.
---

# Operations & Maintenance

This page covers the operational tasks you'll perform on a running Homeschool Hero instance:
checking health, managing backups, running maintenance windows, managing the database, and
upgrading the application.

---

## Health checks

### Application health endpoint

```bash
curl http://localhost:8000/api/health
```

A healthy, fully bootstrapped system returns:
```json
{"status": "ok", "bootstrap_required": false}
```

During first-run setup, `"bootstrap_required": true` is expected and normal.

### Container health status

```bash
docker compose ps
```

All containers should show `healthy`. The app container depends on `db` being healthy before
starting, so startup order is automatic.

---

## Maintenance mode

Maintenance mode serves HTTP 503 to non-admin users while allowing admins to continue working.
Use it for planned downtime, upgrades, or database operations.

### Enable maintenance

**Via environment variable (startup-forced):**
```env
MAINTENANCE_MODE=true
```
Set in `.env` before starting the stack. Maintenance stays active until the variable is removed
or set to `false` and the container is restarted.

**Via the admin API:**
```bash
# Enable
curl -X POST http://localhost:8000/api/admin/maintenance \
  -H "Content-Type: application/json" \
  -d '{"enabled": true, "message": "System update in progress"}'

# Check status
curl http://localhost:8000/api/admin/maintenance
```

**Via the UI:** Navigate to **Family Settings → Maintenance mode**.

### Schedule a maintenance window

```bash
curl -X PUT http://localhost:8000/api/admin/maintenance/schedule \
  -H "Content-Type: application/json" \
  -d '{
    "start": "2026-06-01T02:00:00Z",
    "end": "2026-06-01T04:00:00Z",
    "message": "Scheduled database maintenance"
  }'
```

The system activates maintenance automatically at the scheduled start time and deactivates it at
the end time, unless `MAINTENANCE_MODE=true` or manual maintenance is still enabled.

### Pre-maintenance checklist

1. Run a fresh backup (see below)
2. Confirm the backup is restorable
3. Notify family members of the planned window and expected impact
4. Verify TLS/certificate status if maintenance page will be publicly visible

### Post-maintenance verification

1. Disable manual maintenance if it was enabled
2. Confirm `/api/health` and `/api/admin/maintenance` show normal status
3. Log in as admin and as a non-admin user to verify both flows work
4. Verify uploads, grading, backups, and notifications still respond normally

---

## Backups

### How backups work

A backup artifact contains:
- A PostgreSQL custom-format dump (`pg_dump --format=custom`)
- A copy of `/data/uploads` (all submission files)
- A full export ZIP bundle
- A `manifest.json` with artifact metadata

### Run a one-off backup

```bash
# Via Docker
docker compose --profile backup run --rm backup python -m backend.cli backups once

# Via shell helper
./scripts/backup.sh

# Without the backup profile (runs in the app container)
docker compose exec app python -m backend.cli backups once
```

### Scheduled backups

Enable the `backup` service profile to run automated backups:

```bash
docker compose --profile backup up -d --build
```

Configure the schedule in `.env`:

```env
BACKUP_SCHEDULE=0 2 * * *          # Nightly at 2am UTC
BACKUP_RETENTION_DAYS=14           # Keep 14 days of backups
BACKUP_RETENTION_COUNT=3           # Keep at least 3 backups regardless of age
```

### Backup destinations

| Destination | `BACKUP_DESTINATION` | Notes |
|-------------|---------------------|-------|
| Local bind mount | `local` | Default; writes to `./data/backups` on the host |
| SMB network share | `smb` | NAS or Windows share; requires `BACKUP_SMB_*` variables |
| NFS mount | `nfs` | Requires `BACKUP_NFS_*` variables |

### Encrypted backups

Set `BACKUP_ENCRYPTION_KEY` to enable restic-based encrypted backups. Requires `restic` to be
installed in the backup container.

### List available backups

```bash
docker compose exec app python -m backend.cli backups list
```

Or via the UI: **Settings → Data Management → Backups**.

### Restore procedure

Restore endpoints are available at `/api/restore`:
- `GET /api/restore` — list available backup artifacts
- `POST /api/restore/validate` — validate a backup with a confirmation token
- `POST /api/restore/full` — full database and uploads restore
- `POST /api/restore/selective` — selective restore (data only or uploads only)

::: danger Data loss risk
A full restore replaces your current database and uploads. Always run a fresh backup immediately
before restoring. `pg_restore` must be available in the container for PostgreSQL restores.
:::

---

## Database management

### Migration behavior

On every startup, Homeschool Hero:
1. Validates runtime configuration
2. Checks the current Alembic revision
3. Applies pending migrations automatically when `MIGRATION_MODE=apply` (the default)
4. Refuses to start if migration execution fails

### Migration commands

```bash
# Via Docker (recommended)
docker compose exec app python -m backend.cli migrations status
docker compose exec app python -m backend.cli migrations upgrade head
docker compose exec app python -m backend.cli migrations downgrade -1
docker compose exec app python -m backend.cli migrations lint
docker compose exec app python -m backend.cli migrations verify
```

```powershell
# Windows helpers
.\scripts\migrate.ps1 status
.\scripts\migrate.ps1 upgrade head
```

### Connect directly to PostgreSQL

```bash
docker compose exec db psql -U homeschool -d homeschool_hero
```

Or with variables from `.env`:
```bash
docker compose exec db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"
```

### Change `MIGRATION_MODE`

Set `MIGRATION_MODE=warn` if you want to inspect migration state at startup without applying
changes. This is useful for debugging or when you want to run migrations manually.

---

## Upgrading

### Standard upgrade (Docker)

```bash
# 1. Pull latest code
git pull

# 2. Run a backup before upgrading
docker compose --profile backup run --rm backup python -m backend.cli backups once

# 3. Rebuild and restart
docker compose up -d --build

# 4. Verify health
curl http://localhost:8000/api/health
docker compose ps
```

Migrations run automatically on startup (`MIGRATION_MODE=apply`). Check `docker compose logs app`
if the app fails to start — migration errors will be clearly reported.

### Rollback procedure

If the new version has issues:

```bash
# Restore the previous Docker image (if using tags)
docker compose down
git checkout v<previous-version>
docker compose up -d --build
```

For database rollback, use a backup taken before the upgrade:
```bash
docker compose exec app python -m backend.cli backups restore <backup-id>
```

---

## Log management

### View logs

```bash
docker compose logs -f app      # Application logs (FastAPI)
docker compose logs -f db       # PostgreSQL logs
docker compose logs -f ollama   # Ollama model loading / inference
docker compose logs backup      # Backup run history
```

### Enable structured JSON logging

Set `LOG_JSON=true` in `.env` for production. JSON logs are easier to ingest into log aggregation
systems (e.g., Loki, CloudWatch, Splunk).

### Log levels

Set `LOG_LEVEL` in `.env`:
- `DEBUG` — verbose, includes request details (development only)
- `INFO` — standard operational events (default)
- `WARNING` — non-fatal issues that need attention
- `ERROR` — failures that may affect functionality

---

## Metrics

Enable the Prometheus metrics endpoint:

```env
ENABLE_METRICS_ENDPOINT=true
```

Then scrape at `GET /api/metrics` (requires admin authentication).

---

## Reset owner access {#reset-owner-access}

If you lose access to the owner account:

1. Connect directly to PostgreSQL:
   ```bash
   docker compose exec db psql -U homeschool -d homeschool_hero
   ```
2. Find the owner user:
   ```sql
   SELECT id, email, display_name FROM users WHERE is_active = true;
   ```
3. To change the password, generate a bcrypt hash and update:
   ```sql
   UPDATE users SET password_hash = '<bcrypt-hash>' WHERE id = <user-id>;
   ```

::: warning
Only do this if you have legitimate administrative access to the server. Direct database
modifications bypass application-level audit trails.
:::
