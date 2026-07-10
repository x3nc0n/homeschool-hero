---
target: frontend/src/pages/GradebookPage.tsx
total_score: 25
p0_count: 0
p1_count: 2
timestamp: 2026-07-10T19-36-59Z
slug: frontend-src-pages-gradebookpage-tsx
---
⚠️ DEGRADED: single-context (no isolated sub-agent tool invoked; assessment A and B run inline)

---

## Design Health Score — GradebookPage (tab shell + GradesPage)

| # | Heuristic | Score | Key Issue |
|---|-----------|-------|-----------|
| 1 | Visibility of System Status | 3 | Tab state synced to URL; loading/error states in each tab's content |
| 2 | Match System / Real World | 2 | "Review Queue" as a tab inside "Gradebook" is confusing placement; grades ≠ review queue conceptually |
| 3 | User Control and Freedom | 3 | Tab switching, URL-backed state, back navigation |
| 4 | Consistency and Standards | 2 | `text-3xl font-bold` heading — only 3xl in the app; breaks the `text-2xl` page heading convention |
| 5 | Error Prevention | 3 | Tab state validated against available tabs; invalid tab falls back gracefully |
| 6 | Recognition Rather Than Recall | 2 | "Review Queue" appears as both a sidebar nav item and a tab here — duplicate entry with different context |
| 7 | Flexibility and Efficiency | 3 | URL-backed tab state allows direct linking; keyboard tab navigation |
| 8 | Aesthetic and Minimalist Design | 3 | Page itself is minimal; the tab shell is lean |
| 9 | Error Recovery | 3 | Tab fallback, error states in child pages |
| 10 | Help and Documentation | 1 | No explanation of what the gradebook contains vs review queue |
| **Total** | | **25/40** | **Acceptable — significant improvements needed** |

---

## Anti-Patterns Verdict

**LLM assessment**: The GradebookPage shell itself is minimal (a tab wrapper). The two issues here are primarily architectural: (1) Review Queue is conceptually a grading workflow tool, not a grades view — mixing them in a "Gradebook" tab misleads parents about what the Gradebook is for; (2) the `text-3xl font-bold` heading is an outlier in the app's typography system. The detector found no absolute bans.

**Deterministic scan**: 0 findings.

---

## Overall Impression

The gradebook page itself is clean, but it's doing double duty as a tab host for both grade viewing and review queue management — two distinct workflows that benefit from separate contexts. The 3xl heading is a minor but real visual inconsistency that breaks page rhythm.

## What's Working

1. **URL-synced tab state** — navigating directly to `/grades?tab=review` lands on the right tab; important for deep linking from the dashboard's "go to review" action.
2. **Lean shell** — the wrapper adds no visual noise beyond the tabs themselves.
3. **Capability-gated tabs** — review tab only appears for users with `canManageGrading`, correctly scoped.

## Priority Issues

**[P1] Review Queue tab inside Gradebook creates conceptual confusion**
- **What**: "Gradebook" in the sidebar routes to a page with two tabs: "Grades" and "Review Queue." Review Queue is also a direct sidebar nav item under Schoolwork. A parent can reach the review queue from two different paths.
- **Why it matters**: Duplicate entry points with different visual contexts (tab vs. sidebar item) teach the parent that navigation is unpredictable. "Is the Review Queue under Schoolwork or under Gradebook?" is an unnecessary question.
- **Fix**: Remove the Review Queue tab from Gradebook. The Review Queue is its own workflow (inbox-style) and belongs at its own top-level URL. The Gradebook should be strictly grades: grade entry, grade history, report card preview.
- **Suggested command**: `/impeccable distill frontend/src/pages/GradebookPage.tsx`

**[P1] `text-3xl font-bold` heading breaks typography system**
- **What**: `<h1 className="text-3xl font-bold">Gradebook</h1>` — 1.875rem/30px bold. Every other page heading in the app uses `text-2xl` (1.5rem) or `text-xl` (1.25rem). This is the only 3xl heading.
- **Why it matters**: One oversized heading breaks the visual rhythm and implies a hierarchy that doesn't exist (Gradebook is not more important than other pages). It also conflicts with the app's established heading scale.
- **Fix**: Change to `text-2xl font-semibold` to match the convention used in ReviewDetailPage and other page headers.
- **Suggested command**: `/impeccable typeset frontend/src/pages/GradebookPage.tsx`

**[P2] GradesPage content (actual grade visualization) not reviewed in this pass**
- **What**: GradebookPage wraps `<GradesPage />` which is a separate component not reviewed here.
- **Why it matters**: The actual grade visualization — the core product value of the Gradebook — lives in a child component that may have its own issues.
- **Fix**: Schedule a separate critique of `frontend/src/pages/GradesPage.tsx` as part of the overhaul backlog.
- **Suggested command**: `/impeccable critique frontend/src/pages/GradesPage.tsx`

## Persona Red Flags

**Jordan (parent checking child's grades for the first time)**: Clicks "Gradebook" in the sidebar. Sees a page with "Gradebook" in large text and two tabs: "Grades" and "Review Queue." Clicks "Grades" — correct. But is confused why "Review Queue" is here when it's also in the left nav. Wonders if they're the same or different.

**Alex (parent power user)**: Prefers to keyboard-navigate. Tabs between the two page tabs using arrow keys (Radix Tabs supports this). The URL updates — good. The back button works — good. This surface is actually well-served for Alex.

## Minor Observations
- If `canManageGrading` is false, the user sees only the Grades tab and the TabsList with one item — single-tab TabsList looks odd (unnecessary chrome). Could be conditionally hidden when only one tab is available.
- The page doesn't render a description or subtitle to orient the parent beyond "Gradebook."

## Questions to Consider
- Should the Gradebook be reconceived as a "Progress" view — showing grade trends, subject averages, and report card status — rather than a list of individual grades mixed with a review workflow?
- What if the tab was removed and the Gradebook was strictly the grades view, with a prominent link to the Review Queue for teachers who need to approve grades?
