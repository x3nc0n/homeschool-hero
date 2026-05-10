# Administrator Setup & Configuration Guide

This guide is for full administrators deploying, configuring, and maintaining **Homeschool Hero**.

Homeschool Hero is a self-hosted stack built around:

- **FastAPI** backend (`backend/`)
- **React 18 + Vite** frontend (`frontend/`)
- **PostgreSQL 16** for production data
- Optional **Ollama/OpenAI** grading, **SMTP**, and **scheduled backups**

In Docker deployments, the React app is built into the image and served by the FastAPI container at `/`.

---

## 1. System Requirements

### Recommended host sizing

Base stack (`app` + `db`):

- **CPU:** 2 vCPU minimum, 4 vCPU recommended
- **RAM:** 4 GB minimum, 8 GB recommended
- **Disk:** 20 GB minimum before uploads/backups

AI stack (`--profile ai` or `--profile full`):

- Add **at least 6 GB RAM** for the `ollama` container
- **12-16 GB total RAM** is the practical target for local Ollama use

These recommendations are based on the compose memory limits:

- `APP_MEMORY_LIMIT=1536m`
- `DB_MEMORY_LIMIT=1024m`
- `OLLAMA_MEMORY_LIMIT=6g`
- `SMTP_MEMORY_LIMIT=256m`
- `BACKUP_MEMORY_LIMIT=256m`

### Software prerequisites

For Docker deployment:

- Docker Engine / Docker Desktop with **Compose v2**
- Git

For non-Docker local installs:

- **Python 3.12**
- **Node.js 22** for frontend parity with the Docker build stage
- **PostgreSQL 16**
- **Tesseract OCR**
- `pg_dump` / `pg_restore` (from PostgreSQL client tools)

Optional:

- **Ollama** for local AI grading
- SMTP relay or Mailpit-compatible SMTP server
- Reverse proxy / TLS terminator (or the provided `docker-compose.tls.yml`)

---

## 2. Quick Start

Fastest safe local start:

```bash
git clone https://github.com/x3nc0n/homeschool-hero.git
cd homeschool-hero
cp .env.example .env
docker compose up --build
```

Windows helper:

```powershell
git clone https://github.com/x3nc0n/homeschool-hero.git
cd homeschool-hero
.\scripts\start.ps1
```

Then:

1. Open `http://localhost:8000`
2. Complete the one-time owner bootstrap flow
3. Confirm health at `http://localhost:8000/api/health`
4. Open API docs at `http://localhost:8000/api/docs`

Quick profile variants:

```bash
# Base stack
docker compose up -d --build

# AI grading with Ollama
docker compose --profile ai up -d --build

# Local SMTP relay (Mailpit)
docker compose --profile email up -d --build

# Scheduled backups
docker compose --profile backup up -d --build

# All optional services
docker compose --profile full up -d --build
```

---

## 3. Installation

### A. Docker installation (recommended)

#### Step 1: Clone the repository

```bash
git clone https://github.com/x3nc0n/homeschool-hero.git
cd homeschool-hero
```

#### Step 2: Create and edit `.env`

```bash
cp .env.example .env
```

Generate a strong secret:

```bash
python - <<'PY'
import secrets
print(secrets.token_urlsafe(48))
PY
```

PowerShell:

```powershell
[Convert]::ToBase64String([System.Security.Cryptography.RandomNumberGenerator]::GetBytes(48))
```

At minimum, change:

- `SECRET_KEY`
- `POSTGRES_PASSWORD`
- `DATABASE_URL`
- bootstrap defaults (`BOOTSTRAP_*`)
- `INVITATION_BASE_URL`
- `SESSION_COOKIE_SECURE=true` when behind HTTPS

#### Step 3: Start the stack

```bash
docker compose up -d --build
```

#### Step 4: Verify startup

```bash
docker compose ps
docker compose logs -f app
curl http://localhost:8000/api/health
```

Expected base services:

- `app`
- `db`

#### Step 5: Complete first-run bootstrap

