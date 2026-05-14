# Unified RBAC Model

- Status: Accepted
- Date: 2026-05-14T08:57:23-05:00
- Related issues: #97, #98, #99, #100, #101, #102, #103

## Decision summary

Homeschool Hero will keep **family membership** and **authorization** as separate concerns:

1. **`FamilyMembership` + `FamilyRole` remain the persisted family relationship model.** They stay canonical for invitations, ownership, student scoping, and backward compatibility with local auth.
2. **Introduce a provider-neutral `AppRole` layer** for external identity assertions. The normalized values are `admin`, `teacher`, and `student`.
3. **Capabilities remain the canonical enforcement surface.** Route protection should continue to depend on capabilities, but those capabilities will be derived from both the app-role layer and the family-membership layer.
4. **`manage_family` is too overloaded for #97 and must be split during implementation.** `Admin` is explicitly "IT configuration only," so it must not inherit the current family-wide power implied by `parent`.

In short: **store family relationship in `FamilyMembership`; normalize IdP intent into `AppRole`; authorize with effective capabilities computed from both.**

## Why this model

Keeping `FamilyRole` as the only canonical role would force Entra `Admin/Teacher/Student` into family-specific values that do not mean the same thing. Replacing `FamilyRole` outright would break invitations, owner semantics, and existing local-auth families.

The unified model therefore uses a compatibility layer:

- **Family axis:** who the user is inside a family (`parent`, `co-parent`, `tutor`, `student_viewer`)
- **App-role axis:** what the IdP says the user may do in the application (`admin`, `teacher`, `student`)
- **Capability axis:** what the backend actually enforces on routes

## Unified role model

### Family roles (persisted)

| Field | Purpose |
| --- | --- |
| `FamilyMembership.role` | Family-scoped relationship and baseline local-auth permissions |
| `FamilyMembership.is_owner` | Owner-only powers; never inferred from IdP claims |
| `FamilyMembership.student_id` | Required for student-view-only scoping |
| `Invitation.role` | Role requested for a future family membership |

### App roles (normalized external assertions)

| AppRole | Meaning |
| --- | --- |
| `admin` | IT / platform configuration only. Not curriculum, grading, invitations, or student management. |
| `teacher` | Educational administration. May activate parent/co-parent or tutor family permissions depending on stored membership. |
| `student` | Read-only student experience. Must remain student-scoped. |

## Capability model

### Current capability compatibility

The existing capability set is still the immediate source of truth for route enforcement, but the meaning of `manage_family` is too broad.

Implementation must split it into two logical buckets:

| Current capability | Problem | Target meaning |
| --- | --- | --- |
| `manage_family` | Mixes household administration with IT operations | Split into `manage_household` and `manage_platform` |
| `manage_security` | Exists but is not currently the main gate for security-sensitive actions | Keep for owner/security-sensitive flows |
| `manage_invitations` | Family-scoped, not IdP-admin-scoped | Stay family-scoped |
| `manage_curriculum` | Fine as-is | Stay educational |
| `manage_submissions` | Fine as-is | Stay educational |
| `manage_grading` | Fine as-is | Stay educational |
| `read_students`, `read_curriculum`, `read_submissions`, `read_grades` | Fine as-is | Stay readable by teacher/student profiles subject to scope |

### Role / capability matrix

This matrix resolves the tension between the current capability set and the #97 Entra contract.

| Effective profile | `manage_family` (legacy compatibility) | `manage_curriculum` | `manage_submissions` | `manage_grading` | `manage_invitations` | `manage_security` | Read capabilities | New capability intent |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `admin` only | **No** | No | No | No | No | No by default | No | `manage_platform` only |
| `teacher` + `parent` | Yes, but only until split; maps to household admin today | Yes | Yes | Yes | Yes | Owner-only | Yes | `manage_household` + educational capabilities |
| `teacher` + `co-parent` | Yes, but only until split; maps to household admin today | Yes | Yes | Yes | Yes | No | Yes | `manage_household` + educational capabilities |
| `teacher` + `tutor` | No | Yes | Yes | Yes | No | No | Yes | Educational capabilities only |
| `student` + `student_viewer` | No | No | No | No | No | No | Yes, but student-scoped | Read-only student view |
| `admin` + `teacher` + `parent` or `co-parent` | Yes through the teacher+membership side; plus platform ops | Yes | Yes | Yes | Yes | Owner-only | Yes | Household admin + education + platform ops |
| `admin` + `teacher` + `tutor` | No household admin | Yes | Yes | Yes | No | No | Yes | Tutor education + platform ops |

### Mapping Admin / Teacher / Student to existing capabilities

For follow-on implementation issues, use these rules:

- **Admin** does **not** map directly to the current `parent` capability bundle.
- **Teacher** is the only external role that can unlock existing educational management capabilities.
- **Student** only maps to read capabilities, and only when the stored membership is `student_viewer` with a valid `student_id`.
- **Admin** should be implemented through a new `manage_platform` capability family rather than reusing `manage_family`.

