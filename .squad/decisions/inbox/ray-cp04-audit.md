# Ray CP-04 Audit Logging

- Date: 2026-05-09
- Author: Ray

## Context

CP-04 needs a durable audit trail for security-sensitive family activity after multi-family auth, RBAC, and config validation landed. The log must stay append-only, capture request metadata plus before/after state, and only be visible to parent-level family admins.

## Decision

- Store family-scoped audit events as immutable append-only records in a dedicated `audit_events` table with action enum values, request metadata, and JSON snapshots.
- Centralize event creation in `backend.services.audit.log_event(...)` so routers can add new audit points without duplicating metadata capture logic.
- Expose audit history only through `GET /api/audit`, gated by the existing parent/co-parent `manage_family` capability path, with filterable queries and pagination for the frontend audit log page.

## Impact

- Families get searchable change history for auth, grading, and invitation actions without exposing edit/delete mutation paths.
- Future backend features can add audit coverage with one helper call and consistent event shape.
