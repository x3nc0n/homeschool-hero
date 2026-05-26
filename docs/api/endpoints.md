---
title: API Endpoints
description: REST endpoints by resource — students, assignments, curriculum, grades, calendar, and more.
---

# API Endpoints

All routes are prefixed with `/api`. Mutating requests require the `X-CSRF-Token` header (or a JWT Bearer token for API integrations).

The notation `[teacher]` / `[parent+]` / `[admin]` indicates the minimum role or capability required.

## Students

Base path: `/api/students`

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| `GET` | `/students` | List students in the family | teacher or student app role |
| `POST` | `/students` | Create a student | `manage_students` capability |
| `GET` | `/students/{student_id}` | Get a single student | teacher or student app role |
| `PUT` | `/students/{student_id}` | Update student name | `manage_students` capability |
| `DELETE` | `/students/{student_id}` | Delete a student | `manage_students` capability |

`student_viewer` role is scoped to the linked student only. Creating a student also auto-generates a default schedule for the active school year.

### Example: Create student

```http
POST /api/students
Content-Type: application/json
X-CSRF-Token: <csrf>

{ "name": "Emma Smith" }
```

Response `201 Created`:

```json
{ "id": 3, "family_id": 1, "name": "Emma Smith" }
```

## Assignments

Base path: `/api/assignments`

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| `GET` | `/assignments` | List assignments (filterable) | teacher or student role |
| `POST` | `/assignments` | Create an assignment | `manage_curriculum` |
| `GET` | `/assignments/{id}` | Get a single assignment | teacher or student role |
| `PUT` | `/assignments/{id}` | Update an assignment | `manage_curriculum` |
| `PATCH` | `/assignments/{id}/status` | Update assignment status | `manage_curriculum` |
| `GET` | `/assignments/{id}/answer-key` | Retrieve the answer key | teacher role |
| `PUT` | `/assignments/{id}/answer-key` | Create or replace answer key | teacher role |
| `DELETE` | `/assignments/{id}` | Delete an assignment | `manage_curriculum` |

`GET /assignments` supports query parameters including `student_id`, `subject_id`, `status`, `grading_period_id`, `page`, and `page_size`. Returns a paginated `AssignmentListResponse`.

## Submissions

Base path: `/api/submissions`

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| `GET` | `/submissions` | List submissions | teacher or student role |
| `POST` | `/submissions` | Upload student work | `manage_submissions` |
| `GET` | `/submissions/{id}` | Get submission detail | teacher or student role |
| `DELETE` | `/submissions/{id}` | Delete a submission | `manage_submissions` |

## Grades

Base path: `/api/grades`

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| `GET` | `/grades` | List grades (filterable by student, subject, page) | teacher or student role |
| `POST` | `/grades` | Record a grade for a submission | teacher role |
| `GET` | `/grades/{id}` | Get a single grade | `read_grades` capability |
| `PUT` | `/grades/{id}` | Update a grade | `manage_grading` capability |
| `DELETE` | `/grades/{id}` | Delete a grade | `manage_grading` capability |
| `GET` | `/grades/history` | Filterable grade history | teacher or student role |
| `GET` | `/grades/averages/student/{student_id}` | Per-subject averages for a student | `read_grades` capability |
| `GET` | `/grades/averages/subject/{subject_id}` | Per-student averages for a subject | `read_grades` capability |
| `GET` | `/grades/gradebook` | Gradebook view (first 100 grades) | `read_grades` capability |

`GET /grades/history` supports: `q` (search), `student_id`, `subject_id`, `grading_period_id`, `term_id`, `score_min`, `score_max`, `date_from`, `date_to`, `page`, `page_size`.

## Gradebook

Base path: `/api/gradebook`

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| `GET` | `/gradebook/categories` | List grade categories | `read_grades` |
| `PUT` | `/gradebook/categories` | Replace grade category list | `manage_grading` |
| `GET` | `/gradebook/scales` | List grade scales | `read_grades` |
| `PUT` | `/gradebook/scales` | Replace grade scale list | `manage_grading` |
| `GET` | `/gradebook/{student_id}` | Full gradebook view for a student | `read_grades` |
| `GET` | `/gradebook/{student_id}/summary` | Subject-level summary | `read_grades` |
| `GET` | `/gradebook/{student_id}/trends` | Grade trend data | `read_grades` |
| `POST` | `/gradebook/calculate` | Recalculate gradebook | `manage_grading` |

## Subjects

Base path: `/api/subjects`

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| `GET` | `/subjects` | List subjects | teacher or student role |
| `POST` | `/subjects` | Create a subject | `manage_curriculum` |
| `GET` | `/subjects/{id}` | Get a single subject | teacher or student role |
| `PUT` | `/subjects/{id}` | Update a subject | `manage_curriculum` |
| `DELETE` | `/subjects/{id}` | Delete a subject | `manage_curriculum` |

## Curriculum

Base path: `/api/curriculum` and `/api/resources`

### Curriculum Packages

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| `GET` | `/curriculum/packages` | List packages | `read_curriculum` |
| `POST` | `/curriculum/packages` | Create a package | `manage_curriculum` |
| `GET` | `/curriculum/packages/{id}` | Get package detail | `read_curriculum` |
| `PUT` | `/curriculum/packages/{id}` | Update a package | `manage_curriculum` |
| `DELETE` | `/curriculum/packages/{id}` | Delete a package | `manage_curriculum` |
| `POST` | `/curriculum/packages/{id}/clone` | Clone a package | `manage_curriculum` |

