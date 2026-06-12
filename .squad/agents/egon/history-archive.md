# Egon — History Archive

(Entries prior to 2026-06-09; summarized for length management)

## RBAC Redesign & Triage (2026-05-22)
- Merged 7 RBAC-related architecture decisions (hierarchy redesign, Ray guardrails, Tully OIDC/security, Venkman service-worker denylist)
- decisions.md grew from 35145 → 44191 bytes
- Ray's RBAC implementation complete with 334 tests passing

## SIEM Architecture Decomposition (2026-05-18)
- Analyzed issue #113 (structured security logging for SIEM integration)
- Designed 4-phase implementation: Phase 1 (types + emitter), Phase 2 (emit at security points), Phase 3 (OpenTelemetry), Phase 4 (docs)
- Created architecture decision + implementation spec; ready for Ray Phase 1–2

## Dependabot Triage (2026-05-18)
- Triaged 10 open Dependabot PRs
- Critical findings: alembic 1.18.4 breaking change, bcrypt 5.0 enforcement, ESLint 10.x ecosystem conflicts
- Assigned domain owners (Ray backend, Venkman frontend)

## PR #109 Approval & v0.9.2 Release (2026-05-15)
- Reviewed PR #109 (multi-provider auth + breakglass local login)
- Initial rejection for `AUTH_BREAKGLASS_LOCAL` semantics conflict
- Re-approved after Winston's fix commit b1fd05c
- v0.9.2 released; all 300 backend tests passing; CVE-2026-32597 closed

## RBAC Unified Model & Issue Chain (2026-05-14)
- Scribe processed spawn manifest outcomes; merged RBAC triage + unified model decision
- Created 6 coordinated issues with dependency chain (#98–#103); all fail-closed on missing mappings
- Architecture decision written: FamilyMembership/FamilyRole as persisted model + AppRole normalization

## Azure Architecture Proposal (2026-05-09)
- Authored comprehensive Azure PaaS architecture proposal (`docs/azure-architecture.md`)
- Key decisions: ACA over AKS, zone-redundant PostgreSQL, Azure AI Document Intelligence, Azure OpenAI
- 5 architecture decision records + cost estimates (~$45/month dev, ~$700/month prod)
- Proposed `Spaidoso/homeschool-hero-azure` repo with 5-phase implementation plan

## Dependabot Backlog Clearance & Cycle (2026-05-09)
- Merged 7 Dependabot PRs (#8, #9, #10, #12, #14, #15, #20)
- Closed #13 as duplicate of #12, #7/#11/#16 after alignment commit
- Verified pytest 9.0.3 + pytest-asyncio 1.3.0 compatibility with asyncio_mode = auto
- 6 CI action bump PRs (#1–6) merged with clean version bumps
- Backend: auto-merge enabled on 8 of 10 PRs; held #9 (pytest 9.x major) and #13 (duplicate)
- Frontend: auto-merge on 1 PR; closed 4 major bumps (React 19, react-router v7, tailwind v4)

## Team Architecture Sync (2026-05-09)
- Ray completed 9 architectural decisions (AG-02, AG-03, AG-04, AG-06, AM-05, CI fixes, DM-02, DM-03, IO-04)
- Ray fixed 3 CI root causes: migration ROLLBACK_NOTES, TLS minimum policy, redundant test definitions
- Venkman fixed ESLint 9.x peer conflict + 3 architectural decisions
- Winston submitted auto-patch policy decision (limited to direct dependencies, human review for high-risk)
- All 14 inbox decisions merged; clear execution path defined

## Security Issue Triage (2026-05-09)
- Triaged 4 open security issues; backend service issues → Ray, test code issues → Winston
- #22 (insecure TLS) → squad:ray; #23–25 (test code) → squad:winston

## Phase 3 Planning Complete (2026-05-08)
- Comprehensive production plan finalized: 40 structured todos across 9 functional areas
- Functional areas: multi-family tenancy, RBAC, academic operations, compliance, data portability, graceful degradation, self-hosted operations, performance, security
- Dependency graph validated; rollout strategy defined
- Team aligned on post-MVP direction

## Phase 1 Completion (2026-05-08)
- All four agents completed MVP workstreams in parallel
- Ray: Backend foundation (CRUD APIs, auth, migrations) ✓ 33 tests
- Venkman: Frontend SPA (10 pages, protected routes) ✓ build passing
- Winston: Test infrastructure (async pytest, mocked deps) ✓ 33 tests
- Scribe archived decisions.md; 4 entries merged, inbox cleared

## Project & Architecture Context (2026-05-08)
- **Project:** homeschool-hero — open-source homeschool platform for families
- **User:** John — mildly IT-inclined parent audience
- **Stack:** Python 3.12 + FastAPI (backend), React 18 + Vite + shadcn/ui (frontend), PostgreSQL 16 (DB)
- **ORM:** SQLAlchemy 2.0 + Alembic migrations
- **OCR:** Tesseract (pytesseract)
- **AI Grading:** Ollama (default) + optional OpenAI fallback
- **Auth:** Single family password, bcrypt hash, session cookie
- **Deployment:** docker-compose (app, db, ollama services)
- **File Storage:** Local filesystem via Docker volume at /data/uploads/
