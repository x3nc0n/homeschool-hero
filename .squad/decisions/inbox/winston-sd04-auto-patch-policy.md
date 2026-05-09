# Winston SD-04 — Guarded auto-patch policy

- **Date:** 2026-05-08
- **Author:** Winston
- **Context:** Security issue sync now creates normalized GitHub issues for HIGH/CRITICAL findings, and SD-04 adds automated triage plus dependency patch generation.
- **Decision:** Limit automatic remediation to direct dependency version bumps in tracked Python and frontend manifests. Route all CodeQL findings, base-image/container package findings, transitive dependency updates, and ambiguous fixes to `needs-human-review`. Require the mirrored CI gate set to pass before opening an auto-generated PR, and never auto-merge critical or non-dependency findings without explicit human sign-off.
- **Impact:** Security issues now have a clear audit trail, low-risk dependency fixes can be proposed quickly, and reviewers keep control over high-risk remediation.
