# Venkman — History

## Learnings

(See history-archive.md for earlier entries prior to 2026-06-09)

- 2026-06-09T10:01:15-05:00 — XSS prevention pattern: CodeQL `js/xss-through-dom` tracks taint through React state — a sanitization check inside an event handler is NOT visible to the taint analysis at the render site. Fix: derive a `safePreviewUrl` computed value at render time that explicitly validates the URL scheme (`startsWith('blob:')`) before it reaches `src`/`data` HTML attributes. This pattern applies to any tainted value that flows through state into an HTML attribute sink — always add the sanitization guard at the render callsite, not just in the setter.

- 2026-05-18T16:38:51.741-05:00 — ESLint 10 + `@eslint/js` 10 work with the existing flat config in `frontend/eslint.config.js` unchanged, but `eslint-plugin-jsx-a11y@6.10.2` still advertises peer support only through ESLint 9. Added `frontend/.npmrc` with `legacy-peer-deps=true` so plain `npm install` succeeds while keeping the accessibility plugin enabled; `cd frontend && npm run lint && npm run build` both pass on ESLint 10.

- 2026-06-12T17:18:11.955-05:00 — School year setup now uses a dedicated wizard component in `frontend/src/components/features/SchoolYearSetupWizard.tsx`, with date/preset generation in `frontend/src/lib/schoolYearWizard.ts`; `frontend/src/pages/CalendarPage.tsx` keeps the post-create editing surface so parents can fine-tune terms and holiday dates after the guided flow.

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
