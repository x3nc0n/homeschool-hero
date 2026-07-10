---
target: frontend/src/pages/DashboardPage.tsx
total_score: 24
p0_count: 0
p1_count: 2
timestamp: 2026-07-10T19-36-59Z
slug: frontend-src-pages-dashboardpage-tsx
---
⚠️ DEGRADED: single-context (no isolated sub-agent tool invoked; assessment A and B run inline)

---

## Design Health Score — DashboardPage

| # | Heuristic | Score | Key Issue |
|---|-----------|-------|-----------|
| 1 | Visibility of System Status | 3 | Updated-at timestamp, refresh button, loading/error states all present |
| 2 | Match System / Real World | 3 | Plain language mostly; "pacing" and "compliance" may need explanation for new parents |
| 3 | User Control and Freedom | 3 | Collapsible widgets, pull-to-refresh, refresh button |
| 4 | Consistency and Standards | 2 | Student summary uses hero-metric grid pattern; quick actions are visually equal to each other |
| 5 | Error Prevention | 2 | No onboarding path; new parents see a fully expanded wall of widgets with no guidance |
| 6 | Recognition Rather Than Recall | 3 | Labels visible on all elements; status meanings communicated via badges |
| 7 | Flexibility and Efficiency | 2 | No keyboard shortcuts for dashboard actions; no persistent widget state (collapses reset on reload) |
| 8 | Aesthetic and Minimalist Design | 2 | 7 widgets all open by default; hero-metric 2×2 in student summary cards; system status visible to non-operators |
| 9 | Error Recovery | 3 | ErrorState component present; retry buttons on widget and page level |
| 10 | Help and Documentation | 1 | No tooltips; no onboarding; "pacing alerts" and "compliance warnings" undefined for new parents |
| **Total** | | **24/40** | **Acceptable — significant improvements needed** |

---

## Anti-Patterns Verdict

**LLM assessment**: The dashboard is the clearest example of the "identical card grid" anti-pattern in this app. Every data point — a schedule block, an assignment, a grade, an attendance entry, a pacing alert — renders as the same `rounded-lg border p-3` row inside the same `Card`. There is no visual hierarchy distinguishing urgent information (a compliance warning) from ambient information (today's schedule). The student summary cards use the hero-metric template (big number, small uppercase label, 2×2 grid) which the Impeccable rules flag explicitly.

**Deterministic scan**: 0 findings — no absolute-ban patterns in markup.

---

## Overall Impression

The dashboard has the right information architecture — student summaries, upcoming work, recent grades, and alerts are all the right things to show. The problem is everything is shown at equal weight, all at once, with no visual priority. A parent arriving for their morning check-in should see "3 things need your attention today" before they see "here are 22 items in 7 widgets."

## What's Working

1. **Collapsible widgets** — the hide/show toggle is the right instinct; it lets the parent customize density.
2. **Student summary cards** — the right four data points (GPA, attendance, due count, pacing) in one glance. Structure is correct even if execution needs refinement.
3. **Pull-to-refresh** — mobile-appropriate interaction for a parent checking the dashboard on their phone.

## Priority Issues

**[P1] Hero-metric pattern in student summary cards**
- **What**: Each student summary card has a 2×2 grid of `rounded-lg border p-3` boxes — GPA, Attendance, Due soon, Pacing — with `text-xs uppercase text-muted-foreground` labels above `text-lg font-semibold` values.
- **Why it matters**: This is the "hero-metric template" anti-pattern (big number, small label, grid) flagged in the Impeccable skill. It reads as "SaaS analytics dashboard" rather than "parent gradebook." The identical box styling means all four metrics feel equally important.
- **Fix**: Replace the 2×2 box grid with an inline stat row (4 values in a single flex row with clear separators), reserving the bordered box treatment for the single most important alert on this student. Give pacing status a distinct visual treatment (colored left edge or icon) when status is "behind" — that's the only metric that needs an urgent signal.
- **Suggested command**: `/impeccable layout frontend/src/pages/DashboardPage.tsx`

**[P1] No visual priority differentiation — everything is equally loud**
- **What**: Compliance warnings (critical) render with the same card/border style as "today's schedule" (informational). Urgent pacing alerts use the same `text-xs text-destructive` inline text as a timestamp note.
- **Why it matters**: A parent who has a compliance deadline this week and two pacing alerts shouldn't have to skim through 7 widgets to find them. The page provides no signal about where the most urgent attention is needed.
- **Fix**: Add a top-of-page alert band that surfaces P0 items (overdue compliance items, urgent pacing alerts) before the widget grid. Color the alert band destructive/amber; keep the widget grid neutral.
- **Suggested command**: `/impeccable colorize frontend/src/pages/DashboardPage.tsx`

**[P2] Quick actions are visually indistinguishable from secondary actions**
- **What**: "Add attendance", "Create assignment", "Record grade" are three `Button variant="outline"` controls at equal weight. No primary action is indicated.
- **Why it matters**: A parent who wants to log this morning's attendance doesn't have a visual signal that "Add attendance" is the thing to do — all three buttons look equivalent.
- **Fix**: Identify the single most common first daily action (likely "Add attendance") and make it the primary button (`variant="default"`). Demote the others to outline or secondary.
- **Suggested command**: `/impeccable clarify frontend/src/pages/DashboardPage.tsx`

**[P2] System status widget shown to parents**
- **What**: The "System status" widget (healthy/degraded services, service names) is visible to all parent/tutor roles.
- **Why it matters**: Service health data is operator-level information. A parent seeing "Database: degraded" has no context for what that means and no action to take.
- **Fix**: Gate this widget behind an admin-only capability check, or replace it with a parent-legible summary ("Some features may be slower than usual") when services are degraded.
- **Suggested command**: `/impeccable distill frontend/src/pages/DashboardPage.tsx`

## Persona Red Flags

**Jordan (first-time parent)**: Opens dashboard for the first time. Sees "Family dashboard" header, then an orange "Quick actions" card, then "Student summary" (0 students — empty state), then 7 collapsed/expanded widgets. Has no idea what "pacing" means or what "compliance warnings" are. No tooltip, no help link, no onboarding prompt. Will click "Add attendance" hoping it explains what to do next.

**Sam (parent with 3 students, weekly check-in)**: Scrolls through all 7 widgets looking for anything flagged. Compliance warning is buried in the third section of the right column. Wishes there were a "show only alerts" view.

## Minor Observations
- Widget collapse state resets on every page reload — a parent who hides "System status" every session will keep seeing it on return.
- "Updated {timestamp}" in the header is `hidden md:block` — mobile users have no indication of when data was last refreshed beyond the refresh button.
- `formatPercent` returns `'—'` for null attendance — visually indistinct from a zero. Should be "Not recorded" or similar.

## Questions to Consider
- Should the default dashboard view for a new parent be an onboarding checklist ("Set up your first student", "Create your first assignment") rather than an empty 7-widget grid?
- What if pacing alerts and compliance warnings were promoted to the very top of the page with a red/amber header band, and everything else was below the fold?