Check bootstrap status:

```bash
curl http://localhost:8000/api/auth/bootstrap
```

When `bootstrap_required` is `true`, create the owner account from the web UI at `/`. After the first owner is created, `/api/auth/register` is intentionally disabled for future open registration.

### B. Non-Docker installation

#### Backend

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Point `DATABASE_URL` at PostgreSQL 16, then run:

```powershell
python -m backend.cli migrations upgrade head
uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

#### Frontend

```powershell
cd frontend
npm ci
npm run build
cd ..
```

The backend serves the built frontend from `frontend/dist`, so build the frontend before running `uvicorn` in a non-Docker deployment.

---

## 4. Configuration Reference

Homeschool Hero reads settings from environment variables through `backend/config.py`. Docker Compose loads `.env.example` first, then `.env` as an optional override.

### Core application and database

| Variable | Default | Notes |
| --- | --- | --- |
| `APP_PORT` | `8000` | Host port published by the `app` container. |
| `POSTGRES_USER` | `homeschool` | PostgreSQL user for the `db` service. |
| `POSTGRES_PASSWORD` | `changeme` | PostgreSQL password; change in all real deployments. |
| `POSTGRES_DB` | `homeschool_hero` | PostgreSQL database name. |
| `DATABASE_URL` | `postgresql+asyncpg://homeschool:changeme@db:5432/homeschool_hero` | Async SQLAlchemy URL used by FastAPI and Alembic. |
| `SECRET_KEY` | `change-me-in-production` in `.env.example` | Signing key for session cookies and other signed state. Use a long random value. |
| `UPLOAD_DIR` | `/data/uploads` | Upload root inside the container. |
| `UPLOAD_MAX_BYTES` | `26214400` | 25 MiB max upload size. |
| `UPLOAD_ALLOWED_MIME_TYPES` | `application/pdf,image/jpeg,image/png,image/heic,image/heif,image/tiff,image/webp` | Allowed upload MIME types. |
| `MIGRATION_MODE` | `apply` | `apply` auto-runs pending migrations; `warn` logs only. |
| `LOG_LEVEL` | `INFO` | Backend log level. |
| `LOG_JSON` | unset | When enabled, favors structured JSON logs outside tests. |

### Session, transport, and maintenance

| Variable | Default | Notes |
| --- | --- | --- |
| `SESSION_COOKIE_NAME` | `homeschool_session` | HttpOnly signed session cookie name. |
| `CSRF_COOKIE_NAME` | `homeschool_csrf` | Readable CSRF cookie name. |
| `SESSION_MAX_AGE_SECONDS` | `28800` | 8-hour session lifetime. |
| `SESSION_ROTATION_SECONDS` | `1800` | Active-session rotation interval. |
| `SESSION_COOKIE_SECURE` | `false` | Set to `true` behind HTTPS. |
| `TLS_ENABLED` | `false` | Enables backend HTTPS-aware behavior. |
| `HTTPS_REDIRECT_ENABLED` | `false` | Redirects HTTP to HTTPS except health paths. |
| `HSTS_ENABLED` | `true` | Sends HSTS on secure requests. |
| `HSTS_MAX_AGE_SECONDS` | `31536000` | HSTS max-age. |
| `HSTS_INCLUDE_SUBDOMAINS` | `true` | Adds `includeSubDomains`. |
| `HSTS_PRELOAD` | `false` | Adds `preload` when appropriate. |
| `MAINTENANCE_MODE` | `false` | Forces maintenance mode on at startup. |
| `MAINTENANCE_MESSAGE` | built-in message | Message returned during maintenance. |

### Authentication, bootstrap, and invitations

