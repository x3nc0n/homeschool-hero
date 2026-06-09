## Ray Security Hardening Batch

- Date: 2026-06-09T17:21:25-05:00
- Context: Issue batch #183, #178, #181, and #180 tightened CI supply-chain controls, migration configuration, reverse-proxy trust, and TLS edge headers.
- Decision:
  - Default backend behavior will **not** trust `X-Forwarded-*` headers; operators must explicitly set `TRUST_PROXY_HEADERS=true` when the app is deployed behind a trusted reverse proxy.
  - Alembic runtime database selection remains owned by `backend/migrations/env.py` via application settings, and `backend/alembic.ini` stays credential-free.
  - Nginx TLS termination includes explicit frame, MIME sniffing, CSP, referrer, and permissions headers as baseline edge hardening.
- Rationale:
  - Default-deny proxy header trust prevents spoofed client IP and scheme headers from weakening rate limiting or cookie security on direct app access.
  - Removing fallback credentials from Alembic avoids shipping a secret-like connection string in repo config while preserving existing migration behavior.
  - Edge security headers provide consistent browser-side protections even before requests hit the app.
