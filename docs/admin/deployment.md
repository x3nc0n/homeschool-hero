---
title: Deployment
description: Docker Compose deployment guide — profiles, volumes, ports, TLS, and container hardening.
---

# Deployment

Homeschool Hero is designed to be deployed with Docker Compose. This page covers every aspect
of the Docker deployment: services, profiles, volumes, networking, TLS, and container hardening.

---

## System requirements

### Base stack (`app` + `db`)

| Resource | Minimum | Recommended |
|----------|---------|-------------|
| CPU | 2 vCPU | 4 vCPU |
| RAM | 4 GB | 8 GB |
| Disk | 20 GB | 40 GB+ |

### With AI grading (`--profile ai`)

Add at least **6 GB RAM** for the `ollama` container. Practical minimum: **12–16 GB total RAM**.
Memory limits in Compose:

| Container | Default limit |
|-----------|--------------|
| `app` | `1536m` |
| `db` | `1024m` |
| `ollama` | `6g` |
| `smtp` | `256m` |
| `backup` | `256m` |

Override any limit in `.env` (e.g., `OLLAMA_MEMORY_LIMIT=8g`).

### Software prerequisites

**Docker deployment:**
- Docker Engine or Docker Desktop with Compose v2
- Git

**Non-Docker installation:**
- Python 3.12
- Node.js 22 (for frontend build only)
- PostgreSQL 16
- Tesseract OCR
- `pg_dump` / `pg_restore`

---

## Compose services

| Service | Profile | Purpose |
|---------|---------|---------|
| `app` | default | FastAPI backend + compiled React UI |
| `db` | default | PostgreSQL 16 |
| `ollama` | `ai`, `full` | Local LLM endpoint for AI grading |
| `smtp` | `email`, `full` | Mailpit local SMTP relay for testing |
| `backup` | `backup`, `full` | Dedicated scheduled backup worker |

### Starting profiles

```bash
# Base stack only
docker compose up -d --build

# With AI grading
docker compose --profile ai up -d --build

# With email relay (for local dev/test)
docker compose --profile email up -d --build

# With automated backups
docker compose --profile backup up -d --build

# Full stack (all services)
docker compose --profile full up -d --build
```

---

## Volumes and mounts

| Mount | Type | Purpose |
|-------|------|---------|
| `pgdata` | named volume | PostgreSQL data directory |
| `uploads_data` | named volume | Submission file uploads |
| `ollama_data` | named volume | Ollama model cache |
| `${BACKUP_MOUNT_SOURCE:-./data/backups}:/data/backups` | bind mount | Backup artifacts |

::: warning Back up your volumes
`pgdata` and `uploads_data` contain all user data. Include them in your backup strategy.
The `backup` service handles this automatically when enabled.
:::

---

## Ports

| Service | Default | Variable |
|---------|---------|----------|
| `app` | `8000:8000` | `APP_PORT` |
| `smtp` (Mailpit SMTP) | `1025:1025` | `SMTP_DEV_PORT` |
| `smtp` (Mailpit UI) | `8025:8025` | `SMTP_WEB_PORT` |
| nginx (TLS overlay) | `80:80`, `443:443` | — |

The `db` and `ollama` services are **not** exposed outside the Docker network by default.

---

## Networking

Compose creates an isolated internal network for all services. Cross-service communication uses
service names as hostnames (`db`, `ollama`, `smtp`). Only `app` (and optionally the TLS nginx
proxy) publishes ports to the host.

---

## Container hardening

All services inherit these security options:

```yaml
restart: unless-stopped
security_opt:
  - no-new-privileges:true
cap_drop:
  - ALL
```

Additional per-service hardening:

| Service | Extra hardening |
|---------|----------------|
| `db` | Restores minimum caps: `CHOWN`, `DAC_OVERRIDE`, `FOWNER`, `SETGID`, `SETUID` |
| `app`, `backup`, `ollama`, `smtp` | `read_only: true` filesystem + `tmpfs` for writable paths |

---

## Health checks

| Service | Health command |
|---------|---------------|
| `app` | `curl -fsS http://127.0.0.1:8000/api/health` |
| `db` | `pg_isready -U $POSTGRES_USER -d $POSTGRES_DB` |
| `ollama` | `ollama show "$OLLAMA_MODEL"` |
| `smtp` | `wget -qO- http://127.0.0.1:8025/livez` |
| `backup` | `python -m backend.cli backups healthcheck` |

Check container health status:

```bash
docker compose ps
```

Check the app health endpoint directly:

```bash
curl http://localhost:8000/api/health
```

---

## TLS deployment

### Option A — Built-in nginx TLS overlay

```bash
docker compose -f docker-compose.yml -f docker-compose.tls.yml up -d --build
```

The TLS overlay adds an nginx reverse proxy that:
- Listens on ports 80 (HTTP redirect) and 443 (HTTPS)
- Automatically sets `SESSION_COOKIE_SECURE=true`
- Enables `TLS_ENABLED=true` and `HTTPS_REDIRECT_ENABLED=true`
- Configures HSTS headers

Place your TLS certificate and key at the paths expected by `nginx/nginx-tls.conf`.

### Option B — External reverse proxy

If you terminate TLS elsewhere (HAProxy, Traefik, Caddy, Cloudflare Tunnel), configure the
upstream app to trust the proxy:

1. Set `SESSION_COOKIE_SECURE=true` in `.env`
2. Set `TLS_ENABLED=true`
3. Set `HTTPS_REDIRECT_ENABLED=false` (the proxy handles this)
4. Configure your proxy to forward `X-Forwarded-For` and `X-Forwarded-Proto` headers

Use `nginx/nginx-tls.conf` as a reference configuration.

### HSTS settings

| Variable | Default | Notes |
|----------|---------|-------|
| `HSTS_ENABLED` | `true` | Sends HSTS header on secure requests |
| `HSTS_MAX_AGE_SECONDS` | `31536000` | 1-year max-age |
| `HSTS_INCLUDE_SUBDOMAINS` | `true` | Adds `includeSubDomains` |
| `HSTS_PRELOAD` | `false` | Enable only after confirming all subdomains support HTTPS |

---

## Non-Docker installation

### Backend

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Point `DATABASE_URL` at PostgreSQL 16, then:

```powershell
python -m backend.cli migrations upgrade head
uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

### Frontend

```powershell
cd frontend
npm ci
npm run build
cd ..
```

The backend serves the built frontend from `frontend/dist`. Always build the frontend before
starting `uvicorn` in a non-Docker deployment.

---

## Upgrade procedure

1. Pull the latest image or code:
   ```bash
   git pull
   ```
2. Rebuild containers:
   ```bash
   docker compose up -d --build
   ```
3. Migrations run automatically on startup when `MIGRATION_MODE=apply` (the default).
4. Verify health:
   ```bash
   curl http://localhost:8000/api/health
   docker compose ps
   ```

::: tip Pre-upgrade backup
Always run a backup before upgrading:
```bash
docker compose --profile backup run --rm backup python -m backend.cli backups once
```
:::

---

## Production `.env` template

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

EMAIL_PROVIDER=smtp
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
