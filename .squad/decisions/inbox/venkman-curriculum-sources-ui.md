# Venkman — Curriculum Sources + AI Import UI

- Date: 2026-06-12T18:37:58.792-05:00
- Issue: #165 Phases 2-3

## Decision
Keep the existing `/curriculum` hub and Phase 1 import wizard intact, then layer the new work inside them: `CurriculumImportLibraryPage` gets nested `My Library` / `Browse Sources` tabs, and `CurriculumImportWizard` gains a second import mode for AI-assisted document parsing.

## Why
- This preserves the Phase 1 manual JSON path without fragmenting the curriculum workspace into more routes.
- Reusing the existing preview tree keeps review/edit behavior consistent whether the draft came from manual JSON, an external source, or AI parsing.
- Frontend dev work can keep moving while Ray finalizes the backend because `src/lib/api.ts` and `src/lib/curriculumImportMock.ts` share the same fallback pattern for the new source-browser and AI-import endpoints.

## Contract notes
- The source browser expects `/api/curriculum/sources`, `/api/curriculum/sources/{source}/search?q=...`, and `/api/curriculum/sources/{source}/import/{item_id}` to return metadata that can be rendered as cards/results and imported directly into the existing curriculum library detail shape.
- The AI upload flow posts either multipart `file` data or a JSON `{ "url": "..." }` body to `/api/curriculum/ai-import`, then confirms with `/api/curriculum/ai-import/confirm` using `{ "draft": <curriculum document>, "source_url": <optional url> }`.
- Production AI import should stay gated behind `family.enabled_features.curriculum_ai_import` plus configured `ai_grading` and `ocr` capabilities; dev mode can fall back to the local mock flow when backend endpoints are not ready yet.
