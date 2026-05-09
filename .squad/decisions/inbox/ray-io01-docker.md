# Ray IO-01 — Docker deployment topology

## Context

Homeschool Hero needs a production-ready self-hosted deployment that stays simple for default installs while allowing optional AI, email, and backup services to be enabled with Docker Compose profiles.

## Decision

- Keep the default stack limited to `app` + `db`.
- Add optional Compose profiles:
  - `ai` → `ollama`
  - `email` → local SMTP relay (`smtp`)
  - `backup` → scheduled backup worker
  - `full` → all optional services
- Harden containers with restart policies, named volumes, memory limits, health checks, dropped capabilities, `no-new-privileges`, and read-only root filesystems where practical.
- Run the application container as a non-root user and front it with `tini` for clean signal handling.

## Impact

- Fresh installs still work with `docker compose up --build`.
- Optional services can be turned on without editing app code.
- Backups, uploads, database state, and Ollama models persist across restarts.
- Deployment operations are documented and supported by `scripts/start.sh`, `scripts/start.ps1`, and `scripts/backup.sh`.
