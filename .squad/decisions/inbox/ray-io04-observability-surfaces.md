# Ray IO-04 Observability Surfaces

- **Context:** Operators need basic troubleshooting and monitoring without deploying a separate observability stack.
- **Decision:** Use standard Python logging with context-aware JSON output outside tests, generate/request-propagate correlation IDs in middleware, expose an authenticated JSON `/api/metrics` endpoint behind `ENABLE_METRICS_ENDPOINT`, and surface recent activity/system health in the dashboard.
- **Impact:** Request, grading, and backup activity can be traced with consistent fields; slow endpoints and failed jobs are visible in logs and the UI; self-hosted installs can inspect health/metrics without Prometheus, ELK, or another external service.
