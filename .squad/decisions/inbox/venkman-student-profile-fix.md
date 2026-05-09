# Student profile dashboard resilience

- **Date:** 2026-05-09T14:45:14.180-05:00
- **Author:** Venkman

## Context

Student profile pages currently depend on the dashboard aggregator response. If one optional dashboard widget throws while building that payload, the whole student profile fails with a generic error even though the student record itself is valid.

## Decision

Treat student-profile dashboard widgets as best-effort data. The backend should return the rest of the dashboard when optional sections like grade summaries, pacing, compliance, or system health fail, and the frontend should still render the student record even when dashboard widgets are partially unavailable.

## Impact

Student profiles stay usable during partial backend failures or legacy-data issues. This same resilience pattern should be applied to future aggregated views instead of making the whole page depend on every widget succeeding.