## Family scope rules

1. **Every family-scoped session still requires a `FamilyMembership`.** An IdP role does not create family membership by itself.
2. **`is_owner` remains database-backed state.** IdP claims never mint owner status.
3. **`student_id` remains the enforcement key for student-limited access.** A `student` app role without a `student_viewer` membership and `student_id` is invalid for family data access.
4. **Invitations continue to issue family roles, not app roles.** External users receive app roles from the IdP and family roles from accepted invitations/memberships.
5. **A single user may need both axes.** Example: an externally authenticated user who needs curriculum access and maintenance access must have a family membership plus `teacher`, and separately receive `admin` if they also need platform operations.

## Conflict resolution and precedence rules

Authorization resolves in this order:

1. **Authenticate the user** and normalize external role evidence into zero or more `AppRole` values.
2. **Load `FamilyMembership`** for the selected family.
3. **Build effective capabilities** from both sources.
4. **Fail closed** on missing or contradictory data.

Specific precedence rules:

1. **Family membership is authoritative for family scope.** An IdP claim cannot elevate a user above the stored `FamilyRole`, `is_owner`, or `student_id`.
2. **App roles are authoritative for external-role intent.** An externally authenticated user cannot exercise capability families that their IdP role set does not allow.
3. **When the two disagree, the narrower result wins.**
   - IdP `Admin` + membership `tutor` => platform operations only; no curriculum/grading.
   - IdP `Teacher` + membership `tutor` => tutor capabilities.
   - IdP `Teacher` + membership `parent` => parent/co-parent family capabilities, subject to `is_owner`.
   - IdP `Student` + membership `parent` => reject as misconfigured; do not silently downgrade a parent membership into student mode.
4. **Multiple app roles are additive, never substitutive.** `admin` + `teacher` means union of those app-role grants, still constrained by family membership.
5. **No mapped app role means no external authorization.** If OIDC/SAML/JWT claims cannot be mapped to at least one valid `AppRole`, return `403`.

## Backward compatibility and migration path

No database rewrite is required for existing local-auth families.

### Phase 1: compatibility layer

- Keep `FamilyRole`, `Invitation.role`, `is_owner`, and `student_id` unchanged.
- Add `AppRole` normalization for external auth only.
- For **local auth**, synthesize app roles from the stored family role:
  - `parent` => `teacher` + `admin`
  - `co-parent` => `teacher` + `admin`
  - `tutor` => `teacher`
  - `student_viewer` => `student`
- Continue returning the existing membership role to the frontend.

This preserves current behavior for local-auth families while allowing SSO tenants to adopt the stricter #97 model.

### Phase 2: capability split

- Replace legacy `manage_family` checks with explicit target capabilities:
  - student roster, family settings, compliance state, grade scales => `manage_household`
  - maintenance mode, backups, restore, exports, operational admin => `manage_platform`
- Keep `manage_security` for owner/security-sensitive actions.
- Provide a temporary compatibility alias so existing routes can migrate incrementally without breaking current users.

### Phase 3: provider-specific adoption

- #99 defines configurable external role mapping.
- #100 and #101 extract OIDC/SAML role evidence.
- #102 applies the unified capability engine to routes.
- #103 reuses the same model for JWT bearer tokens.

## API contract changes

### Internal `AuthSession`

`AuthSession.role` is currently ambiguous because it only exposes the family role. The internal contract should evolve to:

```python
@dataclass(slots=True)
class AuthSession:
    user_id: int
    family_id: int
    email: str
    display_name: str
    auth_provider: str
    family_role: str
    app_roles: tuple[str, ...]
    is_owner: bool
    family_name: str
    family_state_code: str = 'CUSTOM'
    enabled_features: dict[str, bool] | None = None
    student_id: int | None = None
    ui_preferences: dict[str, str] | None = None
    role: str = ''  # deprecated alias of family_role during migration
```

Recommended semantics:

- `family_role` = persisted `FamilyMembership.role`
- `app_roles` = normalized provider-neutral roles (`admin`, `teacher`, `student`)
- `role` = deprecated alias for backward compatibility with existing callers

### External session response

No breaking frontend change is required in the first implementation wave.

- Keep returning `membership.role` as the family role.
- Add `membership.app_roles` only when the UI needs to differentiate external admin/teacher/student states.
- Do not remove `membership.role` until frontend routing no longer depends on the legacy family-role strings.

## Consequences

- Local-auth families keep working without migration pain.
- External auth gains a clean contract that matches #97.
- `Admin` stops being an accidental synonym for `parent`.
- Invitations, owner semantics, and student scoping remain explicit and auditable.
- Follow-on implementation work can proceed without re-deciding precedence rules.