| Variable | Default | Notes |
| --- | --- | --- |
| `PASSWORD_MIN_LENGTH` | `12` | Minimum local password length. |
| `AUTH_LOCKOUT_THRESHOLD` | `5` | Failed logins before temporary lockout. |
| `AUTH_LOCKOUT_MINUTES` | `15` | Lockout duration. |
| `AUTH_PROVIDER` | `local` | `local`, `oidc`, or `saml`. |
| `AUTH_AUTO_PROVISION_MODE` | `default_family` | `default_family` or `reject` for external identities. |
| `AUTH_DEFAULT_FAMILY_NAME` | `SSO Users` | Family for auto-provisioned SSO users. |
| `OIDC_CLIENT_ID` | unset | Required for OIDC. |
| `OIDC_CLIENT_SECRET` | unset | Required for OIDC. |
| `OIDC_DISCOVERY_URL` | unset | Required for OIDC; example: Entra discovery URL. |
| `SAML_METADATA_URL` | unset | Required for SAML. |
| `SAML_ENTITY_ID` | unset | Required for SAML. |
| `SAML_ACS_URL` | unset | Required for SAML. |
| `BOOTSTRAP_OWNER_EMAIL` | `owner@homeschool-hero.local` | Default owner email for first-run defaults and legacy upgrades. |
| `BOOTSTRAP_OWNER_DISPLAY_NAME` | `Family Owner` | First-run display name default. |
| `BOOTSTRAP_FAMILY_NAME` | `My Family` | First-run family name default. |
| `BOOTSTRAP_TIMEZONE` | `UTC` | First-run family timezone default. |
| `BOOTSTRAP_GRADING_SCALE` | `letter` | First-run grading scale default. |
| `FAMILY_PASSWORD` | `changeme` | Legacy single-family upgrade support; keep populated during old-to-new upgrades. |
| `FAMILY_PASSWORD_HASH` | unset | Optional legacy bcrypt hash instead of plaintext family password. |
| `INVITATION_BASE_URL` | `http://localhost:8000` | Base URL used in invitation links. |
| `INVITATION_EXPIRY_DAYS` | `7` | Supported by the backend even though not pre-seeded in `.env.example`. |

### AI grading and OCR

| Variable | Default | Notes |
| --- | --- | --- |
| `AI_PROVIDER` | `ollama` | `ollama` or `openai`. |
| `OLLAMA_HOST` | `http://ollama:11434` | Ollama API base URL. |
| `OLLAMA_MODEL` | `llama3.2` | Model name; Compose preloads this model. |
| `OPENAI_API_KEY` | unset | Required when `AI_PROVIDER=openai`. |
| `CONFIDENCE_THRESHOLD` | `0.8` | Auto-approve threshold. Lower-confidence jobs go to review. |
| `GRADING_POLL_INTERVAL` | `5` | Background worker poll interval, in seconds. |
| `GRADING_REQUEST_TIMEOUT_SECONDS` | `120` | Timeout for AI grading requests. |
| `OCR_REQUEST_TIMEOUT_SECONDS` | `120` | Timeout for OCR. |
| `GRADING_RETRY_ATTEMPTS` | `3` | Retries for OCR/AI calls. |
| `GRADING_RETRY_BACKOFF_SECONDS` | `1` | Exponential backoff base delay. |
| `AI_CIRCUIT_BREAKER_THRESHOLD` | `3` | Consecutive AI failures before the circuit opens. |
| `AI_CIRCUIT_BREAKER_RESET_SECONDS` | `300` | Circuit breaker reset window. |

### Email, metrics, and observability

| Variable | Default | Notes |
| --- | --- | --- |
| `SMTP_HOST` | `smtp` in `.env.example` | SMTP relay host. |
| `SMTP_PORT` | `1025` in `.env.example`, backend default `587` | Use a real relay port in production. |
| `SMTP_USERNAME` | unset | Optional SMTP username. |
| `SMTP_PASSWORD` | unset | Required when `SMTP_USERNAME` is set. |
| `SMTP_FROM_EMAIL` | `notifications@homeschool-hero.local` | Sender address. |
| `SMTP_USE_TLS` | `false` in `.env.example` | Enables STARTTLS. |
| `SMTP_DEV_PORT` | `1025` | Host SMTP port for Mailpit. |
| `SMTP_WEB_PORT` | `8025` | Host web UI port for Mailpit. |
| `ENABLE_METRICS_ENDPOINT` | `false` | Enables authenticated `GET /api/metrics`. |

