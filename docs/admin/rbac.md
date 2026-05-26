---
title: RBAC & Roles
description: Role-based access control model — family roles, app roles, capabilities, and SSO integration.
---

# RBAC & Roles

Homeschool Hero uses a **two-axis authorization model** that keeps family membership separate
from platform-level role assertions. This design supports both local authentication families and
SSO-integrated deployments (OIDC, SAML, Entra) without requiring different code paths.

---

## Concepts

### Three axes of authorization

| Axis | Where it lives | What it controls |
|------|---------------|-----------------|
| **Family role** | `FamilyMembership.role` in the database | Family-scoped relationship and household permissions |
| **App role** | Derived from IdP claims or synthesized from family role | Platform-level capability grants |
| **Capability** | Enforced at the route level | The actual permission check |

Routes never check role strings directly — they check **capabilities**. The capability set
for a request is computed from both the family role and the app role, then intersected with
what that user's membership allows.

---

## Family roles

Family roles are stored in `FamilyMembership.role` and represent a user's relationship to
a specific family:

| Family role | Description |
|-------------|-------------|
| `parent` | Primary household administrator. Full curriculum, grading, student management, and household admin. Owners also get `manage_security`. |
| `co_parent` | Same capabilities as `parent`. Designed for spouses or co-administrators. Not an owner by default. |
| `tutor` | Educational access only. Can manage curriculum, submissions, and grading but cannot manage household settings or issue invitations. |
| `student_viewer` | Read-only student experience. Scoped to a specific `student_id` — can only see their own work. |

### Owner flag

The `is_owner` flag on `FamilyMembership` is separate from the family role. Only `parent` users
who are also owners receive `manage_security` — the capability required for security-sensitive
operations. The owner flag is **never derived from IdP claims**; it is always explicit database state.

---

## App roles

App roles are provider-neutral assertions about what a user should be able to do in the
application. They are used to normalize external IdP claims (e.g., Entra roles) into the
capability system.

| App role | Meaning |
|----------|---------|
| `admin` | Platform/IT operations. Does **not** mean family administrator — this is infrastructure access. Includes `manage_platform`, educational capabilities, and read capabilities. |
| `teacher` | Educational administration. Curriculum, submissions, grading, invitations, and read capabilities. |
| `student` | Read-only student experience. Scoped read capabilities and `view_own_progress`. |

For local authentication, app roles are **synthesized** from family roles:

| Family role | Synthesized app roles |
|-------------|----------------------|
| `parent` | `admin` + `teacher` |
| `co_parent` | `admin` + `teacher` |
| `tutor` | `teacher` |
| `student_viewer` | `student` |

This means existing local-auth families work exactly as before — no migration needed.

---

## Capabilities

Capabilities are the actual permission flags checked at route boundaries. They are defined in
`backend/services/rbac.py`:

### Management capabilities

| Capability | Description |
|------------|-------------|
| `manage_household` | Family settings, grading scales, compliance configuration |
| `manage_students` | Create, edit, archive students |
| `manage_platform` | Maintenance mode, backups, restores, export, operational admin |
| `manage_curriculum` | Curriculum packages, units, lessons, standards |
| `manage_submissions` | Upload and manage student submissions |
| `manage_grading` | Grade assignments, manage review queue |
| `manage_invitations` | Send and manage family invitations |
| `manage_security` | Security-sensitive operations (owner-only) |
| `manage_family` | Legacy compatibility alias — maps to `manage_household` + `manage_platform` |

### Read capabilities

| Capability | Description |
|------------|-------------|
| `read_students` | View student records |
| `read_curriculum` | View curriculum packages and lessons |
| `read_submissions` | View submission history |
| `read_grades` | View grade records |
| `view_own_progress` | Student-scoped: view only their own progress |

---

## Capability matrix

This table shows what each role combination can do:

| Role | `manage_household` | `manage_students` | `manage_platform` | `manage_curriculum` | `manage_grading` | `manage_invitations` | `manage_security` | Read |
|------|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|
| `parent` (owner) | ✅ | ✅ | — | ✅ | ✅ | ✅ | ✅ | ✅ |
| `parent` (non-owner) | ✅ | ✅ | — | ✅ | ✅ | ✅ | — | ✅ |
| `co_parent` | ✅ | ✅ | — | ✅ | ✅ | ✅ | — | ✅ |
| `tutor` | — | — | — | ✅ | ✅ | — | — | ✅ |
| `student_viewer` | — | — | — | — | — | — | — | Own only |
| App role `admin` only (SSO) | — | ✅ | ✅ | ✅ | ✅ | ✅ | — | ✅ |
| App role `teacher` only (SSO) | — | — | — | ✅ | ✅ | ✅ | — | ✅ |
| App role `student` only (SSO) | — | — | — | — | — | — | — | Own only |
| `admin` + `teacher` + `parent` (SSO) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | Owner-only | ✅ |

