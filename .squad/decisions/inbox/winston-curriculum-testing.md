# Winston decision — Curriculum import test follow-ups

- Date: 2026-06-12T17:48:45.564-05:00
- Scope: Issue #165 Phase 1 backend contract coverage

## Decisions needed

1. **Empty curriculum behavior**
   - Should `POST /api/curriculum/import` reject payloads with zero subjects (`422`) or allow draft/placeholder curricula (`201`)?
   - Current anticipatory spec assumes fail-closed, but this is still a product choice.

2. **Cross-family access semantics**
   - Existing family-scoped curriculum resources usually return `404` to avoid record leakage.
   - Requested issue coverage says `403` for “cannot access other user's curriculum”; team should choose one convention for the new `/api/curriculum/{id}` surface.

3. **Activation repeat behavior**
   - Need contract for second `POST /api/curriculum/{id}/activate`: idempotent `200`, conflict `409`, or another explicit status.
   - Tests currently expect “no duplicate assignments” regardless of chosen status.

4. **Activation calendar linkage**
   - Clarify whether activation always targets the active school year, a curriculum-owned school year, or an explicit request field.
   - This choice affects due-date assertions and “no school year configured” failure handling.

5. **Import size / concurrency guarantees**
   - Current contract test assumes a hard ceiling at `1000` lessons and flags concurrent imports as a future requirement.
   - Confirm the intended size threshold and whether imports must be transactionally isolated under concurrent requests.

## Why this matters

- The staged test suite already passes contract validation checks locally and skips missing API routes cleanly.
- Locking these decisions now will let Ray unskip/convert the pending API assertions without reworking the expected behavior later.
