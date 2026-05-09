# Ray CP-02 RBAC + Invitations

- Date: 2026-05-08
- Context: CP-02 needed enforceable family roles across existing APIs plus an invitation flow that works whether SMTP is configured or not. Student-viewer access also needed a reliable way to map a login to one student record.
- Decision: Introduce capability-based backend authorization in `backend/services/authorization.py`, add nullable `student_id` bindings on memberships and invitations for student-viewer scoping, and make invitations return copyable links/codes whenever SMTP is disabled or unavailable.
- Impact: Existing routers can share consistent role checks, student viewers are restricted to one student scope, and family admins can onboard users even in self-hosted environments without email infrastructure.
