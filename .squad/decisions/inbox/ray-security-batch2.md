# Ray Security Batch 2

- **Author:** Ray
- **Requested by:** John
- **Date:** 2026-06-09T21:29:25-05:00
- **Issues:** #176, #177, #179, #182, #184, #185

## Decision

- Remove the public `/uploads` static mount and serve uploaded files only through authenticated `/api/files/{path}` downloads.
- File downloads must validate both safe path resolution under `UPLOAD_DIR` and family ownership of the underlying record; student-viewer sessions also keep their student-level scope checks when downloading files.
- Startup must reject default `POSTGRES_PASSWORD` / `FAMILY_PASSWORD` placeholders outside demo mode so production-like deployments fail closed instead of booting with known credentials.
- The TLS nginx container keeps the shared hardening posture (`no-new-privileges`, `cap_drop: ALL`) and restores only `NET_BIND_SERVICE` as the minimal bind capability, with read-only filesystem + tmpfs scratch space.

## Impact

- Student homework, portfolio attachments, curriculum files, and attendance excuse documents are no longer anonymously downloadable by guessed URLs.
- Operators get an immediate startup error if they leave default credentials in place outside demo flows.
- The TLS reverse proxy now matches the repo's container-hardening baseline without losing port 80/443 binding.
