# Venkman RC-01 — Report cards and PDF generation

- **Date:** 2026-05-09
- **Author:** Venkman
- **Context:** RC-01 needs printable report cards and in-progress snapshots while reusing AG-04 gradebook calculations and AM-05 attendance data without introducing a separate reporting data pipeline.
- **Decision:** Generate report cards from live gradebook and attendance data per grading period, persist drafts/finals as `report_cards` plus `report_card_entries`, and use ReportLab for server-side PDF rendering so exports stay deterministic in backend tests and do not depend on browser rendering.
- **Impact:** Families get draft/final report cards and printable PDFs from one backend workflow, frontend detail/progress views share the same API contract, and tests can validate PDF bytes plus finalize immutability in SQLite-backed CI.
