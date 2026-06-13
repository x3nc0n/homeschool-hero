# Ray decision — Curriculum sources and AI import

- Date: 2026-06-12T18:37:58.792-05:00
- Scope: Issue #165 Phases 2 and 3 backend

## Decisions

1. Use a discoverable connector framework in `backend/services/curriculum_sources/` so source integrations stay isolated behind `search`, `fetch`, and `convert_to_standard_format` while the API only depends on the standard curriculum schema.
2. Ship three connectors now: OpenStax (live CMS JSON API), CK-12 (curated FlexBook catalog fallback because stable unauthenticated automation against ck12.org is currently blocked), and OER Commons (live connector gated by `OER_COMMONS_API_TOKEN`).
3. Keep AI import draft-first: `/api/curriculum/ai-import` extracts PDF/DOCX/TXT or URL text, sends it to an Azure/OpenAI-compatible chat-completions endpoint with tool-calling, and returns an unsaved `CurriculumImportDocument`; `/api/curriculum/ai-import/confirm` persists the reviewed draft through the same save path as manual/source imports.

## Rationale

- Reusing the Phase 1 import persistence path avoids new storage models and keeps activation behavior identical regardless of where a curriculum originated.
- OpenStax already exposes structured public JSON, CK-12 still matters to the roadmap even though their public surface is unstable for automation, and OER Commons is valuable enough to support once a token is available.
- Draft-first AI import reduces the risk of hallucinated structure being saved without a human review pass, while still giving the frontend a concrete preview payload to edit.
