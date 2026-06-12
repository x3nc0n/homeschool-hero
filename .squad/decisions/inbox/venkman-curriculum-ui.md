# Venkman — Curriculum UI Decision

- Date: 2026-06-12T17:48:45.564-05:00
- Decision: Keep `/curriculum` as the existing hub, make the new Library tab the default manager landing view, preserve the Packages/Lesson Plans/Resources tabs, and add `/curriculum/:curriculumId` for imported-curriculum detail.
- Why: This satisfies issue #165 Phase 1 without breaking the current curriculum workspace routes or sidebar navigation.
- Assumptions: The frontend now accepts both the legacy issue contract shape (`grade_levels`, `estimated_hours`) and Ray’s newer metadata-backed schema, and it uses a dev-only localStorage mock fallback until the backend import endpoints are fully available.
