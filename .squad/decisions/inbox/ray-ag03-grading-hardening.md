# Ray Decision Inbox — AG-03 Grading Hardening

- **Date:** 2026-05-09
- **Author:** Ray
- **Context:** The grading pipeline now needs to survive OCR/AI outages, expose step-by-step operator state, and support answer-key-assisted scoring without losing auditability.
- **Decision:** Keep grading orchestration on `grading_jobs` with a validated status machine (`pending` → OCR/AI/review steps → `final`), store answer keys separately per assignment, combine answer-key scoring with AI confidence for suggestions, and route timeout/circuit-breaker failures into manual review instead of hard job failure.
- **Impact:** Families get resilient grading behavior, review tools can show precise pipeline progress and override context, and audit records capture both automated grading steps and human finalization.
