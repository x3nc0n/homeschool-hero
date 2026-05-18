# Venkman ESLint upgrade

- Date: 2026-05-18T16:38:51.741-05:00
- Requester: John
- Scope: frontend dependency maintenance

## Decision

Upgrade `frontend` to `eslint@^10.4.0` and `@eslint/js@^10.0.1` together, and commit `frontend/.npmrc` with `legacy-peer-deps=true` as a temporary install compatibility shim.

## Why

- Dependabot PR #92 (`@eslint/js` 10) conflicts with ESLint 9 because `@eslint/js@10.0.1` declares `peerOptional eslint@^10.0.0`.
- Dependabot PR #136 (`eslint` 10) should not land separately from the `@eslint/js` major bump because the flat config imports `@eslint/js` directly.
- `eslint-plugin-jsx-a11y@6.10.2` is still the latest release and only declares peer support through ESLint 9, but linting still passes with ESLint 10 in this repo.
- The `.npmrc` shim keeps `npm install` working without dropping accessibility lint coverage.

## Validation

- `cd frontend && npm install`
- `cd frontend && npm run lint`
- `cd frontend && npm run build`