### Backups and restore

| Variable | Default | Notes |
| --- | --- | --- |
| `BACKUP_TARGET` | `/data/backups` | Path inside the container where backup artifacts are written. |
| `BACKUP_DESTINATION` | `local` | `local`, `smb`, or `nfs`. |
| `BACKUP_SCHEDULE` | `0 2 * * *` | Cron expression in UTC. |
| `BACKUP_RETENTION_DAYS` | `14` | Delete old backup directories beyond this age, subject to retention count. |
| `BACKUP_RETENTION_COUNT` | `3` | Runtime-supported minimum number of backups to keep, even if older than retention days. |
| `BACKUP_FILENAME_PREFIX` | `homeschool-hero` | Prefix for plain-copy backup directories. |
| `BACKUP_SCHEDULER_ENABLED` | `true` | Backend scheduler toggle. |
| `BACKUP_MOUNT_SOURCE` | `./data/backups` when Compose expands the default | Host path bind-mounted to `/data/backups`. |
| `BACKUP_SMB_HOST` | unset | Metadata/validation for SMB-mounted targets. |
| `BACKUP_SMB_SHARE` | unset | SMB share name. |
| `BACKUP_SMB_USER` | unset | SMB username. |
| `BACKUP_SMB_PASSWORD` | unset | SMB password. |
| `BACKUP_NFS_HOST` | unset | NFS host. |
| `BACKUP_NFS_PATH` | unset | NFS export path. |
| `BACKUP_ENCRYPTION_KEY` | unset | Enables restic mode only when `restic` is installed. |
| `APP_BACKUP_SCHEDULER_ENABLED` | `false` in Compose | Compose-only override to keep the main `app` container from also scheduling backups when a dedicated `backup` service is used. |

### Container resource limits

| Variable | Default |
| --- | --- |
| `APP_MEMORY_LIMIT` | `1536m` |
| `DB_MEMORY_LIMIT` | `1024m` |
| `OLLAMA_MEMORY_LIMIT` | `6g` |
| `SMTP_MEMORY_LIMIT` | `256m` |
| `BACKUP_MEMORY_LIMIT` | `256m` |

### Example production `.env`

```env
APP_PORT=8000
POSTGRES_USER=homeschool
POSTGRES_PASSWORD=replace-with-long-random-password
POSTGRES_DB=homeschool_hero
DATABASE_URL=postgresql+asyncpg://homeschool:replace-with-long-random-password@db:5432/homeschool_hero

SECRET_KEY=replace-with-long-random-secret
SESSION_COOKIE_SECURE=true
TLS_ENABLED=true
HTTPS_REDIRECT_ENABLED=true
INVITATION_BASE_URL=https://school.example.com

BOOTSTRAP_OWNER_EMAIL=admin@example.com
BOOTSTRAP_OWNER_DISPLAY_NAME=Primary Admin
BOOTSTRAP_FAMILY_NAME=Example Family
BOOTSTRAP_TIMEZONE=America/Chicago
BOOTSTRAP_GRADING_SCALE=letter

AUTH_PROVIDER=local
AI_PROVIDER=ollama
OLLAMA_MODEL=llama3.2

SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USERNAME=mailer
SMTP_PASSWORD=replace-me
SMTP_FROM_EMAIL=notifications@example.com
SMTP_USE_TLS=true

BACKUP_TARGET=/data/backups
BACKUP_DESTINATION=local
BACKUP_SCHEDULE=0 2 * * *
BACKUP_RETENTION_DAYS=14
BACKUP_RETENTION_COUNT=3
```

---

## 5. Docker Deployment

### Compose services

`docker-compose.yml` defines these services:

