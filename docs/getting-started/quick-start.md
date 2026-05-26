---
title: Quick Start
description: Install and run Homeschool Hero with Docker in under 10 minutes.
---

# Quick Start

This page gets you from zero to a running Homeschool Hero instance as fast as possible.
It assumes you have Docker and Git installed.

## Prerequisites

- **Docker Engine** (or Docker Desktop) with **Compose v2**
- **Git**
- 4 GB RAM minimum (12–16 GB if you want local AI grading with Ollama)

::: tip Windows users
Use the included PowerShell helper to clone and start in one step:
```powershell
git clone https://github.com/x3nc0n/homeschool-hero.git
cd homeschool-hero
.\scripts\start.ps1
```
:::

---

## Step 1 — Clone the repository

```bash
git clone https://github.com/x3nc0n/homeschool-hero.git
cd homeschool-hero
```

---

## Step 2 — Create your `.env` file

```bash
cp .env.example .env
```

The `.env.example` contains safe defaults that work out of the box for local development.
**Before any internet-facing deployment, you must change:**

| Variable | Why it matters |
|----------|---------------|
| `SECRET_KEY` | Signs session cookies — must be unique and random |
| `POSTGRES_PASSWORD` | Database password |
| `DATABASE_URL` | Must match `POSTGRES_PASSWORD` |
| `BOOTSTRAP_OWNER_EMAIL` | Your admin account email |

Generate a strong secret key:

```bash
# Linux/macOS
python3 -c "import secrets; print(secrets.token_urlsafe(48))"

# Windows PowerShell
[Convert]::ToBase64String([System.Security.Cryptography.RandomNumberGenerator]::GetBytes(48))
```

---

## Step 3 — Start the stack

### Base stack (no AI grading)

```bash
docker compose up -d --build
```

This starts `app` (FastAPI + React UI) and `db` (PostgreSQL 16).

### With AI grading (Ollama)

```bash
docker compose --profile ai up -d --build
```

Adds the `ollama` container. On first boot, Ollama downloads the configured model (default:
`llama3.2`). AI grading features are available once the model is ready — watch progress with
`docker compose logs -f ollama`.

### All optional services

```bash
docker compose --profile full up -d --build
```

Adds `ollama`, `smtp` (Mailpit local relay), and `backup` (scheduled backup worker).

---

## Step 4 — Verify the stack is healthy

```bash
docker compose ps
```

All services should show `healthy` or `running`. Check the app specifically:

```bash
curl http://localhost:8000/api/health
```

Expected response:

```json
{
  "status": "ok",
  "bootstrap_required": true
}
```

`"bootstrap_required": true` means the first-run setup is waiting — that's expected before you
complete the setup wizard.

---

## Step 5 — Complete the setup wizard

Open `http://localhost:8000` in your browser.

You'll be redirected to the **first-run setup wizard**. See the **[Setup Wizard →](./setup-wizard)**
guide for a full walkthrough.

In summary:
1. Create the owner account (email, password, display name)
2. Name your family and choose your timezone
3. Pick a grading scale (letter grades, percentages, or custom)
4. Add your first student

After completing setup, `GET /api/health` will return `"bootstrap_required": false`.

---

## Useful commands

### View logs

```bash
docker compose logs -f app        # Application logs
docker compose logs -f db         # Database logs
docker compose logs -f ollama     # AI model loading progress
```

### Stop the stack

```bash
docker compose down               # Keep data volumes
docker compose down -v            # Destroy all data (use for clean resets)
```

### Restart after config change

```bash
docker compose up -d --build      # Rebuild and restart
```

### Open the API docs

The interactive Swagger UI is available at `http://localhost:8000/api/docs`.

---

## Choosing a Docker profile

| Command | Services started | Use when |
|---------|-----------------|----------|
| `docker compose up -d --build` | `app`, `db` | Basic use, no AI grading |
| `--profile ai` | + `ollama` | AI-assisted grading |
| `--profile email` | + `smtp` | Testing email notifications locally |
| `--profile backup` | + `backup` | Scheduled automated backups |
| `--profile full` | all services | Full local stack |

---

## TLS / HTTPS

For built-in TLS termination via nginx:

```bash
docker compose -f docker-compose.yml -f docker-compose.tls.yml up -d --build
```

This adds an nginx reverse proxy on ports 80 and 443 and automatically sets
`SESSION_COOKIE_SECURE=true`, `TLS_ENABLED=true`, and `HTTPS_REDIRECT_ENABLED=true`.

See [Deployment →](/admin/deployment) for full TLS configuration details.

---

## What's next?

- **[Setup Wizard →](./setup-wizard)** — complete first-run configuration
- **[Administration →](/admin/)** — deeper deployment and configuration reference
- **[Parent & Teacher Guide →](/teacher-guide)** — learn how to use the platform day-to-day
