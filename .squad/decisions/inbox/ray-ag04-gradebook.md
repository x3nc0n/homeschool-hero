# Ray AG-04 Gradebook Model

- **Context:** Weighted gradebooks need configurable category weights, drop-lowest rules, letter grades, GPA mapping, and subject-specific grading behavior without breaking the existing assignment/submission/grade flow.
- **Decision:** Keep `Assignment` as the assessment record, extend it with additional assessment categories, add subject-level grading mode (`points` vs `percentage`), persist `GradeCategory` and `GradeScale` per family, and calculate running weighted grades on demand through a dedicated gradebook service/API.
- **Impact:** Existing grading CRUD stays backward compatible, families can override grade scales per subject, gradebook views stay current without background recomputation, and future reporting can reuse the same calculation service for transcripts and progress reports.