| Service | Default/Profile | Purpose |
| --- | --- | --- |
| `app` | default | FastAPI API + bundled React UI |
| `db` | default | PostgreSQL 16 |
| `ollama` | `ai`, `full` | Local LLM endpoint for grading |
| `smtp` | `email`, `full` | Mailpit for local email testing |
| `backup` | `backup`, `full` | Dedicated scheduled backup worker |

### Profiles

| Profile | Adds |
| --- | --- |
| none | `app`, `db` |
| `ai` | `ollama` |
| `email` | `smtp` |
| `backup` | `backup` |
| `full` | `ollama`, `smtp`, `backup` |

### Volumes and mounts

| Mount | Type | Used by |
| --- | --- | --- |
| `pgdata` | named volume | PostgreSQL data |
| `uploads_data` | named volume | submission uploads |
| `ollama_data` | named volume | Ollama model cache |
| `${BACKUP_MOUNT_SOURCE:-./data/backups}:/data/backups` | bind mount | app + backup artifacts |

### Ports

Base stack:

- `app`: `${APP_PORT:-8000}:8000`

Email profile:

- `${SMTP_DEV_PORT:-1025}:1025`
- `${SMTP_WEB_PORT:-8025}:8025`

TLS override (`docker-compose.tls.yml`):

- `80:80`
- `443:443`

### Networking

- Compose creates an internal project network
- `db` is **not** published externally by default
- `ollama` is **not** published externally by default
- only `app` and optional Mailpit/TLS ports are exposed

### Container hardening

All services inherit:

- `restart: unless-stopped`
- `security_opt: no-new-privileges:true`
- `cap_drop: [ALL]`

Additional details:

- `db` restores the minimum capabilities needed for PostgreSQL initialization: `CHOWN`, `DAC_OVERRIDE`, `FOWNER`, `SETGID`, `SETUID`
- `app`, `backup`, `ollama`, and `smtp` use `read_only: true`
- temporary writable paths are provided with `tmpfs`

### Health checks

| Service | Health command |
| --- | --- |
| `app` | `curl -fsS http://127.0.0.1:8000/api/health` |
| `db` | `pg_isready -U $POSTGRES_USER -d $POSTGRES_DB` |
| `ollama` | `ollama show "$OLLAMA_MODEL"` |
| `smtp` | `wget -qO- http://127.0.0.1:8025/livez` |
| `backup` | `python -m backend.cli backups healthcheck` |

### TLS deployment

For built-in TLS termination:

```bash
docker compose -f docker-compose.yml -f docker-compose.tls.yml up -d --build
```

What the TLS override does:

- adds an `nginx` reverse proxy
- exposes ports `80` and `443`
- sets `SESSION_COOKIE_SECURE=true`
- sets `TLS_ENABLED=true`
- sets `HTTPS_REDIRECT_ENABLED=true`

Use `nginx/nginx-tls.conf` as the reference reverse-proxy config if you terminate TLS elsewhere.

---

## 6. Database Management

### Migration behavior

On startup, Homeschool Hero:

1. validates runtime configuration
2. inspects the current Alembic revision
3. applies pending migrations automatically when `MIGRATION_MODE=apply`
4. refuses startup if migration execution fails

### Migration commands

```bash
python -m backend.cli migrations status
python -m backend.cli migrations upgrade head
python -m backend.cli migrations downgrade -1
python -m backend.cli migrations lint
python -m backend.cli migrations verify
```

Docker examples:

```bash
docker compose exec app python -m backend.cli migrations status
docker compose exec app python -m backend.cli migrations upgrade head
docker compose exec app python -m backend.cli migrations lint
```

Windows wrapper:

```powershell
.\scripts\migrate.ps1 status
.\scripts\migrate.ps1 upgrade head
```

### Connecting to PostgreSQL

```bash
docker compose exec db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"
```

With defaults:

```bash
docker compose exec db psql -U homeschool -d homeschool_hero
```

### Backup behavior

Backup artifacts include:

