# Authentication providers

Homeschool Hero keeps local email/password authentication as the default. Set `AUTH_PROVIDER=oidc` or `AUTH_PROVIDER=saml` only when you want to enable a single sign-on overlay.

## Shared settings

| Variable | Description |
| --- | --- |
| `AUTH_PROVIDER` | `local`, `oidc`, or `saml`. |
| `AUTH_AUTO_PROVISION_MODE` | `default_family` to auto-create/match a family membership, or `reject` to require a pre-created user/invitation. |
| `AUTH_DEFAULT_FAMILY_NAME` | Family used when `AUTH_AUTO_PROVISION_MODE=default_family` and no invitation exists. |

Incoming IdP users are matched by email first. If no accepted membership exists, Homeschool Hero auto-accepts a pending invitation for that email. If there is no invitation, the user is either added to `AUTH_DEFAULT_FAMILY_NAME` as a non-owner parent or rejected, based on `AUTH_AUTO_PROVISION_MODE`.

## OIDC configuration

Required when `AUTH_PROVIDER=oidc`:

| Variable | Description |
| --- | --- |
| `OIDC_CLIENT_ID` | OAuth client/application ID from your provider. |
| `OIDC_CLIENT_SECRET` | OAuth client secret. |
| `OIDC_DISCOVERY_URL` | OpenID discovery document URL (`.../.well-known/openid-configuration`). |

Available endpoints:

- `GET /api/auth/oidc/login`
- `GET /api/auth/oidc/callback`

### Microsoft Entra ID example

1. In Microsoft Entra ID, register a new web application.
2. Add a redirect URI pointing to `https://<your-host>/api/auth/oidc/callback`.
3. Create a client secret and copy the **Application (client) ID**.
4. Use the tenant discovery URL in `OIDC_DISCOVERY_URL`, for example:
   `https://login.microsoftonline.com/<tenant-id>/v2.0/.well-known/openid-configuration`
5. Grant `openid`, `profile`, and `email` delegated permissions if your tenant policy requires explicit consent.
6. Set:

```env
AUTH_PROVIDER=oidc
OIDC_CLIENT_ID=<entra-client-id>
OIDC_CLIENT_SECRET=<entra-client-secret>
OIDC_DISCOVERY_URL=https://login.microsoftonline.com/<tenant-id>/v2.0/.well-known/openid-configuration
AUTH_AUTO_PROVISION_MODE=default_family
AUTH_DEFAULT_FAMILY_NAME=John Family
```

Entra often returns `preferred_username` instead of `email`; Homeschool Hero accepts either.

### Entra bearer-token API access

For production API bearer tokens issued by Microsoft Entra ID, configure JWT validation against the tenant-specific JWKS endpoint and require the tenant ID explicitly:

```env
JWT_ENABLED=true
JWT_JWKS_URL=https://login.microsoftonline.com/<tenant-id>/discovery/v2.0/keys
JWT_ISSUER=https://login.microsoftonline.com/<tenant-id>/v2.0
JWT_AUDIENCE=<auth-client-id-or-api-uri>
JWT_TENANT_ID=<tenant-id>
JWT_ALGORITHM=RS256
```

Homeschool Hero treats the Entra `roles` claim as authoritative for RBAC, accepts `groups` only as supporting data, and still requires `X-Family-Id` on bearer requests so the app can rehydrate the caller's family membership before authorization.

## SAML 2.0 configuration

Required when `AUTH_PROVIDER=saml`:

| Variable | Description |
| --- | --- |
| `SAML_METADATA_URL` | Remote IdP metadata XML URL. |
| `SAML_ENTITY_ID` | Service provider entity ID published by Homeschool Hero. |
| `SAML_ACS_URL` | Assertion Consumer Service URL, usually `https://<your-host>/api/auth/saml/acs`. |

Available endpoints:

- `GET /api/auth/saml/metadata`
- `GET /api/auth/saml/login`
- `POST /api/auth/saml/acs`

Suggested values:

```env
AUTH_PROVIDER=saml
SAML_METADATA_URL=https://idp.example.com/metadata
SAML_ENTITY_ID=https://app.example.com/api/auth/saml/metadata
SAML_ACS_URL=https://app.example.com/api/auth/saml/acs
AUTH_AUTO_PROVISION_MODE=reject
```

Use `GET /api/auth/saml/metadata` when your IdP asks for SP metadata.
