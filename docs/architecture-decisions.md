# Architecture Decision Records

## ADR-001: Remove Redis dependency (2026-05-10)

### Status
Accepted

### Context
The initial architecture included an optional Redis integration for caching,
with the health check monitoring a `REDIS_URL` configuration. The current
cache layer (`backend/services/cache.py`) uses an in-process `MemoryTTLCache`
that stores entries in a Python dictionary with TTL expiration and ETag
support.

For a single-family homeschool deployment running as a single Docker
container, in-process caching is sufficient. Redis adds operational
complexity (another container, memory, configuration) with no measurable
benefit at this scale.

### Decision
Remove all Redis references:
- The `REDIS_URL` configuration setting
- The Redis health check in the status page
- Any documentation suggesting Redis setup

The in-process `MemoryTTLCache` remains the sole cache backend.

### Consequences
- **Simplified deployment**: One fewer container to manage
- **Status page**: Shows only relevant services (no perpetual "not configured" amber)
- **No cache sharing**: Multiple app replicas cannot share cache state

### Future: Multi-tenant / Scaled Deployment
If Homeschool Hero evolves into a multi-tenant platform (e.g., for a
homeschool co-op, non-profit, or commercial use), the following infrastructure
additions would be warranted:

1. **Redis or Valkey** — Shared cache layer for session storage, rate
   limiting, and cross-replica cache coherence. Re-add `REDIS_URL` to
   `config.py` and implement a `RedisTTLCache` adapter alongside
   `MemoryTTLCache`.

2. **Horizontal scaling** — Multiple app replicas behind a load balancer.
   Requires external session storage (Redis) and sticky sessions or
   JWT-based auth.

3. **Background job queue** — Replace in-process task execution with
   Celery + Redis/RabbitMQ for grading jobs, report generation, and
   backup scheduling.

4. **Database connection pooling** — PgBouncer or similar for connection
   management across multiple replicas.

5. **Object storage** — Move file uploads from local disk to S3-compatible
   storage (MinIO, AWS S3) for durability and horizontal scaling.

6. **Metrics and observability** — Prometheus + Grafana for monitoring,
   OpenTelemetry for distributed tracing.

These changes are intentionally deferred. The current architecture optimizes
for simplicity and ease of deployment for the primary use case: a single
family running Homeschool Hero on their home network or a small VPS.

## ADR-002: Azure Communication Services email integration (2026-05-10)

### Status
Accepted

### Context
The app originally supported only SMTP for sending transactional emails
(notifications, invitations, security alerts). For cloud deployments on
Azure, Azure Communication Services (ACS) provides a managed email service
that eliminates the need to run or configure an SMTP relay.

### Decision
Add `EMAIL_PROVIDER` configuration that supports three modes:
- `smtp` (default) — traditional SMTP relay (backward compatible)
- `acs` — Azure Communication Services email via SDK
- `none` — disable email entirely

The implementation uses a strategy pattern in `backend/services/email_service.py`
that abstracts the sending and health-check logic behind a unified interface.

### Consequences
- **Backward compatible** — existing SMTP users need no changes
- **Azure-native** — cloud deployments can use ACS without SMTP infrastructure
- **New dependency** — `azure-communication-email` package added
- **Connection string auth** — ACS uses connection strings; the deployment
  infrastructure (Bicep) provisions the ACS resource and outputs the
  connection string for the app to consume

### Configuration
```env
EMAIL_PROVIDER=acs
ACS_CONNECTION_STRING=endpoint=https://...;accesskey=...
ACS_SENDER_ADDRESS=DoNotReply@your-domain.azurecomm.net
```
