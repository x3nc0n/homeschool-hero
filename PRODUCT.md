# Product

## Register

product

## Users

**Primary — Parent-Teacher (owner / co-parent / tutor)**
Home-educating parent who wears both teacher and admin hats. Mildly IT-literate at best. Uses the app at a desktop or laptop during the school day. Logs attendance, creates assignments, reviews AI-graded work, and keeps an eye on compliance and pacing. Cannot tolerate complex tooling; needs the interface to stay out of the way and make tasks obvious.

**Secondary — Student**
K–12 learner. Primarily uses the app on a phone or tablet to photograph and upload completed paper assignments. Has a narrow, focused surface: upload work, check grades, view today's schedule. Needs frictionless mobile capture.

**Tertiary — Tutor / Co-parent**
Shares grading and curriculum duties. Mirror of primary except no ownership privileges.

## Product Purpose

Homeschool Hero is a self-hosted homeschool learning, grading, and records management platform for families. It replaces paper gradebooks, compliance binders, and ad-hoc file folders with a single authenticated workspace. Core workflows: assignment creation and tracking, photo/scan upload of paper student work, automated OCR + AI grading with mandatory human review, quiz/test delivery, gradebook and report card generation, attendance logging, and state compliance report exports.

Success looks like: a non-technical parent can run a complete school day — create an assignment, receive the student's photo upload, approve the AI grade, and log attendance — without consulting a manual or contacting support.

## Brand Personality

Trustworthy. Calm. Capable.

The app is a *tool*, not a toy. It should project quiet competence: a parent-teacher should feel confident that their records are accurate, their children's progress is tracked, and the compliance burden is handled — without the interface being clinical or bureaucratic. Think a well-organized teacher's desk, not a hospital dashboard.

## Anti-references

- **Google Classroom / canvas-style "student portal" visual language** — overly colorful, banner-heavy, feels like it's made for kids; this app is primarily a *parent* tool.
- **Typical SaaS admin dashboards** (pure dark-mode enterprise analytics, dense KPI grids, hero-metric cards) — wrong register; parents are not ops managers.
- **Bland white-and-gray scaffolded CRUD apps** — the "AI made this in five minutes" look; every widget the same height, same card style, same muted palette. Not trustworthy.
- **Overly playful / pastel "edu-tech" aesthetic** — bubbly, rounded, emoji-heavy; undermines the legitimacy of academic records.

## Design Principles

1. **The task is the teacher.** Every screen should be oriented around one specific job the user is doing right now. Avoid multi-purpose screens that force the user to choose before they've even started.
2. **Earned confidence, not assumed familiarity.** Labels, status indicators, and feedback should speak plainly. Parents should never need to decode a status code, abbreviation, or AI-generated percentage without context.
3. **Mobile-first for students, desktop-first for parents.** The upload flow must work one-handed on a phone. The review/gradebook/compliance surfaces can lean into desktop density.
4. **Records are permanent.** Any action that finalizes, submits, or deletes work should surface appropriate friction — a clear label, a summary of what will happen, and a confirm step. Accidental finalization is a P0 failure.
5. **Progressive disclosure over information walls.** Default views should show the 20% of data the parent needs 80% of the time. Everything else lives one tap deeper.

## Accessibility & Inclusion

WCAG 2.1 AA minimum. Focus indicators and keyboard navigation are implemented. High-contrast theme available. Mobile-safe touch targets (44px+). Reduced-motion respecting transitions. i18next i18n scaffolded (en default). No known color-blindness testing gaps; should be addressed in the overhaul.
