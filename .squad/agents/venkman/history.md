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
