# Ray Curriculum API Contract

Timestamp: 2026-06-12T17:48:45.564-05:00

Issue: #165 Phase 1 backend

## Standard import document

`POST /api/curriculum/import` accepts a JSON document with:

- `schema_version`: string, current default `1.0`
- `name`, `description`, `source`
- `metadata`: `grade_levels[]`, `standards_alignment[]`, `estimated_hours`, `prerequisites[]`, plus `external_source` / `extensions`
- `subjects[]`
  - `name`, `description`, `metadata`
  - `units[]`
    - `name`, `description`, `metadata`
    - `lessons[]`
      - `name`, `description`, `estimated_minutes`
      - `objectives[]`
      - `resources[]` with `name`, `description`, `resource_type`, `url`, `tags[]`, `metadata`, `extensions`
      - `metadata`

The backend enforces nested schema validation plus import limits for subjects, units, lessons, objectives, resources, and total payload size.

## Endpoints

### `GET /api/curriculum/schema`
Returns the live JSON schema generated from the backend Pydantic import model.

### `POST /api/curriculum/import`
Creates an imported curriculum source document and returns the persisted nested record with generated IDs, counts, metadata, raw payload, and activation state.

### `GET /api/curriculum`
Lists imported curricula for the current family with summary fields:

- `id`, `name`, `description`, `source`, `schema_version`
- `metadata`
- `subject_count`, `unit_count`, `lesson_count`
- `is_activated`, `last_activation_summary`, `last_activated_at`

### `GET /api/curriculum/{curriculum_id}`
Returns the full nested imported curriculum, including subject/unit/lesson IDs and nullable activation link IDs.

### `POST /api/curriculum/{curriculum_id}/activate`
Request body:

```json
{
  "school_year_id": 1,
  "subject_mappings": { "12": 5 },
  "create_missing_subjects": true,
  "generate_assignments": false
}
```

Behavior:

- Creates one internal curriculum package per imported subject for the selected school year
- Reuses mapped or name-matched subjects, or creates missing subjects when allowed
- Copies imported units and lessons into existing planner tables
- Creates resource records/lesson-resource links for imported lesson resources
- Optionally creates assignments from activated lessons when `generate_assignments=true`
- Saves activation summary plus back-links from imported subject/unit/lesson rows to created internal records

Response summary:

- `curriculum_id`
- `package_ids[]`, `subject_ids[]`, `unit_ids[]`, `lesson_ids[]`, `resource_ids[]`, `assignment_ids[]`
- `generated_assignments`
- `activated_at`

### `DELETE /api/curriculum/{curriculum_id}`
Deletes the imported source document only. Activated internal packages, lessons, resources, and assignments remain as user-owned planning data.
