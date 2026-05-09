# Ray CP-03 Configuration and Capabilities

- Date: 2026-05-08
- Author: Ray

## Context

CP-03 needed required startup validation without making optional integrations block the app. Docker health checks also needed to stay healthy when optional services like Ollama, SMTP, backup storage, or Tesseract were unavailable.

## Decision

- Treat `DATABASE_URL`, `SECRET_KEY`, and a writable `UPLOAD_DIR` as startup blockers with actionable validation errors.
- Treat AI grading, email, backup, and OCR as optional capabilities that are probed at startup and re-checked on demand through `/api/capabilities` and `/api/health`.
- Keep Docker app startup dependent on PostgreSQL only; optional services can come and go without preventing the API from serving requests.

## Impact

- Operators get clearer setup failures and a safer degraded mode.
- Frontend and backend can both react to capability loss without crashing core workflows.
