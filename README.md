# Homeschool Hero

[![CI](https://github.com/x3nc0n/homeschool-hero/actions/workflows/ci.yml/badge.svg)](https://github.com/x3nc0n/homeschool-hero/actions/workflows/ci.yml)
[![Security](https://github.com/x3nc0n/homeschool-hero/actions/workflows/security.yml/badge.svg?branch=main)](https://github.com/x3nc0n/homeschool-hero/actions/workflows/security.yml)
[![Container Image](https://img.shields.io/badge/container-ghcr.io%2Fx3nc0n%2Fhomeschool--hero-2496ED?logo=docker&logoColor=white)](https://github.com/x3nc0n/homeschool-hero/pkgs/container/homeschool-hero)

Homeschool Hero is a self-hosted homeschool platform for roster management, curriculum planning, assignments, attendance, grading, compliance, reporting, and family administration.

## Current feature set

- Multi-family tenancy with owner, parent, co-parent, tutor, and student-scoped memberships
- Local auth plus optional OIDC and SAML overlays
- Students, subjects, curriculum packages, calendars, schedules, and lesson planning
- Assignments, quizzes, submissions, OCR-assisted grading, review queues, and gradebook analytics
- Attendance tracking, compliance monitoring, report cards, transcripts, exports, notifications, and audit logs
- Docker-first deployment with optional AI, email, and backup profiles

## Quickstart

```bash
git clone https://github.com/x3nc0n/homeschool-hero.git
cd homeschool-hero
docker compose --profile ai up --build
# Open http://localhost:8000
```

> **Tip:** Demo mode (`DEMO_MODE=true` in `.env.example`) seeds sample data on first
> startup. Log in with **`demo@example.com`** / **`demo1234`**.
> Start the demo with the `ai` profile so Ollama comes up alongside the app.
> AI grading and review features will show as degraded until Ollama finishes its
> first model download.
> If you see stale data from a previous run, tear down the Docker volumes first:
>
> ```bash
> docker compose down -v
> docker compose --profile ai up --build
> ```

The default demo stack starts:

- `app` — FastAPI API + bundled React UI on port `8000`
- `db` — PostgreSQL 16 with persistent storage
- `ollama` — local AI service for grading and review

## API documentation

- OpenAPI schema: `http://localhost:8000/api/openapi.json`
- Swagger UI: `http://localhost:8000/api/docs`
- ReDoc: `http://localhost:8000/api/redoc`
- Integration guide: `docs/api-integration.md`
- Admin guide: `docs/admin-guide.md`
- Auth provider setup: `docs/auth-providers.md`
- Developer setup: `docs/development.md`

Swagger UI automatically uses the current session cookie and forwards the CSRF cookie as `X-CSRF-Token` for same-origin mutating requests.

## Compose profiles

```bash
# AI grading with local Ollama
docker compose --profile ai up --build

# Local SMTP relay (Mailpit)
docker compose --profile email up --build

# Scheduled backups
docker compose --profile backup up --build

# Everything
docker compose --profile full up --build
```

Profile mapping:

- Base stack: `app`, `db`
- `ai`: adds `ollama`
- `email`: adds `smtp`
- `backup`: adds `backup`
- `full`: enables all optional services

## Docker deployment

### Pull from GHCR

Pre-built images are published to GitHub Container Registry on every release:

```bash
docker pull ghcr.io/x3nc0n/homeschool-hero:latest

# Or pin to a specific version
docker pull ghcr.io/x3nc0n/homeschool-hero:v0.8.2
```

To run standalone with an external database:

```bash
docker run -d --name homeschool-hero \
  -p 8000:8000 \
  -e DATABASE_URL="postgresql+asyncpg://user:pass@db-host:5432/homeschool" \
  -e SECRET_KEY="your-secret-key" \
  ghcr.io/x3nc0n/homeschool-hero:latest
```

### Build locally

Recommended production steps:

1. Copy `.env.example` to `.env`
2. Replace `SECRET_KEY`, database credentials, and bootstrap defaults
3. Set `SESSION_COOKIE_SECURE=true` behind HTTPS
4. Set `INVITATION_BASE_URL` to your external URL
5. Configure SMTP if you want invitation or alert emails
6. Enable `ai` only on hosts that can run Ollama comfortably
7. Point `BACKUP_MOUNT_SOURCE` at a writable local directory or mounted NAS share, then enable `backup` for scheduled NAS backups

Examples:

```bash
# Demo stack with Ollama
docker compose --profile ai up -d --build

# Base stack without AI
docker compose up -d --build

# Full stack
docker compose --profile full up -d --build

# Review health
docker compose ps
docker compose logs -f app
curl http://localhost:8000/health
```

Useful helpers:

```bash
./scripts/start.sh
./scripts/start.sh --profile full
./scripts/backup.sh
```

```powershell
.\scripts\start.ps1
.\scripts\start.ps1 --profile email
```

## Local development

### Backend

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
cd backend
python -m pytest -q
uvicorn backend.main:app --reload
```

### Frontend

```powershell
cd frontend
npm ci
npm run build
```

See `docs/development.md` for the full development workflow.

## Authentication and tenancy

- First run exposes a one-time owner bootstrap flow
- All family data is filtered by `family_id`
- Local email/password auth is the default
- Set `AUTH_PROVIDER=oidc` or `AUTH_PROVIDER=saml` to enable external sign-in
- Incoming external users are matched by email and can be auto-provisioned into `AUTH_DEFAULT_FAMILY_NAME`

## Configuration reference

| Variable | Required | Description |
| --- | --- | --- |
| `APP_PORT` | No | Host port published for the web app. |
| `POSTGRES_USER` | Yes | PostgreSQL username for the `db` container. |
| `POSTGRES_PASSWORD` | Yes | PostgreSQL password for the `db` container. |
| `POSTGRES_DB` | Yes | PostgreSQL database name. |
| `DATABASE_URL` | Yes | Async SQLAlchemy connection string for FastAPI and Alembic. |
| `SECRET_KEY` | Yes | Signing key for session cookies. |
| `SESSION_COOKIE_NAME` | No | Session cookie name. |
| `CSRF_COOKIE_NAME` | No | CSRF cookie name. |
| `SESSION_MAX_AGE_SECONDS` | No | Session lifetime in seconds. |
| `SESSION_COOKIE_SECURE` | No | Set to `true` behind HTTPS. |
| `SESSION_ROTATION_SECONDS` | No | Interval after which active sessions are rotated. |
| `PASSWORD_MIN_LENGTH` | No | Minimum password length for local users. |
| `AUTH_LOCKOUT_THRESHOLD` | No | Failed login attempts before temporary lockout. |
| `AUTH_LOCKOUT_MINUTES` | No | Temporary lockout duration in minutes. |
| `AUTH_PROVIDER` | No | `local`, `oidc`, or `saml`. |
| `AUTH_AUTO_PROVISION_MODE` | No | `default_family` or `reject` for external identities. |
| `AUTH_DEFAULT_FAMILY_NAME` | No | Family name used when auto-provisioning SSO users. |
| `OIDC_CLIENT_ID` | No | OIDC client/application ID. |
| `OIDC_CLIENT_SECRET` | No | OIDC client secret. |
| `OIDC_DISCOVERY_URL` | No | OIDC discovery URL. |
| `SAML_METADATA_URL` | No | SAML IdP metadata URL. |
| `SAML_ENTITY_ID` | No | Service provider entity ID. |
| `SAML_ACS_URL` | No | SAML assertion consumer service URL. |
| `BOOTSTRAP_OWNER_EMAIL` | No | Initial owner email and legacy migration owner email. |
| `BOOTSTRAP_OWNER_DISPLAY_NAME` | No | Initial owner display name. |
| `BOOTSTRAP_FAMILY_NAME` | No | Initial family name. |
| `BOOTSTRAP_TIMEZONE` | No | Initial family timezone. |
| `BOOTSTRAP_GRADING_SCALE` | No | Initial family grading scale. |
| `FAMILY_PASSWORD` | Yes* | Legacy password source for single-family upgrades. |
| `FAMILY_PASSWORD_HASH` | No | Legacy bcrypt hash source for upgrades. |
| `INVITATION_BASE_URL` | No | External base URL for invitation links. |
| `AI_PROVIDER` | No | `ollama` or `openai`. |
| `OLLAMA_HOST` | No | Ollama base URL. |
| `OLLAMA_MODEL` | No | Ollama model name. |
| `OPENAI_API_KEY` | No | Required when `AI_PROVIDER=openai`. |
| `GRADING_REQUEST_TIMEOUT_SECONDS` | No | Timeout for AI grading requests. |
| `OCR_REQUEST_TIMEOUT_SECONDS` | No | Timeout for OCR requests. |
| `GRADING_RETRY_ATTEMPTS` | No | AI retry attempts before fallback. |
| `GRADING_RETRY_BACKOFF_SECONDS` | No | Backoff between AI retry attempts. |
| `AI_CIRCUIT_BREAKER_THRESHOLD` | No | Consecutive AI failures before circuit opens. |
| `AI_CIRCUIT_BREAKER_RESET_SECONDS` | No | Seconds before AI circuit breaker resets. |
| `CONFIDENCE_THRESHOLD` | No | Auto-approval threshold between `0` and `1`. |
| `GRADING_POLL_INTERVAL` | No | Background grading worker poll interval. |
| `UPLOAD_DIR` | No | Upload storage path inside the app container. |
| `UPLOAD_MAX_BYTES` | No | Maximum upload size in bytes. |
| `UPLOAD_ALLOWED_MIME_TYPES` | No | Comma-separated allowed upload MIME types. |
| `ENABLE_METRICS_ENDPOINT` | No | Enables authenticated `/api/metrics`. |
| `LOG_LEVEL` | No | Root backend log level. |
| `LOG_JSON` | No | Force JSON logging on or off. |
| `MIGRATION_MODE` | No | `apply` or `warn` during startup migration preflight. |
| `SMTP_HOST` | No | SMTP relay host. |
| `SMTP_PORT` | No | SMTP relay port. |
| `SMTP_USERNAME` | No | SMTP username. |
| `SMTP_PASSWORD` | No | SMTP password. |
| `SMTP_FROM_EMAIL` | No | Sender address for notification email. |
| `SMTP_USE_TLS` | No | Enable STARTTLS for SMTP. |
| `EMAIL_PROVIDER` | No | `smtp` (default), `acs`, or `none`. |
| `ACS_CONNECTION_STRING` | No | Azure Communication Services connection string when `EMAIL_PROVIDER=acs`. |
| `ACS_SENDER_ADDRESS` | No | Azure Communication Services sender address when `EMAIL_PROVIDER=acs`. |
| `SMTP_DEV_PORT` | No | Host port for Mailpit SMTP. |
| `SMTP_WEB_PORT` | No | Host port for Mailpit web UI. |
| `BACKUP_TARGET` | No | Backup path inside the container. Use `/data/backups` when the host bind mount points at a NAS or local archive path. |
| `BACKUP_DESTINATION` | No | `local`, `smb`, or `nfs`; used for validation and operator-facing status. |
| `BACKUP_SCHEDULE` | No | Five-field cron expression for scheduled backups (`0 2 * * *` by default). |
| `BACKUP_RETENTION_DAYS` | No | Retention period for backups. |
| `BACKUP_FILENAME_PREFIX` | No | Prefix for generated backup archives. |
| `BACKUP_SCHEDULER_ENABLED` | No | Enables cron-based backup scheduling in the current process. |
| `BACKUP_MOUNT_SOURCE` | No | Host path bind-mounted to `/data/backups`. Point this at a mounted SMB/NFS share for NAS backups. |
| `BACKUP_SMB_HOST` | No | SMB host recorded for NAS configuration and startup validation. |
| `BACKUP_SMB_SHARE` | No | SMB share name recorded for NAS configuration and startup validation. |
| `BACKUP_SMB_USER` | No | SMB username recorded for the mounted NAS share. |
| `BACKUP_SMB_PASSWORD` | No | SMB password recorded for the mounted NAS share. |
| `BACKUP_NFS_HOST` | No | NFS host recorded for NAS configuration and startup validation. |
| `BACKUP_NFS_PATH` | No | NFS export path recorded for NAS configuration and startup validation. |
| `BACKUP_ENCRYPTION_KEY` | No | Restic repository password. When `restic` is available, backups switch to encrypted incremental snapshots automatically. |
| `APP_MEMORY_LIMIT` | No | Memory limit for `app`. |
| `DB_MEMORY_LIMIT` | No | Memory limit for `db`. |
| `OLLAMA_MEMORY_LIMIT` | No | Memory limit for `ollama`. |
| `SMTP_MEMORY_LIMIT` | No | Memory limit for `smtp`. |
| `BACKUP_MEMORY_LIMIT` | No | Memory limit for `backup`. |

\* Keep `FAMILY_PASSWORD` or `FAMILY_PASSWORD_HASH` populated when upgrading an existing installation from the legacy single-family auth model.

## Operational notes

- Startup waits for PostgreSQL, validates migration state, and applies migrations when `MIGRATION_MODE=apply`
- `/health` stays green for optional service outages and reports degraded capabilities instead
- `/api/metrics` is available only when `ENABLE_METRICS_ENDPOINT=true`
- Scheduled backups include database dumps, uploads, and DM-02 full export bundles; use the UI at `/settings/backups` for trigger/history/status visibility
- Pull requests are expected to pass backend tests, frontend build/lint, migration checks, container checks, and secret scanning

Additional references:

- `docs/architecture.md`
- `docs/migrations.md`
- `docs/security-scanning.md`
