---
title: Configuration Reference
description: Complete environment variable reference for Homeschool Hero — auth, email, AI, backups, and more.
---

# Configuration Reference

All Homeschool Hero settings are controlled by environment variables. The Compose stack loads
`.env.example` first, then applies overrides from `.env`. Never commit secrets to `.env.example`.

For a minimal production `.env`, see [Deployment → Production `.env` template](/admin/deployment#production-env-template).

---

## Core application and database

| Variable | Default | Description |
|----------|---------|-------------|
| `APP_PORT` | `8000` | Host port published by the `app` container |
| `POSTGRES_USER` | `homeschool` | PostgreSQL user for the `db` service |
| `POSTGRES_PASSWORD` | `changeme` | PostgreSQL password — **must change** |
| `POSTGRES_DB` | `homeschool_hero` | PostgreSQL database name |
| `DATABASE_URL` | `postgresql+asyncpg://homeschool:changeme@db:5432/homeschool_hero` | Async SQLAlchemy connection URL — must match `POSTGRES_PASSWORD` |
| `SECRET_KEY` | `change-me-in-production` | Session cookie signing key — use a long random value |
| `UPLOAD_DIR` | `/data/uploads` | Upload root inside the container |
| `UPLOAD_MAX_BYTES` | `26214400` | Maximum upload size (25 MiB) |
| `UPLOAD_ALLOWED_MIME_TYPES` | `application/pdf,image/jpeg,image/png,image/heic,image/heif,image/tiff,image/webp` | Allowed upload MIME types |
| `MIGRATION_MODE` | `apply` | `apply` auto-runs pending migrations; `warn` logs only |
| `LOG_LEVEL` | `INFO` | Backend log level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `LOG_JSON` | unset | Enable structured JSON logging (recommended in production) |
| `DEMO_MODE` | `false` | Seeds demo family data on startup; **never enable in production** |

---

## Session and transport security

| Variable | Default | Description |
|----------|---------|-------------|
| `SESSION_COOKIE_NAME` | `homeschool_session` | HttpOnly signed session cookie name |
| `CSRF_COOKIE_NAME` | `homeschool_csrf` | Readable CSRF cookie name |
| `SESSION_MAX_AGE_SECONDS` | `28800` | Session lifetime (8 hours) |
| `SESSION_ROTATION_SECONDS` | `1800` | Active session rotation interval (30 minutes) |
| `SESSION_COOKIE_SECURE` | `false` | Set to `true` behind HTTPS — required in production |
| `TLS_ENABLED` | `false` | Enables HTTPS-aware behavior in the backend |
| `HTTPS_REDIRECT_ENABLED` | `false` | Redirects HTTP to HTTPS (except health check paths) |
| `HSTS_ENABLED` | `true` | Sends HSTS header on secure requests |
| `HSTS_MAX_AGE_SECONDS` | `31536000` | HSTS max-age (1 year) |
| `HSTS_INCLUDE_SUBDOMAINS` | `true` | Adds `includeSubDomains` to HSTS |
| `HSTS_PRELOAD` | `false` | Adds HSTS `preload` — only enable after all subdomains support HTTPS |

---

## Authentication and identity

### Auth provider selection

| Variable | Default | Description |
|----------|---------|-------------|
| `AUTH_PROVIDER` | `local` | Identity provider: `local`, `oidc`, or `saml` |
| `AUTH_AUTO_PROVISION_MODE` | `default_family` | `default_family` auto-creates membership; `reject` requires an invitation |
| `AUTH_DEFAULT_FAMILY_NAME` | `SSO Users` | Family used when `AUTH_AUTO_PROVISION_MODE=default_family` |
| `AUTH_BREAKGLASS_LOCAL` | `true` | Allows local login even when `AUTH_PROVIDER=oidc` or `saml` |
| `AUTH_LOCKOUT_THRESHOLD` | `5` | Failed login attempts before temporary lockout |
| `AUTH_LOCKOUT_MINUTES` | `15` | Lockout duration in minutes |
| `PASSWORD_MIN_LENGTH` | `12` | Minimum local password length |

### OIDC configuration

Required when `AUTH_PROVIDER=oidc`:

| Variable | Description |
|----------|-------------|
| `OIDC_CLIENT_ID` | OAuth client/application ID from your IdP |
| `OIDC_CLIENT_SECRET` | OAuth client secret |
| `OIDC_DISCOVERY_URL` | OpenID discovery document URL (`.well-known/openid-configuration`) |

Available OIDC endpoints:
- `GET /api/auth/oidc/login` — initiates OIDC flow
- `GET /api/auth/oidc/callback` — receives the IdP callback

**Microsoft Entra ID example:**

```env
AUTH_PROVIDER=oidc
OIDC_CLIENT_ID=<entra-client-id>
OIDC_CLIENT_SECRET=<entra-client-secret>
OIDC_DISCOVERY_URL=https://login.microsoftonline.com/<tenant-id>/v2.0/.well-known/openid-configuration
AUTH_AUTO_PROVISION_MODE=default_family
AUTH_DEFAULT_FAMILY_NAME=My Family
```

In Entra: register a web application, add a redirect URI pointing to
`https://<your-host>/api/auth/oidc/callback`, and grant `openid`, `profile`, and `email`
delegated permissions.

### SAML 2.0 configuration

Required when `AUTH_PROVIDER=saml`:

| Variable | Description |
|----------|-------------|
| `SAML_METADATA_URL` | Remote IdP metadata XML URL |
| `SAML_ENTITY_ID` | Service provider entity ID published by Homeschool Hero |
| `SAML_ACS_URL` | Assertion Consumer Service URL (`https://<your-host>/api/auth/saml/acs`) |

Available SAML endpoints:
- `GET /api/auth/saml/metadata` — SP metadata (provide to your IdP)
- `GET /api/auth/saml/login` — initiates SAML login
- `POST /api/auth/saml/acs` — Assertion Consumer Service

### Bearer token (JWT) validation

For API access with Entra-issued JWTs:

| Variable | Description |
|----------|-------------|
| `JWT_ENABLED` | `true` to enable JWT bearer token validation |
| `JWT_JWKS_URL` | JWKS endpoint URL for public key discovery |
| `JWT_ISSUER` | Expected `iss` claim value |
| `JWT_AUDIENCE` | Expected `aud` claim value |
| `JWT_TENANT_ID` | Entra tenant ID (enforced explicitly) |
| `JWT_ALGORITHM` | JWT signing algorithm (e.g., `RS256`) |

Bearer token requests must include `X-Family-Id` so the backend can rehydrate the caller's
family membership. The Entra `roles` claim is authoritative for RBAC; `groups` is accepted
as supplementary data.

---

## Bootstrap and invitations

| Variable | Default | Description |
|----------|---------|-------------|
| `BOOTSTRAP_OWNER_EMAIL` | `owner@homeschool-hero.local` | Default owner email for first-run |
| `BOOTSTRAP_OWNER_DISPLAY_NAME` | `Family Owner` | Owner display name default |
| `BOOTSTRAP_FAMILY_NAME` | `My Family` | Family name default |
| `BOOTSTRAP_TIMEZONE` | `UTC` | Family timezone default (IANA format) |
| `BOOTSTRAP_GRADING_SCALE` | `letter` | Initial grading scale (`letter`, `percentage`, `custom`) |
| `INVITATION_BASE_URL` | `http://localhost:8000` | Base URL used in invitation email links |
| `INVITATION_EXPIRY_DAYS` | `7` | How long an invitation link remains valid |
| `FAMILY_PASSWORD` | `changeme` | Legacy single-family upgrade support only |
| `FAMILY_PASSWORD_HASH` | unset | Optional bcrypt hash for legacy upgrade |

---

## AI grading and OCR

| Variable | Default | Description |
|----------|---------|-------------|
| `AI_PROVIDER` | `ollama` | AI grading provider: `ollama` or `openai` |
| `OLLAMA_HOST` | `http://ollama:11434` | Ollama API base URL |
| `OLLAMA_MODEL` | `llama3.2` | Ollama model name; Compose pre-pulls this model |
| `OPENAI_API_KEY` | unset | Required when `AI_PROVIDER=openai` |
| `CONFIDENCE_THRESHOLD` | `0.8` | Auto-approve threshold (0.0–1.0). Jobs below this go to the human review queue. |
| `GRADING_POLL_INTERVAL` | `5` | Background worker poll interval in seconds |
| `GRADING_REQUEST_TIMEOUT_SECONDS` | `120` | Timeout for AI grading requests |
| `OCR_REQUEST_TIMEOUT_SECONDS` | `120` | Timeout for OCR operations |
| `GRADING_RETRY_ATTEMPTS` | `3` | Retries for OCR/AI calls before failure |
| `GRADING_RETRY_BACKOFF_SECONDS` | `1` | Exponential backoff base delay |
| `AI_CIRCUIT_BREAKER_THRESHOLD` | `3` | Consecutive AI failures before circuit opens |
| `AI_CIRCUIT_BREAKER_RESET_SECONDS` | `300` | Circuit breaker reset window |

When the circuit breaker opens (after `AI_CIRCUIT_BREAKER_THRESHOLD` consecutive failures),
all new grading jobs are routed directly to the human review queue until the reset window passes.

---

## Email

| Variable | Default | Description |
|----------|---------|-------------|
| `EMAIL_PROVIDER` | `smtp` | Email provider: `smtp`, `acs`, or `none` |
| `SMTP_HOST` | `smtp` | SMTP relay hostname |
| `SMTP_PORT` | `1025` (dev) / `587` (backend default) | SMTP port |
| `SMTP_USERNAME` | unset | SMTP username (leave unset for unauthenticated relay) |
| `SMTP_PASSWORD` | unset | SMTP password (required when `SMTP_USERNAME` is set) |
| `SMTP_FROM_EMAIL` | `notifications@homeschool-hero.local` | Sender address |
| `SMTP_USE_TLS` | `false` | Enable STARTTLS for SMTP |
| `ACS_CONNECTION_STRING` | unset | Azure Communication Services connection string |
| `ACS_SENDER_ADDRESS` | unset | Azure Communication Services sender address |
| `SMTP_DEV_PORT` | `1025` | Host port for Mailpit SMTP (dev/test only) |
| `SMTP_WEB_PORT` | `8025` | Host port for Mailpit web UI (dev/test only) |

Set `EMAIL_PROVIDER=none` to disable all email sending (invitations will still be created but
links must be manually shared).

---

## Backups and storage

| Variable | Default | Description |
|----------|---------|-------------|
| `BACKUP_TARGET` | `/data/backups` | Backup output path inside the container |
| `BACKUP_DESTINATION` | `local` | Destination type: `local`, `smb`, or `nfs` |
| `BACKUP_SCHEDULE` | `0 2 * * *` | Cron expression (UTC) for scheduled backups |
| `BACKUP_RETENTION_DAYS` | `14` | Delete backups older than this age |
| `BACKUP_RETENTION_COUNT` | `3` | Minimum number of backups to keep regardless of age |
| `BACKUP_FILENAME_PREFIX` | `homeschool-hero` | Prefix for backup directory names |
| `BACKUP_SCHEDULER_ENABLED` | `true` | Toggle for the built-in backup scheduler |
| `BACKUP_MOUNT_SOURCE` | `./data/backups` | Host path bind-mounted to `/data/backups` |
| `BACKUP_ENCRYPTION_KEY` | unset | Enables restic encryption mode when set |

**SMB (network share) settings:**

| Variable | Description |
|----------|-------------|
| `BACKUP_SMB_HOST` | SMB server hostname or IP |
| `BACKUP_SMB_SHARE` | SMB share name |
| `BACKUP_SMB_USER` | SMB username |
| `BACKUP_SMB_PASSWORD` | SMB password |

**NFS settings:**

| Variable | Description |
|----------|-------------|
| `BACKUP_NFS_HOST` | NFS server hostname or IP |
| `BACKUP_NFS_PATH` | NFS export path |

---

## Observability and metrics

| Variable | Default | Description |
|----------|---------|-------------|
| `ENABLE_METRICS_ENDPOINT` | `false` | Enables authenticated `GET /api/metrics` Prometheus endpoint |

---

## Container resource limits

Override any limit in `.env`:

| Variable | Default |
|----------|---------|
| `APP_MEMORY_LIMIT` | `1536m` |
| `DB_MEMORY_LIMIT` | `1024m` |
| `OLLAMA_MEMORY_LIMIT` | `6g` |
| `SMTP_MEMORY_LIMIT` | `256m` |
| `BACKUP_MEMORY_LIMIT` | `256m` |

---

## Maintenance mode

| Variable | Default | Description |
|----------|---------|-------------|
| `MAINTENANCE_MODE` | `false` | Forces maintenance mode on at startup |
| `MAINTENANCE_MESSAGE` | built-in message | Message returned to non-admin users during maintenance |

See [Operations & Maintenance](/admin/operations) for the full maintenance workflow.
