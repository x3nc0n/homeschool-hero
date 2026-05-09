#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ ! -f .env ]]; then
  cp .env.example .env
  python - <<'PY'
from pathlib import Path
import secrets

path = Path(".env")
content = path.read_text(encoding="utf-8")
content = content.replace("SECRET_KEY=change-me-in-production", f"SECRET_KEY={secrets.token_urlsafe(48)}", 1)
path.write_text(content, encoding="utf-8")
PY
  echo "Created .env from .env.example with a generated SECRET_KEY."
fi

docker compose up --build "$@"
