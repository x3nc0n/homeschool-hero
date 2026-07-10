---
target: frontend/src/pages/ReviewQueuePage.tsx
total_score: 23
p0_count: 0
p1_count: 3
timestamp: 2026-07-10T19-36-59Z
slug: frontend-src-pages-reviewqueuepage-tsx
---
⚠️ DEGRADED: single-context (no isolated sub-agent tool invoked; assessment A and B run inline)

---

## Design Health Score — ReviewQueuePage + ReviewDetailPage

| # | Heuristic | Score | Key Issue |
|---|-----------|-------|-----------|
| 1 | Visibility of System Status | 3 | Open item count, priority badges, busy spinner, loading states present |
| 2 | Match System / Real World | 2 | "AI confidence 0.87" unexplained; "needs_regrade" → "needs regrade" still technical |
| 3 | User Control and Freedom | 3 | Back to queue button, cancel actions, escape navigation |
| 4 | Consistency and Standards | 2 | Native unstyled checkboxes in table; filter bar has no active-filter pill/chip feedback |
| 5 | Error Prevention | 2 | No confirm dialog on bulk approve (irreversible); no confirm on reject |
| 6 | Recognition Rather Than Recall | 2 | Active filters invisible; AI confidence score unlabeled as to meaning |
| 7 | Flexibility and Efficiency | 3 | Bulk approve, bulk assign, search, 5 filter dropdowns |
| 8 | Aesthetic and Minimalist Design | 2 | ReviewDetailPage decision card has 7 fields at equal weight; approve action is not visually primary |
| 9 | Error Recovery | 3 | ErrorState present, error inline on save failures |
| 10 | Help and Documentation | 1 | No explanation of AI confidence; no reviewer guidance for parents new to grading workflow |
| **Total** | | **23/40** | **Acceptable — significant improvements needed** |

---

## Anti-Patterns Verdict

**LLM assessment**: ReviewQueuePage is functional but dense. The 5-filter-dropdown row in a `md:grid-cols-5` layout looks like a data management tool, not a parent's grading inbox. ReviewDetailPage has the right information architecture (image + OCR side by side, then decision form) but the decision form buries the primary action ("Approve") behind 5 fields the reviewer may never fill. No AI confidence explanation means a critical piece of information is invisible to the parent-reviewer.

**Deterministic scan**: 0 findings.

---

## Overall Impression

The review workflow has the right bones: the image + OCR split view in ReviewDetailPage is genuinely the correct design for this task. The problems are in the decision form density and the filter bar's lack of active-state feedback. A parent approving a straightforward math test shouldn't have to navigate past "Override reason", "Reject reason / resubmission note", and "Assign reviewer" just to click Approve.

## What's Working

1. **Submission image + OCR side by side** — correct information architecture for a human review task. Parent can compare handwritten work to transcribed text to AI suggestion in one view.
2. **Bulk actions** — bulk approve and bulk assign are the right power-user affordances for a parent managing a queue of 10+ items.
3. **Priority-first sort** — urgent items surface first by default without requiring the parent to configure it.

## Priority Issues

**[P1] No active filter state feedback — filters are invisible once applied**
- **What**: The 5 filter dropdowns (`status`, `priority`, `student`, `subject`, search) all show their selected value, but there's no count of active filters, no pill chips, and no "clear all filters" control.
- **Why it matters**: A parent who filtered to "priority=urgent, student=Alice" then steps away will return to a seemingly empty queue with no indication why. The filter state is invisible at a glance.
- **Fix**: Add a filter summary chip row below the filter bar (e.g., "Urgent · Alice · Clear all") that shows active non-default filters. Show the filtered count ("Showing 3 of 12") next to the queue count.
- **Suggested command**: `/impeccable clarify frontend/src/pages/ReviewQueuePage.tsx`

**[P1] ReviewDetailPage decision form buries the primary action**
- **What**: The Decision card has 7 form fields stacked vertically at equal visual weight: Final score, AI confidence (read-only), AI feedback, Reviewer notes, Override reason, Reject reason, Assign reviewer — then 3 buttons (Approve/save, Re-grade, Reject).
- **Why it matters**: A parent reviewing a routine assignment (score looks right, approve it) has to visually scan past 5 fields that are only relevant for exceptional cases. The cognitive load for the 80% case (just approve it) is the same as the 20% case (override and annotate). P1 because it will cause parents to hesitate or leave review items unactioned.
- **Fix**: Show only Final score + a single "Notes" field by default. Reveal "Override reason", "Reject reason", and "Assign reviewer" behind a "More options ▸" disclosure. Move the 3 action buttons to the top of the Decision card (primary action first).
- **Suggested command**: `/impeccable distill frontend/src/pages/ReviewDetailPage.tsx`

**[P1] AI confidence score is undefined for parent-reviewers**
- **What**: "AI confidence" displays as `0.87` with no explanation of what it means, what range is acceptable, or what action to take at different confidence levels.
- **Why it matters**: The confidence score is the most important signal for whether a parent needs to scrutinize a grade or can safely approve it — but it's presented as a raw float with no context, label, or guidance.
- **Fix**: Replace the raw float with a labeled band: "High confidence (0.87)" with a brief inline note "AI grades above 0.80 are usually reliable — spot check the score before approving." At confidence < 0.6, surface a caution label "Low confidence — review carefully."
- **Suggested command**: `/impeccable clarify frontend/src/pages/ReviewDetailPage.tsx`

**[P2] No confirmation on bulk approve or reject**
- **What**: `runBulkApprove` fires immediately on button click with no confirmation dialog. Approving 15 items at once is not easily reversible.
- **Why it matters**: Accidental mass-approval of incorrectly AI-graded work could affect a student's gradebook. Once approved, grades are finalized.
- **Fix**: Show a brief confirmation summary before bulk approve: "Approve 15 items for Alice (Math), Bob (Science)? This will finalize these grades." Simple confirm/cancel.
- **Suggested command**: `/impeccable harden frontend/src/pages/ReviewQueuePage.tsx`

## Persona Red Flags

**Jordan (parent new to reviewing AI grades)**: Opens ReviewDetailPage for the first time. Sees submission image (good). Then a wall of form fields. "Final score" is pre-filled with AI's suggestion. Doesn't know whether to change it or leave it. "AI confidence 0.87" — no idea if this is good or bad. Doesn't fill in "Override reason" (doesn't know if required). Clicks "Approve / save" nervously hoping it did the right thing. No confirmation that the grade was saved to the gradebook.

**Alex (experienced parent processing 20 reviews)**: Wants to bulk approve all items with confidence > 0.80. Can't filter by confidence score — only status, priority, student, subject. Has to open each one individually. Frustrated.

## Minor Observations
- `<input type="checkbox">` in the table is unstyled native HTML — renders differently across browsers and doesn't match the shadcn component vocabulary. Replace with Radix Checkbox.
- "Review queue is clear" empty state (used when `queue.length === 0`) blocks the entire page including the filter controls — a parent who just cleared the queue can't see that their filters may have hidden remaining items.
- ReviewDetailPage has no "Next item in queue" navigation — a parent reviewing 10 items must click "Back to queue", find the next item, click Open, repeat. High friction for a batch review task.

## Questions to Consider
- What if the primary Review Queue page was an "inbox" view — card-per-item with swipe-to-approve on mobile — rather than a data table with 5 filter dropdowns?
- Should "AI confidence" be surfaced as a visual indicator (traffic-light icon) in the queue table, so parents can triage without opening each item?
