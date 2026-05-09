# Ray Decision Inbox — AG-02 Submission Versioning

- **Date:** 2026-05-09
- **Author:** Ray
- **Context:** Submission uploads now need deterministic storage, resubmission history, and a single current version that controls grading/review behavior.
- **Decision:** Keep version history on the `submissions` table by adding `submission_version`, `parent_submission_id`, and `is_current`; store files under family/student/assignment/submission folders with extracted file metadata; mark superseded submissions non-current and only allow grading/review on the current version.
- **Impact:** Backup/export layout stays predictable, prior uploads remain viewable, and grading/review logic can safely ignore superseded work without deleting earlier evidence.