- a PostgreSQL custom-format dump (`pg_dump --format=custom`) or SQLite file copy
- a copy of `/data/uploads`
- a generated full export ZIP bundle
- a `manifest.json` (plain-copy mode) or manifest stored under `BACKUP_TARGET/manifests` (restic mode)

Run a one-off backup:

```bash
python -m backend.cli backups once
```

Docker:

```bash
docker compose --profile backup run --rm backup python -m backend.cli backups once
```

Or use the helper:

```bash
./scripts/backup.sh
```

### Restore notes

Restore endpoints live under `/api/restore` and support:

- listing available backups
- validation with a confirmation token
- full restore
- selective restore
- retention policy updates and cleanup

For PostgreSQL restores, `pg_restore` must be available.

---

## 7. Security Configuration

### Session and CSRF model

Homeschool Hero uses:

- **signed cookie sessions** (`itsdangerous`)
- **HttpOnly** session cookie
- separate CSRF cookie
- `SameSite=Lax`

All mutating API requests must send the CSRF value in `X-CSRF-Token`.

### Transport security

Recommended production settings:

```env
SESSION_COOKIE_SECURE=true
TLS_ENABLED=true
HTTPS_REDIRECT_ENABLED=true
HSTS_ENABLED=true
HSTS_MAX_AGE_SECONDS=31536000
HSTS_INCLUDE_SUBDOMAINS=true
HSTS_PRELOAD=false
```

The app also sets:

- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- a restrictive `Content-Security-Policy`

### Authentication controls

- local auth is the default
- failed logins are rate-limited and lock out after `AUTH_LOCKOUT_THRESHOLD`
- sessions rotate after `SESSION_ROTATION_SECONDS`
- first-run owner bootstrap is one-time only

### Request rate limits

Built-in limits in `backend/main.py`:

- login/register: **5 requests / 60 seconds per IP**
- submission uploads: **10 requests / 60 seconds**
- exports: **5 mutating requests / 60 seconds**
- general API traffic: **100 requests / 60 seconds**

### OIDC and SAML

OIDC endpoints:

- `GET /api/auth/oidc/login`
- `GET /api/auth/oidc/callback`

SAML endpoints:

- `GET /api/auth/saml/metadata`
- `GET /api/auth/saml/login`
- `POST /api/auth/saml/acs`

Microsoft Entra ID example:

```env
AUTH_PROVIDER=oidc
OIDC_CLIENT_ID=<entra-client-id>
OIDC_CLIENT_SECRET=<entra-client-secret>
OIDC_DISCOVERY_URL=https://login.microsoftonline.com/<tenant-id>/v2.0/.well-known/openid-configuration
AUTH_AUTO_PROVISION_MODE=default_family
AUTH_DEFAULT_FAMILY_NAME=SSO Users
```

### Secrets and credential handling

- never keep production secrets in `.env.example`
- rotate `SECRET_KEY`, database passwords, SMTP credentials, and API keys through your secrets manager or deployment system
- keep `POSTGRES_PASSWORD`, `OIDC_CLIENT_SECRET`, `SAML` secrets, `SMTP_PASSWORD`, and `OPENAI_API_KEY` out of git history

---

## 8. Optional Services

### Ollama AI

Enable:

```bash
docker compose --profile ai up -d --build
```

Defaults:

```env
AI_PROVIDER=ollama
OLLAMA_HOST=http://ollama:11434
OLLAMA_MODEL=llama3.2
```

Notes:

- the `ollama` container preloads `OLLAMA_MODEL` through `scripts/ollama-entrypoint.sh`
- health stays degraded until the model is actually available
- low confidence, OCR failure, AI outage, or an open circuit breaker routes work to human review

### OpenAI alternative

```env
AI_PROVIDER=openai
OPENAI_API_KEY=<your-key>
```

### SMTP / Mailpit

Local email testing:

```bash
docker compose --profile email up -d --build
```

Mailpit endpoints:

- SMTP: `localhost:${SMTP_DEV_PORT:-1025}`
- Web UI: `http://localhost:${SMTP_WEB_PORT:-8025}`

