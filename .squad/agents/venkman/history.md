# Venkman — History

## Learnings

### ESLint version constraints (2026-05-09T07:12:14.142-05:00)
- `eslint-plugin-jsx-a11y@6.10.2` (latest) declares peer `eslint@"^3 || ... || ^9"` — ESLint 10 is not supported.
- ESLint is pinned to `^9.9.0` (with `@eslint/js` to match) because that's the minimum version providing the `defineConfig`/`globalIgnores` flat-config helpers used in `eslint.config.js`.
- `typescript-eslint@8.x` supports ESLint `^8 || ^9`, so no changes needed there.
- If upgrading ESLint to 10 in future, first confirm `eslint-plugin-jsx-a11y` has released a compatible version.

- Project: homeschool-hero — open-source homeschool platform for families
- User: John
- Target users: parents (primary), students only for upload
- Key UI flows: assignment management, file upload (scan/photo), grade review, quiz/test creation
- Must be simple enough for "mildly IT-inclined" parents
- Mobile-friendly upload flow is critical (phone photos of assignments)
- **GitHub Repository:** https://github.com/x3nc0n/homeschool-hero
- 2026-05-08T17:04:55.759-05:00: Implemented full React 18 + TypeScript frontend with routed pages for login, dashboard, students, subjects, assignments, uploads, grade book, quizzes, and review queue.
- 2026-05-08T17:04:55.759-05:00: Added typed API client with VITE_API_URL fallback to /api, session-aware auth context, responsive navigation shell, loading/error/empty states, and shadcn UI component system.

### Phase 1 Completion (2026-05-08T22:04:55Z)
- Frontend tasks 9-16, 20 completed successfully: React SPA with all pages, protected routing, API integration ✓
- Build passing, all parent workflows wired end-to-end: auth, dashboard, student/subject/assignment CRUD, uploads, grade book, quiz builder/taker, review queue ✓
- Ready for user feedback and phase 2 refinements

### Frontend Bundling: Docker Integration (2026-05-08T23:50:20Z)
- Frontend SPA now bundled into FastAPI backend container
- Built React artifacts served as static files from /app/dist/
- SPA routing preserved via FastAPI fallback to index.html
- Single-port deployment: backend API on /api + frontend on /
- Frontend no longer requires separate development/build infrastructure
- CORS configured for both dev (localhost) and prod deployment
### UX-02 Notifications (2026-05-09T00:06:56-05:00)
- Added backend notification models, Alembic migration, notification service, notification APIs, and background checks for due dates and backup alerts.
- Hooked notifications into grading completion, invitation events, and security lockouts with optional SMTP email delivery plus per-user preferences.
- Added frontend bell dropdown, full notifications page, notification preferences page, and validated with `cd backend && python -m pytest -v` plus `cd frontend && npm run build`.

### UX-03 Search and advanced filtering (2026-05-09T03:55:00-05:00)
- Added a unified backend search service and `/api/search` endpoint spanning assignments, grades, students, subjects, attendance notes, audit logs, curriculum, resources, and notifications with family/RBAC scoping, filters, snippets, and pagination.
- Added global header search with Ctrl/Cmd+K, a dedicated search results page with facets/recent searches, and expanded inline filtering on assignments and grades to use backend-powered query parameters.
- Validated with `cd backend && python -m pytest -v` (`115 passed, 1 skipped`) and `cd frontend && npm run build`.
### RC-03 Portfolio and learning journal (2026-05-08T23:05:00-05:00)
- Added portfolio and learning journal backend support: portfolio entry/collection models, Alembic migration, CRUD/filter/share/public APIs, attachment uploads, audit hooks, and family-isolated tests.
- Added frontend portfolio workspace with entry/journal views, collection builder with drag-and-drop, public share page, typed API client support, and navigation/routes for parents, tutors, and student viewers.
- Validated with cd backend && python -m pytest -q (133 passed, 1 skipped) and cd frontend && npm run build.

### RC-01 Report cards and progress reports (2026-05-09T07:05:00-05:00)
- Added backend report card support with new report card/report card entry models, Alembic migration, generation service, family-scoped APIs, PDF export, finalize workflow, and report-card tests covering aggregation, immutability, PDF output, and family isolation.
- Added frontend report cards workspace with generation by student/grading period, draft detail/editing, progress-report snapshot, finalize controls, PDF download, typed API client updates, navigation, and routing.
- Hardened async assignment/report-card flows to avoid lazy-load `MissingGreenlet` regressions and validated with `cd backend && python -m pytest -q` (`152 passed, 1 skipped`) plus `cd frontend && npm run build`.

