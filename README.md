# Homeschool Hero

[![CI](https://github.com/x3nc0n/homeschool-hero/actions/workflows/ci.yml/badge.svg)](https://github.com/x3nc0n/homeschool-hero/actions/workflows/ci.yml)

Homeschool Hero is a self-hosted homeschool platform for assignments, uploads, OCR-assisted grading, and parent review.

## Quickstart

```bash
git clone https://github.com/x3nc0n/homeschool-hero.git
cd homeschool-hero
# optional: copy .env.example to .env if you want to override defaults
docker compose up --build
# Open http://localhost:8000
```

The default `docker compose up --build` flow starts:

- `app` — FastAPI API + bundled React UI on port `8000`
- `db` — PostgreSQL 16 with persistent data
- `ollama` — local LLM runtime for grading
- `ollama-model` — one-shot model bootstrap that pulls the default grading model before the app starts

Uploads are persisted in a Docker volume mounted at `/data/uploads`, Postgres data is persisted in a named volume, and Ollama models are cached in a named volume. The first startup takes longer because Compose now pulls the default `llama3.2` model automatically so grading works end-to-end without extra setup.

## Environment variables

| Variable | Required | Description |
| --- | --- | --- |
| `POSTGRES_USER` | Yes | Postgres username for the `db` container. |
| `POSTGRES_PASSWORD` | Yes | Postgres password for the `db` container. |
| `POSTGRES_DB` | Yes | Postgres database name. |
| `DATABASE_URL` | Yes | Async SQLAlchemy connection string used by FastAPI and Alembic. |
| `SECRET_KEY` | Yes | Signing key for session cookies. Change this for any real deployment. |
| `SESSION_COOKIE_NAME` | No | Cookie name for the family session. |
| `SESSION_MAX_AGE_SECONDS` | No | Session lifetime in seconds. |
| `FAMILY_PASSWORD` | Yes* | Default family admin password used on first run. |
| `FAMILY_PASSWORD_HASH` | No | Optional bcrypt hash; overrides `FAMILY_PASSWORD` when set. |
| `FAMILY_PIN` | No | Optional alternate PIN login. |
| `FAMILY_PIN_HASH` | No | Optional bcrypt hash for the PIN. |
| `AI_PROVIDER` | No | `ollama` or `openai`. Leave as `ollama` for the standard local stack. |
| `OLLAMA_HOST` | No | Base URL for the Ollama service. |
| `OLLAMA_MODEL` | No | Ollama model name to pre-pull and use for grading. Defaults to `llama3.2`. |
| `OPENAI_API_KEY` | No | Required only when `AI_PROVIDER=openai`. |
| `CONFIDENCE_THRESHOLD` | No | AI auto-approval threshold between `0` and `1`. |
| `GRADING_POLL_INTERVAL` | No | Seconds between grading worker polls. |
| `UPLOAD_DIR` | No | Filesystem path for uploaded work inside the app container. |

\* Set either `FAMILY_PASSWORD` or `FAMILY_PASSWORD_HASH`.

## What the container does on startup

- Runs Alembic migrations automatically
- Waits for PostgreSQL and Ollama to be ready
- Pulls the configured Ollama model automatically
- Ensures the uploads directory exists
- Starts the background grading worker
- Serves the React SPA and FastAPI API from the same port

## Local URLs

- App + API: `http://localhost:8000`
- API health check: `http://localhost:8000/api/health`
- API docs: `http://localhost:8000/docs`