Production SMTP example:

```env
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USERNAME=mailer
SMTP_PASSWORD=<password>
SMTP_FROM_EMAIL=notifications@example.com
SMTP_USE_TLS=true
```

If SMTP is unavailable, invitation delivery falls back to a copyable invitation link.

### Backups / NAS

Enable the dedicated backup worker:

```bash
docker compose --profile backup up -d --build
```

For SMB/NFS, mount the share on the host first, then point `BACKUP_MOUNT_SOURCE` at that mounted path. The container validates writability on startup.

SMB example:

```env
BACKUP_TARGET=/data/backups
BACKUP_DESTINATION=smb
BACKUP_MOUNT_SOURCE=/srv/homeschool-hero-backups
BACKUP_SMB_HOST=nas.local
BACKUP_SMB_SHARE=homeschool-hero
BACKUP_SMB_USER=backup-user
BACKUP_SMB_PASSWORD=<password>
```

NFS example:

```env
BACKUP_TARGET=/data/backups
BACKUP_DESTINATION=nfs
BACKUP_MOUNT_SOURCE=/srv/homeschool-hero-backups
BACKUP_NFS_HOST=nas.local
BACKUP_NFS_PATH=/exports/homeschool-hero
```

### Restic encryption

If `restic` is installed in the runtime image **and** `BACKUP_ENCRYPTION_KEY` is set, backups switch to encrypted incremental snapshots automatically.

The stock Dockerfile does **not** install `restic`, so plain-copy backups are the default unless you extend the image.

---

## 9. CI/CD Pipeline

### Main CI (`.github/workflows/ci.yml`)

Runs on pushes and pull requests to `main`.

Checks:

1. **Backend test matrix**
   - Python `3.11` and `3.12`
   - categories: `unit`, `integration`, `performance`
2. **Backend coverage**
   - Python `3.12`
   - coverage gate: **80%**
3. **Migration checks**
   - PostgreSQL 16 service
   - migration lint
   - upgrade/downgrade verification cycle
4. **Frontend checks**
   - `npm ci`
   - `npm run lint`
   - `npm run build`
5. **Container checks**
   - Docker build
   - Trivy HIGH/CRITICAL gate
6. **Secret scan**
   - Gitleaks

Pull requests also receive a sticky CI summary comment.

### Security pipeline

`security.yml` runs:

- on pull requests to `main`
- manually
- weekly (`0 6 * * 1`)

It performs:

- CodeQL for **Python**
- CodeQL for **JavaScript/TypeScript**
- Trivy image scanning

`security-issues.yml` consumes those artifacts and syncs findings into GitHub issues.

### Release pipeline

`release.yml` runs on tags matching `v*` and:

- builds the container image
- pushes to `ghcr.io/x3nc0n/homeschool-hero`
- tags both the release tag and `latest`
- creates a GitHub release entry

### Auxiliary automation

The repository also includes team automation workflows for issue triage and guarded dependency auto-patching. Those are operational helpers, not required for runtime deployment.

---

## 10. Monitoring & Health Checks

### Public endpoints

| Endpoint | Auth | Purpose |
| --- | --- | --- |
| `/health` | no | Simple alias for API health |
| `/api/health` | no | Simple status/readiness summary |
| `/api/health/ready` | no | Readiness probe |
| `/api/capabilities` | no | Shows optional capability availability |

### Authenticated endpoints

| Endpoint | Purpose |
| --- | --- |
| `/api/health/detailed` | Full service-by-service health |
| `/api/status` | Detailed runtime status, uptime, disk, backup info |
| `/api/metrics` | Runtime metrics payload; requires `ENABLE_METRICS_ENDPOINT=true` |

### What health checks cover

- database connectivity
- optional Redis connectivity
- AI provider reachability
- SMTP reachability
- backup target reachability/writability
- upload disk utilization
- transport flags (`TLS_ENABLED`, redirect, HSTS)

### Useful operational commands

