---
title: Administration
description: Deploy, configure, maintain, and secure your Homeschool Hero instance.
---

# Administration

This section covers everything an administrator needs to run Homeschool Hero in production.
"Administrator" means the person deploying and operating the software — typically the same parent
who owns the family account.

## In this section

| Page | What it covers |
|------|----------------|
| [Deployment](./deployment) | Docker compose profiles, volumes, ports, TLS, container hardening |
| [Configuration](./configuration) | Full environment variable reference: auth, email, AI, backups, storage |
| [Operations & Maintenance](./operations) | Maintenance mode, backups, database management, health checks, upgrades |
| [RBAC & Roles](/admin/rbac) | Role hierarchy, capabilities, family roles vs. app roles, SSO integration |

## Architecture overview

Homeschool Hero runs as a set of Docker containers orchestrated with Compose:

```
┌─────────────────────────────────────────────────────┐
│                   Docker Compose                     │
│                                                     │
│  ┌──────────────────┐    ┌──────────────────────┐   │
│  │   app (default)  │    │     db (default)     │   │
│  │  FastAPI + React │◄──►│   PostgreSQL 16      │   │
│  │  port 8000       │    │   (internal only)    │   │
│  └──────────────────┘    └──────────────────────┘   │
│                                                     │
│  ┌──────────┐  ┌────────┐  ┌──────────────────────┐ │
│  │  ollama  │  │  smtp  │  │        backup        │ │
│  │ (--ai)   │  │(--email│  │      (--backup)      │ │
│  └──────────┘  └────────┘  └──────────────────────┘ │
└─────────────────────────────────────────────────────┘
```

The React frontend is compiled into the Docker image at build time and served by FastAPI from
`frontend/dist`. No separate Node.js process runs in production.

## Configuration approach

All configuration is done through **environment variables**. The Compose stack reads:
1. `.env.example` — safe defaults checked into git
2. `.env` — your local overrides (not committed to git)

Never store secrets in `.env.example`. Always change `SECRET_KEY`, `POSTGRES_PASSWORD`,
`DATABASE_URL`, and `BOOTSTRAP_*` values in your `.env` before any network-accessible deployment.

## Security model

- All containers run with `no-new-privileges`, `cap_drop: ALL`, and `read_only: true` filesystems
  where supported.
- The database is not exposed outside the Docker network by default.
- Sessions are signed with `SECRET_KEY` and protected by CSRF tokens.
- The owner account (`is_owner = true`) is the only identity with `manage_security` capability.
- All authorization is capability-based, not role-string-based, at the route level.

See [RBAC & Roles](/admin/rbac) for the full access control model.
