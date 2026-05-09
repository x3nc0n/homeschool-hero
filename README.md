# Homeschool Hero

[![CI](https://github.com/x3nc0n/homeschool-hero/actions/workflows/ci.yml/badge.svg)](https://github.com/x3nc0n/homeschool-hero/actions/workflows/ci.yml)
[![Security](https://github.com/x3nc0n/homeschool-hero/actions/workflows/security.yml/badge.svg)](https://github.com/x3nc0n/homeschool-hero/actions/workflows/security.yml)
[![Container Image](https://img.shields.io/badge/container-ghcr.io%2Fx3nc0n%2Fhomeschool--hero-2496ED?logo=docker&logoColor=white)](https://github.com/x3nc0n/homeschool-hero/pkgs/container/homeschool-hero)

Homeschool Hero is a self-hosted homeschool platform for assignments, uploads, OCR-assisted grading, and parent review.

## Quickstart

```bash
git clone https://github.com/x3nc0n/homeschool-hero.git
cd homeschool-hero
docker compose up --build
# Open http://localhost:8000
```

The default `docker compose up --build` flow starts only the required base stack:

- `app` — FastAPI API + bundled React UI on port `8000`
- `db` — PostgreSQL 16 with persistent data

AI, email, and scheduled backups are optional. If those services are not running, the app stays healthy and reports a degraded-but-usable capability state.

## Compose profiles

Optional services can be enabled without changing application code:

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

## First-run helpers

Use the helper scripts if you want `.env` bootstrapped automatically with a generated `SECRET_KEY`:

```bash
./scripts/start.sh
./scripts/start.sh --profile full
```

```powershell
.\scripts\start.ps1
.\scripts\start.ps1 --profile email
```

Manual backup trigger:

```bash
./scripts/backup.sh
```

## Production deployment

The shipped Compose topology is designed for single-host, self-hosted deployments:

- All services use `restart: unless-stopped`
- Persistent named volumes store database state, uploads, Ollama models, and backups
- Every service defines a health check
- Containers use memory limits
- Security hardening is enabled with dropped Linux capabilities, `no-new-privileges`, and read-only root filesystems where practical
- The app image runs as a non-root user and uses `tini` for signal handling

Recommended production steps:

1. Copy `.env.example` to `.env`
2. Replace `SECRET_KEY`, database credentials, and bootstrap defaults
3. Set `SESSION_COOKIE_SECURE=true` behind HTTPS
4. Set `INVITATION_BASE_URL` to your external URL
5. For production email, replace the default SMTP settings with your real relay
6. For scheduled backups, keep `BACKUP_TARGET=/data/backups` and enable the `backup` profile
7. Enable the `ai` profile only if the host has enough RAM for Ollama

Example:

```bash
docker compose --profile full up -d --build
docker compose ps
docker compose logs -f app
```

## Common operations

```bash
# Validate the rendered Compose config
docker compose config

# Validate the fully enabled stack
docker compose --profile full config

# Stop services but keep data
docker compose down

# Stop services and remove volumes
docker compose down -v

# Review app health
curl http://localhost:8000/health

# Review capabilities
curl http://localhost:8000/api/capabilities
```

## Authentication and tenancy

- First run shows a one-time owner setup flow that creates the first family and owner account.
- Existing single-family installs are migrated into one default family plus one owner user automatically.
- The migrated owner uses `BOOTSTRAP_OWNER_EMAIL` for login and reuses the previous `FAMILY_PASSWORD` or `FAMILY_PASSWORD_HASH` as the new password.
- All family data is tenant-scoped in the API and database using `family_id` foreign keys.
- Local email/password auth remains the default; optional OIDC and SAML overlays can be enabled with `AUTH_PROVIDER`.
- See `docs/auth-providers.md` for Microsoft Entra ID, generic OIDC, and SAML setup details.

## Environment variables

| Variable | Required | Description |
| --- | --- | --- |
| `APP_PORT` | No | Host port published for the web app. |
| `POSTGRES_USER` | Yes | Postgres username for the `db` container. |
| `POSTGRES_PASSWORD` | Yes | Postgres password for the `db` container. |
| `POSTGRES_DB` | Yes | Postgres database name. |
| `DATABASE_URL` | Yes | Async SQLAlchemy connection string used by FastAPI and Alembic. |
| `SECRET_KEY` | Yes | Signing key for session cookies. Change this for any real deployment. |
| `SESSION_COOKIE_NAME` | No | Cookie name for the authenticated user session. |
| `CSRF_COOKIE_NAME` | No | Cookie name for the CSRF token used by authenticated browser requests. |
| `SESSION_MAX_AGE_SECONDS` | No | Session lifetime in seconds. |
| `SESSION_COOKIE_SECURE` | No | Set to `true` when serving over HTTPS. |
| `AUTH_PROVIDER` | No | `local`, `oidc`, or `saml`. Local remains the default. |
| `AUTH_AUTO_PROVISION_MODE` | No | `default_family` to auto-place SSO users, or `reject` to require an invitation or existing membership. |
| `AUTH_DEFAULT_FAMILY_NAME` | No | Family name used when SSO users are auto-provisioned. |
| `OIDC_CLIENT_ID` | No | Required when `AUTH_PROVIDER=oidc`. |
| `OIDC_CLIENT_SECRET` | No | Required when `AUTH_PROVIDER=oidc`. |
| `OIDC_DISCOVERY_URL` | No | Required when `AUTH_PROVIDER=oidc`; OpenID discovery document URL. |
| `SAML_METADATA_URL` | No | Required when `AUTH_PROVIDER=saml`; IdP metadata XML URL. |
| `SAML_ENTITY_ID` | No | Required when `AUTH_PROVIDER=saml`; service provider entity ID. |
| `SAML_ACS_URL` | No | Required when `AUTH_PROVIDER=saml`; Assertion Consumer Service callback URL. |
| `BOOTSTRAP_OWNER_EMAIL` | No | Email used by the initial owner account and migration-created owner user. |
| `BOOTSTRAP_OWNER_DISPLAY_NAME` | No | Display name for the bootstrap owner account. |
| `BOOTSTRAP_FAMILY_NAME` | No | Default family name used during bootstrap and legacy migration. |
| `BOOTSTRAP_TIMEZONE` | No | Default family timezone for bootstrap and legacy migration. |
| `BOOTSTRAP_GRADING_SCALE` | No | Default family grading scale for bootstrap and legacy migration. |
| `FAMILY_PASSWORD` | Yes* | Legacy password source reused when migrating an existing single-family install. |
| `FAMILY_PASSWORD_HASH` | No | Legacy bcrypt hash source reused when migrating an existing single-family install. |
| `INVITATION_BASE_URL` | No | External base URL used when building invitation links. |
| `AI_PROVIDER` | No | `ollama` or `openai`. Leave as `ollama` when the `ai` profile is enabled. |
| `OLLAMA_HOST` | No | Base URL for the Ollama service. |
| `OLLAMA_MODEL` | No | Ollama model name to pre-pull and use for grading. |
| `OPENAI_API_KEY` | No | Required only when `AI_PROVIDER=openai`. |
| `SMTP_HOST` | No | SMTP relay host. Defaults to the optional `smtp` service for local profile-based installs. |
| `SMTP_PORT` | No | SMTP relay port. |
| `SMTP_USERNAME` | No | SMTP username for authenticated relays. |
| `SMTP_PASSWORD` | No | SMTP password for authenticated relays. |
| `SMTP_FROM_EMAIL` | No | Sender address for invitation emails. |
| `SMTP_USE_TLS` | No | Enable STARTTLS for SMTP connections. |
| `SMTP_DEV_PORT` | No | Host port published for the optional local SMTP listener. |
| `SMTP_WEB_PORT` | No | Host port published for the optional Mailpit web UI. |
| `BACKUP_TARGET` | No | Filesystem path used by the app and backup worker for persistent backups. |
| `BACKUP_SOURCE_HOST` | No | Database hostname used by the backup worker. |
| `BACKUP_SOURCE_PORT` | No | Database port used by the backup worker. |
| `BACKUP_INTERVAL_SECONDS` | No | Seconds between scheduled backups in the `backup` profile. |
| `BACKUP_RETENTION_DAYS` | No | Number of days to keep backup artifacts. |
| `BACKUP_FILENAME_PREFIX` | No | Filename prefix for generated backup archives. |
| `CONFIDENCE_THRESHOLD` | No | AI auto-approval threshold between `0` and `1`. |
| `GRADING_POLL_INTERVAL` | No | Seconds between grading worker polls. |
| `UPLOAD_DIR` | No | Filesystem path for uploaded work inside the app container. |
| `MIGRATION_MODE` | No | `apply` auto-upgrades pending migrations on startup; `warn` reports pending migrations without changing schema. |
| `APP_MEMORY_LIMIT` | No | Memory limit for the `app` service. |
| `DB_MEMORY_LIMIT` | No | Memory limit for the `db` service. |
| `OLLAMA_MEMORY_LIMIT` | No | Memory limit for the `ollama` service. |
| `SMTP_MEMORY_LIMIT` | No | Memory limit for the `smtp` service. |
| `BACKUP_MEMORY_LIMIT` | No | Memory limit for the `backup` service. |

\* Keep `FAMILY_PASSWORD` or `FAMILY_PASSWORD_HASH` populated when upgrading an existing installation from the legacy single-family auth model.

## What the container does on startup

- Runs Alembic migrations automatically
- Performs migration preflight checks for connectivity, current revision, pending revisions, and operator timing
- Waits for PostgreSQL
- Starts the background grading worker
- Ensures the uploads directory exists
- Serves the React SPA and FastAPI API from the same port

If the `ai` profile is enabled, the Ollama container also pre-pulls the configured model before becoming healthy.

## Local URLs

- App + API: `http://localhost:8000`
- API health check: `http://localhost:8000/health`
- API docs: `http://localhost:8000/docs`
- Mailpit UI (when `email` profile is enabled): `http://localhost:8025`

## CI/CD and quality gates

Pull requests into `main` are expected to pass these GitHub Actions quality gates before merge:

- **Backend quality gate** — installs OCR dependencies, runs backend pytest, and enforces backend coverage at `76%` or higher.
- **Migration checks** — lints migration rollback discipline, upgrades from baseline to head, downgrades one revision, then upgrades back to head against PostgreSQL.
- **Frontend checks** — runs the existing frontend lint and production build steps.
- **Container checks** — builds the production image, scans it with Trivy, and fails on `HIGH`/`CRITICAL` vulnerabilities unless they are explicitly listed in `.trivyignore`.
- **Secret scan** — runs Gitleaks on pull requests to catch committed secrets early.

Additional automation:

- **Security workflow** — runs weekly and on pull requests with CodeQL plus Trivy image analysis, publishing findings to the GitHub Security tab and artifacting reports for issue automation.
- **Security issue sync** — after each completed security run, opens or refreshes `security` issues for `HIGH`/`CRITICAL` findings, routes them through `squad`, and closes them when the finding disappears.
- **Dependabot** — opens weekly dependency update PRs for pip, npm, and GitHub Actions.
- **Release workflow** — pushing a `v*` tag builds and publishes `ghcr.io/x3nc0n/homeschool-hero`, then creates a GitHub Release with generated notes.

See `docs/security-scanning.md` for the full security scanning playbook, severity guidance, suppression rules, and escalation path.

### Contributor recommendations

- Run backend tests from a clean state with `cd backend && python -m pytest -q`.
- Check migration state with `python -m backend.cli migrations status` or `scripts/migrate.ps1 status`.
- Follow `docs/migrations.md` for upgrade, downgrade, rollback, and migration-authoring discipline.
- Run frontend checks with `cd frontend && npm ci && npm run lint && npm run build`.
- Keep `.trivyignore` limited to reviewed exceptions only, with a reason comment directly above each ignored CVE.
- Add Gitleaks to your local pre-commit workflow so staged changes are scanned before you push.

### Local pre-commit secret scanning

Create `.pre-commit-config.yaml` in the repository root with:

```yaml
repos:
  - repo: https://github.com/gitleaks/gitleaks
    rev: v8.24.2
    hooks:
      - id: gitleaks
```

Then run:

```bash
pip install pre-commit
pre-commit install
pre-commit run gitleaks --all-files
```

### Dependency update process

- Dependabot opens weekly PRs for root pip, backend test pip, frontend npm, and GitHub Actions updates.
- Dependabot PRs are labeled `dependencies`, `type:chore`, and `squad:copilot` for routing.
- Review update PRs against CI, Security, and container scan results before merge.
- If an update cannot merge safely, document the blocker on the PR and suppress only the specific scanner finding that was reviewed.