### Units

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| `GET` | `/curriculum/units` | List units (filterable by `package_id`) | `read_curriculum` |
| `POST` | `/curriculum/units` | Create a unit | `manage_curriculum` |
| `GET` | `/curriculum/units/{id}` | Get a unit | `read_curriculum` |
| `PUT` | `/curriculum/units/{id}` | Update a unit | `manage_curriculum` |
| `DELETE` | `/curriculum/units/{id}` | Delete a unit | `manage_curriculum` |

### Lessons

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| `GET` | `/curriculum/lessons` | List lessons (filterable by `unit_id`) | `read_curriculum` |
| `POST` | `/curriculum/lessons` | Create a lesson | `manage_curriculum` |
| `GET` | `/curriculum/lessons/{id}` | Get a lesson | `read_curriculum` |
| `PUT` | `/curriculum/lessons/{id}` | Update a lesson | `manage_curriculum` |
| `DELETE` | `/curriculum/lessons/{id}` | Delete a lesson | `manage_curriculum` |
| `POST` | `/curriculum/lessons/{id}/resources/{resource_id}` | Link a resource to a lesson | `manage_curriculum` |
| `DELETE` | `/curriculum/lessons/{id}/resources/{resource_id}` | Unlink a resource from a lesson | `manage_curriculum` |

### Resources

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| `GET` | `/resources` | List resources | `read_curriculum` |
| `POST` | `/resources` | Create a resource | `manage_curriculum` |
| `GET` | `/resources/{id}` | Get a resource | `read_curriculum` |
| `PUT` | `/resources/{id}` | Update a resource | `manage_curriculum` |
| `DELETE` | `/resources/{id}` | Delete a resource | `manage_curriculum` |

## Calendar

Base path: `/api/calendar`

### School Years

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| `GET` | `/calendar/school-years` | List school years | any authenticated |
| `POST` | `/calendar/school-years` | Create a school year | `manage_curriculum` |
| `GET` | `/calendar/school-years/{id}` | Get school year detail (with terms) | any authenticated |
| `PUT` | `/calendar/school-years/{id}` | Update a school year | `manage_curriculum` |
| `DELETE` | `/calendar/school-years/{id}` | Delete a school year | `manage_curriculum` |
| `GET` | `/calendar/active` | Get the currently active school year | any authenticated |
| `GET` | `/calendar/{school_year_id}/days` | Instructional day count for the year | any authenticated |

### Terms

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| `GET` | `/calendar/terms` | List terms (filterable by `school_year_id`) | any authenticated |
| `POST` | `/calendar/terms` | Create a term | `manage_curriculum` |
| `GET` | `/calendar/terms/{id}` | Get a term | any authenticated |
| `PUT` | `/calendar/terms/{id}` | Update a term | `manage_curriculum` |
| `DELETE` | `/calendar/terms/{id}` | Delete a term | `manage_curriculum` |

### Grading Periods

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| `GET` | `/calendar/grading-periods` | List grading periods | any authenticated |
| `POST` | `/calendar/grading-periods` | Create a grading period | `manage_curriculum` |
| `GET` | `/calendar/grading-periods/{id}` | Get a grading period | any authenticated |
| `PUT` | `/calendar/grading-periods/{id}` | Update a grading period | `manage_curriculum` |
| `DELETE` | `/calendar/grading-periods/{id}` | Delete a grading period | `manage_curriculum` |

### Calendar Events

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| `GET` | `/calendar/events` | List events | any authenticated |
| `POST` | `/calendar/events` | Create an event | `manage_curriculum` |
| `GET` | `/calendar/events/{id}` | Get an event | any authenticated |
| `PUT` | `/calendar/events/{id}` | Update an event | `manage_curriculum` |
| `DELETE` | `/calendar/events/{id}` | Delete an event | `manage_curriculum` |

## Schedule & Lesson Plans

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/schedule` | List schedules |
| `POST` | `/schedule` | Create a schedule |
| `GET` | `/schedule/{id}` | Get a schedule |
| `PUT` | `/schedule/{id}` | Update a schedule |
| `DELETE` | `/schedule/{id}` | Delete a schedule |
| `GET` | `/lesson-plans` | List lesson plans |
| `POST` | `/lesson-plans` | Create a lesson plan |
| `GET` | `/lesson-plans/{id}` | Get a lesson plan |
| `PUT` | `/lesson-plans/{id}` | Update a lesson plan |
| `DELETE` | `/lesson-plans/{id}` | Delete a lesson plan |

## Reporting & Exports

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/report-cards/generate` | Queue report card generation |
| `POST` | `/transcripts/generate` | Queue transcript generation |
| `POST` | `/compliance-reports/generate` | Queue compliance report |
| `POST` | `/exports` | Create an async export job |
| `GET` | `/exports/{job_id}/status` | Poll export job status |
| `GET` | `/exports/{job_id}/download` | Download completed export |
| `DELETE` | `/exports/{job_id}` | Delete an export job |

## Notifications

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/notifications` | List in-app notifications |
| `PATCH` | `/notifications/{id}/read` | Mark a notification as read |
| `PUT` | `/notifications/preferences` | Update notification preferences |

## Audit Log

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| `GET` | `/audit` | Read audit events (paginated, filterable) | `manage_platform` capability |

The audit log is immutable — records cannot be deleted through the API.

## Health

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Service health check (no auth required) |

Returns `{ "status": "ok" }` when the application and database are reachable.