```bash
docker compose ps
docker compose logs -f app
docker compose logs -f db
curl http://localhost:8000/api/health
curl http://localhost:8000/api/health/ready
curl http://localhost:8000/api/capabilities
```

---

## 11. Troubleshooting

### `app` exits immediately on startup

Check:

```bash
docker compose logs app
```

Common causes:

- invalid `DATABASE_URL`
- missing OIDC/SAML settings for the selected `AUTH_PROVIDER`
- unwritable `UPLOAD_DIR`
- invalid backup target configuration

### PostgreSQL fails on first boot with permission/capability errors

This stack intentionally drops Linux capabilities globally. PostgreSQL needs a small exception set on the `db` service. Keep this block in `docker-compose.yml`:

```yaml
cap_add:
  - CHOWN
  - DAC_OVERRIDE
  - FOWNER
  - SETGID
  - SETUID
```

Do **not** remove it while `cap_drop: [ALL]` is still active. That is the fix for the recent `PGDATA` initialization failure.

### Migrations fail after Docker or schema changes

Run:

```bash
python -m backend.cli migrations status
python -m backend.cli migrations lint
python -m backend.cli migrations verify
```

If you changed startup, Docker, or migrations, validate against a clean PostgreSQL path rather than assuming SQLite-only tests are enough.

### Ollama is unhealthy

Check:

```bash
docker compose logs -f ollama
curl http://localhost:11434/api/tags
```

Common causes:

- not enough RAM
- `OLLAMA_MODEL` not pulled/loaded
- `AI_PROVIDER=ollama` with no `ollama` service running

### Email is not sending

- verify `SMTP_HOST`, `SMTP_PORT`, `SMTP_FROM_EMAIL`
- if `SMTP_USERNAME` is set, `SMTP_PASSWORD` must also be set
- for local testing, open Mailpit at `http://localhost:8025`

### `/api/metrics` returns 404

Set:

```env
ENABLE_METRICS_ENDPOINT=true
```

Then authenticate before calling the endpoint.

### Port conflicts

Adjust:

- `APP_PORT`
- `SMTP_DEV_PORT`
- `SMTP_WEB_PORT`

### Reset a disposable local stack

For non-production local data only:

```bash
docker compose down -v
docker compose up --build
```

---

## 12. Maintenance

### Regular update procedure

1. Take a fresh backup
2. Pull the latest code or image
3. Review `.env` changes against `.env.example`
4. Rebuild/redeploy
5. Verify migrations, health, and login

Example:

```bash
git pull
docker compose up -d --build
docker compose exec app python -m backend.cli migrations status
curl http://localhost:8000/api/health
```

### Pre-maintenance checklist

1. Trigger a backup
2. Verify the latest backup succeeded
3. Enable maintenance mode if needed
4. Notify users if the system is public

Maintenance endpoints:

- `GET /api/admin/maintenance`
- `POST /api/admin/maintenance`
- `PUT /api/admin/maintenance/schedule`

### Backup maintenance

- monitor `BACKUP_RETENTION_DAYS` and `BACKUP_RETENTION_COUNT`
- confirm backup target writability
- periodically validate restore flow, not just backup creation

### Dependency management

- Python dependencies live in `requirements.txt`, `requirements-prod.txt`, and `backend/requirements-test.txt`
- frontend dependencies live in `frontend/package.json` and `frontend/package-lock.json`
- CI, Trivy, CodeQL, and Gitleaks are the enforced quality/security gates

### Validation commands used on this repository

These checks pass on the current codebase:

```bash
python -m backend.cli migrations lint
cd backend && TESTING=1 python -m pytest -q
cd frontend && npm run lint
cd frontend && npm run build
```

---

## Reference Links

- Main README: `README.md`
- Development guide: `docs/development.md`
- Auth provider guide: `docs/auth-providers.md`
- Migration policy: `docs/migrations.md`
- TLS guide: `docs/tls-setup.md`
- Maintenance mode guide: `docs/maintenance.md`