---

## How capabilities are computed

The `derive_effective_capabilities` function in `backend/services/rbac.py` computes the effective
capability set for a request:

```python
def derive_effective_capabilities(
    *,
    family_role: FamilyRole,
    app_roles: Iterable[AppRole],
    is_owner: bool,
) -> set[Capability]:
    # Start with family-role capabilities
    effective = set(_FAMILY_ROLE_CAPABILITIES[family_role])

    # Union in app-role capabilities
    for app_role in normalized_app_roles:
        effective.update(_APP_ROLE_CAPABILITIES[app_role])

    # Owner-only capability
    if is_owner and family_role is FamilyRole.parent:
        effective.add(Capability.manage_security)

    return effective
```

**Key rules:**
- Family role and app role capabilities are **additive** (union)
- `manage_security` is **only** granted to `parent` + `is_owner`
- `manage_platform` is **only** granted via the `admin` app role (not any family role)
- Multiple app roles produce a union of their capabilities

---

## Precedence and conflict resolution

Authorization resolves in this order:

1. **Authenticate** the user and normalize external IdP claims into `AppRole` values
2. **Load `FamilyMembership`** for the selected family
3. **Build effective capabilities** from both axes
4. **Fail closed** on missing or contradictory data

Specific precedence rules:

| Situation | Result |
|-----------|--------|
| IdP `Admin` + membership `tutor` | Platform operations only; no household admin |
| IdP `Teacher` + membership `tutor` | Tutor educational capabilities |
| IdP `Teacher` + membership `parent` | Full parent/co-parent family capabilities |
| IdP `Student` + membership `parent` | **Rejected** — misconfiguration; not silently downgraded |
| No mapped app role from IdP | `403 Forbidden` — no external authorization granted |
| Multiple app roles | **Union** of capability sets, constrained by family membership |

The **narrower result wins** when the family axis and app axis disagree. An IdP claim cannot
elevate a user above their stored family role.

---

## SSO role mapping

When using OIDC or SAML, external IdP role strings must be mapped to Homeschool Hero `AppRole`
values. Configure the mapping in `.env`:

```env
OIDC_ROLE_CLAIM=roles          # Which JWT/OIDC claim contains roles
OIDC_ROLE_MAP_ADMIN=Admin      # IdP role string that maps to app role "admin"
OIDC_ROLE_MAP_TEACHER=Teacher  # IdP role string that maps to app role "teacher"
OIDC_ROLE_MAP_STUDENT=Student  # IdP role string that maps to app role "student"
```

Incoming IdP users are matched to a family by **email address** first. If a matching accepted
`FamilyMembership` exists, the user session reuses that membership. If not, the user is either
auto-provisioned into `AUTH_DEFAULT_FAMILY_NAME` or rejected, based on `AUTH_AUTO_PROVISION_MODE`.

---

## Invitation system

New family members are added through invitations, not open registration. Invitations carry
a `role` field that determines the `FamilyMembership.role` assigned when the invitation is
accepted.

| Invited as | Gets family role | Gets app roles (synthesized) |
|------------|-----------------|------------------------------|
| Parent | `parent` | `admin` + `teacher` |
| Co-parent | `co_parent` | `admin` + `teacher` |
| Tutor | `tutor` | `teacher` |

Student accounts (`student_viewer`) are created directly by a parent, not through invitations.
Each `student_viewer` membership includes a `student_id` that scopes all data access to that
specific student.

Owners can manage invitations at **Settings → Invitations**. The invitation link expires after
`INVITATION_EXPIRY_DAYS` (default: 7 days).

---

## Local auth vs. SSO

| Aspect | Local auth | OIDC / SAML |
|--------|-----------|-------------|
| App role source | Synthesized from `FamilyMembership.role` | Derived from IdP claims via role mapping |
| Family membership required | Yes | Yes — IdP claim alone is not enough |
| `is_owner` source | Database flag | Database flag (never from IdP) |
| New user provisioning | Invitation only | Auto-provision or invitation (configurable) |
| Password management | Managed in-app | Delegated to IdP |
| Breakglass access | Always available | Via `AUTH_BREAKGLASS_LOCAL=true` |

---

## Architecture reference

The full RBAC architecture decision record is in
[Architecture → Unified RBAC Model](/architecture/rbac-unified-model). That document covers
the design rationale, conflict resolution rules, migration path, and API contract changes in detail.

The implementation is in `backend/services/rbac.py`.
