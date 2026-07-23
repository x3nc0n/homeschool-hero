# API tokens for headless curriculum and grading automation

Use API tokens when automation cannot complete interactive browser sign-in.

## Prerequisites

Set JWT signing for HS256:

```env
JWT_ENABLED=true
JWT_SECRET=<32+-character-random-secret>
JWT_ALGORITHM=HS256
JWT_ISSUER=https://your-app.example
JWT_AUDIENCE=homeschool-hero
API_TOKEN_DEFAULT_EXPIRY_DAYS=90
API_TOKEN_MAX_EXPIRY_DAYS=365
API_TOKEN_MAX_ACTIVE_PER_FAMILY=10
```

`JWT_SECRET` must be present and at least 32 characters.

## API lifecycle

1. Create token (`manage_security` required):
   - `POST /api/auth/api-tokens`
2. List token metadata:
   - `GET /api/auth/api-tokens`
3. Revoke token:
   - `DELETE /api/auth/api-tokens/{id}`

Token values are returned **once** at creation and never returned by list endpoints.

## Example requests

Create token:

```bash
curl -X POST "$BASE_URL/api/auth/api-tokens" \
  -H "Content-Type: application/json" \
  -H "X-CSRF-Token: <csrf-token>" \
  -b "<session-cookie>" \
  -d '{"name":"grading-automation","capabilities":["manage_submissions","manage_grading"],"expires_in_days":90}'
```

List metadata:

```bash
curl "$BASE_URL/api/auth/api-tokens" \
  -H "X-CSRF-Token: <csrf-token>" \
  -b "<session-cookie>"
```

Use bearer token for automation:

```bash
curl -X POST "$BASE_URL/api/submissions" \
  -H "Authorization: Bearer <api-token>" \
  -F "assignment_id=<assignment-id>" \
  -F "student_id=<student-id>" \
  -F "file=@<submission-file>"
```

Revoke:

```bash
curl -X DELETE "$BASE_URL/api/auth/api-tokens/<token-id>" \
  -H "X-CSRF-Token: <csrf-token>" \
  -b "<session-cookie>"
```
