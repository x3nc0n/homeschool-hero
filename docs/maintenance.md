# Maintenance mode

## Enable or disable maintenance

- Environment override: set `MAINTENANCE_MODE=true` to force maintenance on at startup.
- Admin API:
  - `GET /api/admin/maintenance`
  - `POST /api/admin/maintenance`
  - `PUT /api/admin/maintenance/schedule`
- UI: **Family Settings → Maintenance mode**.

When maintenance is active, non-admin users receive HTTP 503 with the maintenance message and the frontend shows the maintenance page. Parents and co-parents can still sign in and operate the system.

## Scheduled maintenance workflow

1. Open **Family Settings**.
2. Set the maintenance message.
3. Enter start and end times.
4. Save the maintenance window.
5. At the scheduled start time, maintenance becomes active automatically.
6. After the end time, maintenance turns off automatically unless `MAINTENANCE_MODE=true` or manual maintenance is still enabled.

## Pre-maintenance checklist

1. Run a fresh backup.
2. Confirm recent backup artifacts are restorable.
3. Notify users of the planned window and expected impact.
4. Verify TLS/certificate status before exposing the maintenance page publicly.

## Post-maintenance verification

1. Disable manual maintenance if it was enabled.
2. Confirm `/health` and `/api/admin/maintenance` show normal status.
3. Log in as an admin and as a non-admin user.
4. Verify uploads, grading, backups, and notifications still respond normally.
