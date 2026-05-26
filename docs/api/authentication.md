---
title: Authentication
description: Session-based auth, CSRF protection, local login, OIDC, and SAML flows for the Homeschool Hero API.
---

# Authentication

Homeschool Hero uses signed session cookies for all browser and API clients. Three authentication methods are supported, controlled by the `AUTH_PROVIDER` environment variable.

## Session & CSRF Model

After any successful login, the server issues two cookies:

| Cookie | Default name | Purpose |
|--------|-------------|---------|
| Session | `homeschool_session` | Signed session identifier; sent automatically by browsers |
| CSRF token | `homeschool_csrf` | Unpredictable token; must be echoed as `X-CSRF-Token` header on mutating requests |

**Read-only requests** (`GET`, `HEAD`, `OPTIONS`) — session cookie only.

**Mutating requests** (`POST`, `PUT`, `PATCH`, `DELETE`) — session cookie **plus** `X-CSRF-Token` header matching the CSRF cookie value.

Cookie names can be changed with `SESSION_COOKIE_NAME` and `CSRF_COOKIE_NAME` env vars.

## Session Response Shape

Every auth endpoint returns the same session envelope on success:

```json
{
  "authenticated": true,
  "user": {
    "id": 1,
    "email": "parent@example.com",
    "display_name": "Jane Smith",
    "is_active": true,
    "auth_provider": "local"
  },
  "family": {
    "id": 1,
    "name": "Smith Family",
    "state_code": "TX",
    "enabled_features": {}
  },
  "membership": {
    "role": "parent",
    "is_owner": true,
    "student_id": null
  },
  "app_roles": ["teacher"],
  "effective_capabilities": [
    "manage_curriculum",
    "manage_grading",
    "manage_students",
    "manage_submissions",
    "read_grades",
    "read_students"
  ],
  "ui_preferences": {}
}
```

`effective_capabilities` drives frontend and backend access control. See [RBAC documentation](/architecture/rbac-unified-model) for the full capability matrix.

## Local Authentication (`AUTH_PROVIDER=local`)

### First-run bootstrap

Check whether the server needs initial setup:

```http
GET /api/auth/bootstrap
```

Returns `{ "bootstrap_required": true }` if no owner account exists yet. Once an owner registers, the bootstrap endpoint is disabled.

### Register (first-run only)

```http
POST /api/auth/register
Content-Type: application/json

{
  "email": "parent@example.com",
  "password": "CorrectHorseBatteryStaple123!",
  "display_name": "Jane Smith",
  "family_name": "Smith Family",
  "timezone": "America/Chicago",
  "grading_scale": "standard"
}
```

Returns `201 Created` with the session envelope and sets session cookies.

### Login

```http
POST /api/auth/login
Content-Type: application/json

{
  "email": "parent@example.com",
  "password": "CorrectHorseBatteryStaple123!",
  "family_id": 1
}
```

Returns `200 OK` with the session envelope. After five consecutive failures the account is temporarily locked (`423 Locked`).

### Logout

```http
POST /api/auth/logout
X-CSRF-Token: <csrf-cookie-value>
```

Clears session cookies and writes an audit log entry.

### Current session

```http
GET /api/auth/me
```

Returns the session envelope for the currently authenticated user. Useful for session restoration on page load.

## OIDC Authentication (`AUTH_PROVIDER=oidc`)

Supports Microsoft Entra ID and any provider with an OpenID Connect discovery document. Requires `OIDC_CLIENT_ID`, `OIDC_CLIENT_SECRET`, and `OIDC_DISCOVERY_URL` environment variables.

### Login flow

1. Redirect the browser to `GET /api/auth/oidc/login` — the server initiates the PKCE handshake.
2. The provider redirects back to `GET /api/auth/oidc/callback` with the authorization code.
3. The server exchanges the code, provisions or matches the user by email, and issues the session cookie.
4. The browser is redirected to `/`.

### Verify OIDC configuration

```http
GET /api/auth/oidc/verify
```

Returns reachability status for the configured OIDC provider. Useful for health checks and admin diagnostics.

### Breakglass local login

When `AUTH_PROVIDER=oidc` (or `saml`) and `AUTH_BREAKGLASS_LOCAL=true`, the local `/api/auth/login` endpoint remains available as a fallback. A warning is logged whenever it is used.

## SAML Authentication (`AUTH_PROVIDER=saml`)

Supports any SAML 2.0 identity provider. Requires `SAML_SP_ENTITY_ID`, `SAML_IDP_METADATA_URL` (or inline metadata), and related environment variables.

### SP metadata

```http
GET /api/auth/saml/metadata
```

Returns the service provider metadata XML. Register this URL or its response with your identity provider.

### Login flow

1. Redirect the browser to `GET /api/auth/saml/login`.
2. The browser is redirected to the IdP login page.
3. The IdP posts a signed assertion to `POST /api/auth/saml/acs` (assertion consumer service).
4. The server validates the assertion, provisions or matches the user, and issues the session cookie.
5. The browser is redirected to `/`.

## API Token (Bearer)

For server-to-server integrations, a JWT bearer token may be passed instead of session cookies:

```http
GET /api/students
Authorization: Bearer <token>
```

Tokens are issued and managed through the admin interface. The token encodes the same `app_roles` and `effective_capabilities` payload as a session cookie.

## Roles and Capabilities

Access control is enforced at the endpoint level by two mechanisms:

**App roles** (set by IdP group claims or admin assignment):

| Role | Implied access |
|------|---------------|
| `admin` | Full platform access — implies teacher and student roles |
| `teacher` | Curriculum, grading, submissions, invitations |
| `student` | Read-only progress for the linked student record |

**Family roles** (set per family membership):

| Role | Key capabilities |
|------|-----------------|
| `parent` / `co_parent` | Manage household, students, curriculum, grading, invitations |
| `tutor` | Manage curriculum, submissions, grading |
| `student_viewer` | View own progress only |

See [Auth Providers](/auth-providers) for full environment variable reference and the Entra ID configuration example.
