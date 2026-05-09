# Winston SD-03 auto-issue routing decisions

- Date: 2026-05-08
- Requested by: John

## Proposed team-relevant decisions

1. Use stable hidden finding fingerprints inside auto-created security issues so repeated detections refresh the same issue and resolved findings can close automatically on later scans.
2. Require `.trivyignore` entries to carry an adjacent reason comment; the issue automation copies that reason into a `suppressed`-labeled issue and fails if the reason is missing.
3. Route all auto-created security findings through the base `squad` label, then let the existing squad triage workflow assign the right human owner.
