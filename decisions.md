# Decisions Log

## Wave 3 Decisions

### Ray AM-01 Academic Calendar

- Date: 2026-05-09
- Author: Ray

#### Context

AM-01 needed family-scoped academic planning with school years, terms, grading periods, holidays, and an instructional day counter that would not drift across timezones.

#### Decision

- Store academic planning boundaries and calendar events as `date` values rather than datetimes.
- Calculate instructional days from weekday defaults across the school year, then apply explicit calendar-event overrides so weekday holidays remove days and custom weekend makeup days add them back.
- Keep calendar management under the existing curriculum RBAC surface: parent/co-parent/tutor can manage, while student viewers remain read-only through calendar GET endpoints.

#### Impact

- The API and frontend can safely exchange `YYYY-MM-DD` values without local/UTC rollover bugs.
- Families can model standard school calendars plus exceptions like closures and Saturday instructional days with predictable day counts.

---

### Ray CP-02 RBAC + Invitations

- Date: 2026-05-08
- Context: CP-02 needed enforceable family roles across existing APIs plus an invitation flow that works whether SMTP is configured or not. Student-viewer access also needed a reliable way to map a login to one student record.
- Decision: Introduce capability-based backend authorization in `backend/services/authorization.py`, add nullable `student_id` bindings on memberships and invitations for student-viewer scoping, and make invitations return copyable links/codes whenever SMTP is disabled or unavailable.
- Impact: Existing routers can share consistent role checks, student viewers are restricted to one student scope, and family admins can onboard users even in self-hosted environments without email infrastructure.

---

### Ray CP-03 Configuration and Capabilities

- Date: 2026-05-08
- Author: Ray

#### Context

CP-03 needed required startup validation without making optional integrations block the app. Docker health checks also needed to stay healthy when optional services like Ollama, SMTP, backup storage, or Tesseract were unavailable.

#### Decision

- Treat `DATABASE_URL`, `SECRET_KEY`, and a writable `UPLOAD_DIR` as startup blockers with actionable validation errors.
- Treat AI grading, email, backup, and OCR as optional capabilities that are probed at startup and re-checked on demand through `/api/capabilities` and `/api/health`.
- Keep Docker app startup dependent on PostgreSQL only; optional services can come and go without preventing the API from serving requests.

#### Impact

- Operators get clearer setup failures and a safer degraded mode.
- Frontend and backend can both react to capability loss without crashing core workflows.

---

### Ray CP-04 Audit Logging

- Date: 2026-05-09
- Author: Ray

#### Context

CP-04 needs a durable audit trail for security-sensitive family activity after multi-family auth, RBAC, and config validation landed. The log must stay append-only, capture request metadata plus before/after state, and only be visible to parent-level family admins.

#### Decision

- Store family-scoped audit events as immutable append-only records in a dedicated `audit_events` table with action enum values, request metadata, and JSON snapshots.
- Centralize event creation in `backend.services.audit.log_event(...)` so routers can add new audit points without duplicating metadata capture logic.
- Expose audit history only through `GET /api/audit`, gated by the existing parent/co-parent `manage_family` capability path, with filterable queries and pagination for the frontend audit log page.

#### Impact

- Families get searchable change history for auth, grading, and invitation actions without exposing edit/delete mutation paths.
- Future backend features can add audit coverage with one helper call and consistent event shape.

---

### Ray CP-05 OIDC + SAML Providers

- Date: 2026-05-09
- Author: Ray

#### Context

John requested Microsoft Entra ID support, but the platform also needs to work with other configurable identity providers and keep local email/password auth as the default.

#### Decision

- Keep `AUTH_PROVIDER=local` as the default runtime mode, with `oidc` and `saml` as optional overlays.
- Match external identities to local users by email first, auto-accept pending invitations when present, and otherwise either place users into a configurable default family or reject them based on `AUTH_AUTO_PROVISION_MODE`.
- Track the provider linkage on `users.auth_provider` and `users.external_id`, and expose the active provider set through `/api/capabilities` so the frontend can render the right login actions.

