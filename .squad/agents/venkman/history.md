# Venkman — History

## Learnings

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
