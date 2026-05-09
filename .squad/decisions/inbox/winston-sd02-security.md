# Winston SD-02 security scanning decisions

- Date: 2026-05-08
- Requested by: John

## Proposed team-relevant decisions

1. Route Dependabot pull requests with `dependencies`, `type:chore`, and `squad:copilot` so weekly update traffic lands in a predictable lane.
2. Keep Trivy suppressions limited to exact reviewed CVEs in `.trivyignore`; do not use broad severity or package-wide suppressions.
3. Keep Gitleaks false-positive handling narrow: prefer inline `gitleaks:allow`, fall back to `.gitleaksignore` fingerprints only after review.