#### Impact

- Operators can self-integrate Microsoft Entra ID or another OIDC/SAML IdP without breaking existing local auth installs.
- Families can onboard SSO users with minimal manual setup while still retaining a reject-only mode for tighter control.

---

### Ray IO-01 — Docker deployment topology

#### Context

Homeschool Hero needs a production-ready self-hosted deployment that stays simple for default installs while allowing optional AI, email, and backup services to be enabled with Docker Compose profiles.

#### Decision

- Keep the default stack limited to `app` + `db`.
- Add optional Compose profiles:
  - `ai` → `ollama`
  - `email` → local SMTP relay (`smtp`)
  - `backup` → scheduled backup worker
  - `full` → all optional services
- Harden containers with restart policies, named volumes, memory limits, health checks, dropped capabilities, `no-new-privileges`, and read-only root filesystems where practical.
- Run the application container as a non-root user and front it with `tini` for clean signal handling.

#### Impact

- Fresh installs still work with `docker compose up --build`.
- Optional services can be turned on without editing app code.
- Backups, uploads, database state, and Ollama models persist across restarts.
- Deployment operations are documented and supported by `scripts/start.sh`, `scripts/start.ps1`, and `scripts/backup.sh`.

---

### Ray SD-01 Hardening

#### Context

Backend auth already used signed cookies, but session security, CSRF protection, lockout controls, and rate limiting were incomplete. The backend also needed safer validation/error behavior for uploads and malformed payloads without adding deployment-only dependencies.

#### Decision

- Keep the signed-cookie session model, but harden it with secure cookie flags, SameSite=Lax, separate CSRF cookies, expiry-aware rotation, and structured security middleware.
- Use an in-process scoped rate limiter for auth/upload/export/general API traffic so limits can key off the current signed session or client IP without introducing new infrastructure.
- Enforce password policy and account lockout in the auth layer, and centralize request validation hardening plus upload MIME/size checks in backend validation/middleware paths.

#### Impact

- Sensitive state-changing endpoints now require matching CSRF tokens, authenticated traffic gets consistent security headers, and abusive request patterns are throttled before handler logic runs.
- Registration/login/upload failures now return structured non-leaky error payloads, while backend tests cover the new protections end-to-end.

---

### Winston IO-03 migration decisions

- Date: 2026-05-08
- Requested by: John

#### Proposed team-relevant decisions

1. Keep `MIGRATION_MODE=apply` as the default startup behavior so stale schemas never serve traffic silently, but allow `MIGRATION_MODE=warn` for operator-controlled maintenance windows.
2. Require every Alembic migration file to include non-placeholder `ROLLBACK_NOTES`; CI should fail migrations that omit rollback guidance, filename conventions, or a downgrade path.
3. Keep CI migration verification at the operator workflow level: lint migrations, upgrade from baseline to head, downgrade one revision, then upgrade back to head.

---

### Winston SD-02 security scanning decisions

- Date: 2026-05-08
- Requested by: John

#### Proposed team-relevant decisions

1. Route Dependabot pull requests with `dependencies`, `type:chore`, and `squad:copilot` so weekly update traffic lands in a predictable lane.
2. Keep Trivy suppressions limited to exact reviewed CVEs in `.trivyignore`; do not use broad severity or package-wide suppressions.
3. Keep Gitleaks false-positive handling narrow: prefer inline `gitleaks:allow`, fall back to `.gitleaksignore` fingerprints only after review.

---

### Winston SD-03 auto-issue routing decisions

- Date: 2026-05-08
- Requested by: John

#### Proposed team-relevant decisions

1. Use stable hidden finding fingerprints inside auto-created security issues so repeated detections refresh the same issue and resolved findings can close automatically on later scans.
2. Require `.trivyignore` entries to carry an adjacent reason comment; the issue automation copies that reason into a `suppressed`-labeled issue and fails if the reason is missing.
3. Route all auto-created security findings through the base `squad` label, then let the existing squad triage workflow assign the right human owner.
