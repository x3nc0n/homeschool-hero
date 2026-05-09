# Venkman UX-03 — Unified search architecture

- **Date:** 2026-05-09
- **Author:** Venkman
- **Context:** UX-03 needs one search experience across multiple family-scoped entities while still supporting SQLite-backed tests and strict student-viewer RBAC.
- **Decision:** Normalize search results behind a single `/api/search` contract that returns entity type, title, snippet, link, timestamps, facet counts, and paginated results. Use PostgreSQL full-text search when available, with SQLite-compatible case-insensitive matching in tests, and enforce family/student scope inside the search service before results are returned.
- **Impact:** Frontend search UI and page-level filters can rely on one consistent API, production search can scale with database indexes, and test environments stay fast and deterministic without a PostgreSQL-only dependency.
