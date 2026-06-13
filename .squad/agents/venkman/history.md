# Venkman — History

## Learnings

(See history-archive.md for earlier entries prior to 2026-06-09)

- 2026-06-12T17:48:45.564-05:00 — react-router v7 audit: the frontend is still on the declarative router stack only (`BrowserRouter` in `src/main.tsx`, `Routes`/`Route`/`Navigate` in `src/App.tsx`, `NavLink` in `AppShell`, plus `Link`, `useNavigate`, `useParams`, `useLocation`, and `useSearchParams` across 18 route-aware files). We do **not** use `createBrowserRouter`, `RouterProvider`, loaders/actions, `useLoaderData`, or splat-route migration patterns, so v6→v7 was a compatibility bump with no source changes required. `react-router-dom@7.17.0` built and linted cleanly; the only dev-runtime crash reproduced on both v6 and v7 was the existing `AuthProvider` undefined-role error, so the migration decision was to merge the dependency bump after rebasing it on top of the shadcn lockfile update.

- 2026-06-09T10:01:15-05:00 — XSS prevention pattern: CodeQL `js/xss-through-dom` tracks taint through React state — a sanitization check inside an event handler is NOT visible to the taint analysis at the render site. Fix: derive a `safePreviewUrl` computed value at render time that explicitly validates the URL scheme (`startsWith('blob:')`) before it reaches `src`/`data` HTML attributes. This pattern applies to any tainted value that flows through state into an HTML attribute sink — always add the sanitization guard at the render callsite, not just in the setter.

- 2026-05-18T16:38:51.741-05:00 — ESLint 10 + `@eslint/js` 10 work with the existing flat config in `frontend/eslint.config.js` unchanged, but `eslint-plugin-jsx-a11y@6.10.2` still advertises peer support only through ESLint 9. Added `frontend/.npmrc` with `legacy-peer-deps=true` so plain `npm install` succeeds while keeping the accessibility plugin enabled; `cd frontend && npm run lint && npm run build` both pass on ESLint 10.

- 2026-06-12T17:18:11.955-05:00 — School year setup now uses a dedicated wizard component in `frontend/src/components/features/SchoolYearSetupWizard.tsx`, with date/preset generation in `frontend/src/lib/schoolYearWizard.ts`; `frontend/src/pages/CalendarPage.tsx` keeps the post-create editing surface so parents can fine-tune terms and holiday dates after the guided flow.

- 2026-06-12T18:37:58.792-05:00 — Curriculum Phase 2-3 extends the Phase 1 import surface instead of adding new routes: `CurriculumImportLibraryPage` now owns `My Library` + `Browse Sources` tabs, `CurriculumImportWizard` handles both standard JSON and AI-assisted document flows, and `src/lib/api.ts` keeps dev-only fallback support for `/curriculum/sources` plus `/curriculum/ai-import*` so the UI stays testable before backend endpoints fully land.

## Recent Activity

### 2026-06-09 Frontend Security Hardening
- Fixed DOM-based XSS issues (#167, #168) in FileUpload.tsx
- Applied render-site sanitization pattern: explicit safety checks at JSX callsite, not just event handlers
- CodeQL taint analysis now verifies safety through React state flow
- Committed b3ef0b5 with XSS pattern guardrail for future maintainers

### Egon Issue Triage Session — 2026-06-12

**Status:** 21 issues closed, 2 features tagged for backlog

Egon completed comprehensive GitHub issue triage. All security findings have been addressed:
- **14 new security scan issues** (#203–#218) closed — already fixed by PR #219
- **7 older duplicates** (#186–#192) closed

**Your assignment:** No new security assignments at this time. Venkman is clear from the triage.

**Next:** Feature backlog (#164, #165) is tagged and ready for grooming when capacity is available.
- 2026-06-12T17:48:45.564-05:00 — Curriculum import Phase 1 now uses a dedicated `CurriculumImportLibraryPage` inside `CurriculumHubPage`, with reusable `CurriculumImportWizard` and `CurriculumImportTree` components plus a new `/curriculum/:curriculumId` detail route. The UI follows the staged School Year Wizard pattern (validate → preview → review → success), uses new curriculum import API helpers in `src/lib/api.ts`, and assumes Ray may return either the issue contract’s legacy top-level fields (`grade_levels`, `estimated_hours`) or the newer metadata-backed schema — `src/lib/curriculumImport.ts` normalizes both, while `src/lib/curriculumImportMock.ts` provides a dev-only localStorage fallback so the flow stays testable before the backend endpoints are fully live.

- 2026-06-12T23:15:42Z — **Curriculum UI Phase 1 COMPLETE.** Delivered `/curriculum` library hub (existing + new Library tab as default), `/curriculum/:curriculumId` detail view with tree hierarchy, 4-step import wizard flow, and typed API helpers with dev-mode localStorage mock fallback. Full build + lint validation passing. Ready for backend integration testing once Ray's PR #229 merges. No code changes needed for react-router v7 compatibility — all frontend routes remain on the declarative API stack.

## Scribe Session (2026-06-12T19:04:57.253-05:00)
- Archived old decisions (before 2026-06-05)
- Source browser UI work: PR #240 (merged), PR #244 (XSS fix)
- Releases: v0.12.0 (Import), v0.13.0 (Enterprise Security), v0.14.0 (Sources+AI), v0.14.1 (Hardening)
