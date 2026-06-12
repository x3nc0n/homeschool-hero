# Ray — History

## Learnings

(See history-archive.md for earlier entries prior to 2026-06-09)

- 2026-06-09T21:29:25-05:00 — Uploaded file URLs now must resolve through authenticated `/api/files/{path}` routes instead of a public `/uploads` mount. For mixed storage formats (submission relative paths plus absolute attendance/resource paths), normalize with `resolve_stored_upload_path()` before generating URLs or checking ownership, and enforce student-viewer scope at file download time just like the owning API resource.

- 2026-06-09T10:01:15-05:00 — CodeQL HIGH security fixes: three patterns applied together. (1) **Path injection** — CodeQL's `py/path-injection` sanitiser requires `os.path.realpath()` + `str.startswith(root + os.sep)` at the point of the filesystem operation, not just validation in a helper function; wrapping in a function still leaves the returned `Path` tainted. The trailing `os.sep` guard prevents prefix-collision (e.g. `/uploads-evil` matching against `/uploads`). (2) **Stack trace exposure** — guard public health endpoints with `try/except` that logs server-side and returns a fixed-shape generic response; for OIDC verify, do not return `str(exc)` for unclassified exception types — log at DEBUG and return `None` so callers fall back to a generic message. (3) **Log injection** — pre-compute sanitised values (`sanitized_message`, `sanitized_correlation_id`, etc.) as local variables *before* the `logger.log()` call so CodeQL can see that the values entering the sink are already sanitized, not raw user input.

## Recent Activity

### 2026-06-09 Security Batch Completion
- Completed security hardening batch (#183, #178, #181, #180) and CodeQL findings (#169-#175)
- Backend fixes: path injection, stack-trace exposure, log injection across storage.py, health.py, auth.py, logging_config.py
- Security defaults: disabled proxy-header trust by default, hardened Alembic, added Nginx TLS headers
- PR #193 merged, 362 tests passing, all CodeQL findings remediated

### Egon Issue Triage Session — 2026-06-12

**Status:** 21 issues closed, 2 features tagged for backlog

Egon triaged all 23 open GitHub issues and closed 21:
- **14 issues** already fixed by PR #219 (nginx hardening, backend validation, API hardening, dependencies)
- **7 issues** identified as duplicates of the new security scan batch

**Your assignment:** Continue validation of PR #219 in QA before release. Ray owns:
- Security items #178, #180, #181, #183 (follow-up from Wave 1 triage)
- Backlog items #113, #141 (no action needed at this time)

**Note:** The new security scan (#203–#218) and older batch (#186–#192) have been fully triaged and closed. Next scan cycle will be monitored for false-positive patterns.