### RC-04 State compliance reporting (2026-05-09T02:07:44-05:00)
- Added backend compliance report support with a new `ComplianceReport` model, Alembic migration, generation service, required-report checklist logic, PDF export, finalize flow, and family-scoped APIs for annual assessments, quarterly reports, attendance logs, portfolio reviews, and notices of intent.
- Added frontend compliance reports workspace with student/year/report-type generation, required checklist visibility, draft preview/finalize/download actions, new API client/types, navigation/routing, and a compliance dashboard handoff card into the reporting workflow.
- Validated with `cd backend && python -m pytest -q` (`158 passed, 1 skipped`) plus `cd frontend && npm run build`.
### UX-01 Unified dashboard and views (2026-05-09T04:01:07-05:00)
- Replaced the legacy dashboard with a unified `/api/dashboard` aggregator that rolls up today’s schedule, next-7-day assignments, recent grades, attendance snapshots, pacing alerts, compliance warnings, per-student summary cards, and system health in one response with student-viewer filtering.
- Rebuilt the frontend landing experience around that single API call: dashboard is now the home route, student profile drill-down pages were added, dashboard widgets are collapsible, refreshable, and responsive, and navigation moved to a grouped sidebar with breadcrumbs and active states.
- Validated with `cd backend && python -m pytest -q` (`184 passed, 1 skipped`) plus `cd frontend && npm run build`.

### UX-05 Mobile-responsive PWA (2026-05-09T04:19:50-05:00)
- Added a mobile-ready PWA shell with `vite-plugin-pwa`, a checked-in manifest, generated 192/512 SVG icons, service-worker caching for the app shell/static assets/API reads, install prompting, offline-ready/update banners, and an offline status indicator.
- Reworked the app shell for handheld use with a hamburger drawer, bottom tab navigation, larger touch targets, mobile-safe form controls, and pull-to-refresh support on dashboard, student detail, upload, and attendance views.
- Upgraded assignment upload and attendance mobile UX with camera capture + preview flow, swipe-to-mark attendance cards on small screens, and responsive attendance card/table layouts; validated with `cd frontend && npm run build`, `cd frontend && npm run test:i18n`, and a manifest JSON validation check.
### UX-06 Accessibility WCAG 2.1 AA compliance (2026-05-09T04:19:50-05:00)
- Added frontend accessibility guardrails: skip-to-content link, stronger focus styling, live-region announcements, semantic card/empty/loading/error primitives, keyboard-friendly mobile navigation, notification panel dialog semantics, and automatic label-to-control association for shared form layouts.
- Added `eslint-plugin-jsx-a11y`, fixed current accessibility lint issues, increased touch target sizing in shared controls, documented the manual accessibility checklist in `docs/accessibility-checklist.md`, and kept frontend validation green with `cd frontend && npm run lint` plus `cd frontend && npm run build`.
- Revalidated the full stack with `cd backend && python -m pytest -q` (`187 passed, 1 skipped`).
### UX-04 Themes and customization (2026-05-09T04:51:12-05:00)
- Added a full appearance system with a ThemeProvider, localStorage-backed preferences, light/dark/high-contrast themes, accent color overrides, font size and density controls, and a desktop sidebar position toggle that supports left, right, and collapsed layouts.
- Added backend-backed UI preferences with a new user preferences model, migration, auth session payload support, and authenticated `GET/PUT /api/users/preferences` endpoints so saved appearance choices load immediately after sign-in.
- Added a dedicated Appearance settings page with live preview and reset/save flows, then validated with `python -m pytest backend\tests\test_user_preferences.py backend\tests\test_auth.py -q` plus `cd frontend && npm run lint && npm run build`.

### Team Architecture Sync (2026-05-09T12:25:20Z)
- Ray submitted 9 architectural decisions: AG-02 (submission versioning), AG-03 (grading hardening), AG-04 (gradebook model), AG-06 (performance strategy), AM-05 (attendance migration), DM-02 (exports), DM-03 (backups), IO-04 (observability), CI fix (ROLLBACK_NOTES + TLS 1.2).
- Ray fixed 3 CI root causes: 16 migration ROLLBACK_NOTES blocks, TLS security (minimum TLSv1_2), removed redundant test definitions. 210 tests passing.
- Venkman submitted RC-01 (report cards with ReportLab PDF generation), UX-03 (unified search API), ESLint 9.x pin decision.
- Security triage: #22 (Insecure TLS, backend/services/health.py) → Ray; #23-25 (redundant assignments, backend/tests/contracts.py) → Winston.
- All 14 inbox decisions merged to active registry; clear execution path for post-MVP production features.

### Frontend Dependency Review Cycle (2026-05-09T12:44:00Z)
- Reviewed 5 frontend dependency PRs (#17–21) for version compatibility and migration impact
- Auto-merge enabled on #20 (@types/node patch bump — safe Node.js types update)
- Closed #17–18 (React 19.x major version): marked for planned React migration sprint; requires component API updates and hook changes
- Closed #19 (React Router v7 major): marked for routing migration; API breaking changes require route definition rework
- Closed #21 (Tailwind CSS v4 major): marked for styling migration; config and utility class changes need review
- **Outcome:** Frontend dependency stability maintained; 3 major version upgrades queued for dedicated migration planning; patch auto-merge policy working as designed

### Teacher documentation (2026-05-09T13:37:25.539-05:00)
- Created the comprehensive Parent/Teacher User Guide at `docs/teacher-guide.md`.
