# Attendance Requirements by US State — Research Summary

**Author:** Egon (Lead)
**Date:** 2026-07-10
**Related issue:** #297 — Attendance overhaul: research state requirements, simplify to minimums
**Status:** Research complete; scope decision recorded

> ⚠️ **Legal disclaimer:** This document is a software design guide, not legal advice. Requirements
> summarized here are based on publicly available information and known to be accurate as of mid-2026,
> but laws change. Every homeschooling family is responsible for verifying the current rules in their
> own state or jurisdiction. When in doubt, consult your state's homeschool organization or an attorney.

---

## 1. What the current implementation tracks

The existing `AttendanceRecord` model stores:

| Field | Notes |
|---|---|
| `status` | `present \| absent \| tardy \| excused` |
| `check_in_time` / `check_out_time` | Clock times for session start/end |
| `instructional_hours` | Computed or manually entered decimal hours |
| `notes` | Free text |
| `AttendanceExcuse` relation | Separate excuse object with document upload and approval workflow |

The frontend exposes all four statuses, the check-in/check-out time pickers, an hours field, and an excuse upload flow. This is a reasonable model for a public school but creates unnecessary overhead for a homeschool family in most US states.

---

## 2. State-by-state survey

### Methodology

Requirements were compiled from the HSLDA state-law map, WorldPopulationReview homeschool law
summaries, and state DOE resources. States that offer multiple homeschool options (e.g., "umbrella
school" vs. "notice of intent") may have varying requirements per option; the most permissive common
option is noted here, since self-hosted families are likely using that path.

### Bucket definitions

| Bucket | Description |
|---|---|
| **A — None** | No attendance requirement of any kind for homeschoolers |
| **B — Days only** | Minimum instructional *days* (typically 180); no hours tracking required |
| **C — Hours only** | Minimum instructional *hours* per year; day count not separately required |
| **D — Days + Hours** | Both day count and minimum daily or annual hours are specified |
| **E — Notification / recordkeeping only** | No day/hour count, but families must file a notice, maintain a portfolio, or submit to assessment |

### State table

| State | Bucket | Days | Hours | Notes |
|---|---|---|---|---|
| Alabama | B | 180 | — | Records recommended |
| Alaska | A | — | — | No attendance requirement |
| Arizona | A | — | — | No attendance requirement |
| Arkansas | A | — | — | Notice of intent required; no day/hour count |
| California | E | — | — | Operates as private school; records kept internally |
| Colorado | D | 172 | ~4 hrs/day | Progress evaluation required |
| Connecticut | B | 180 | — | Equivalent instruction standard |
| Delaware | A | — | — | No attendance requirement |
| Florida | A | — | — | Portfolio/evaluation OR standardized testing |
| Georgia | D | 180 | 4.5 hrs/day | Annual progress report required |
| Hawaii | E | — | — | Must track hours; no minimum |
| Idaho | A | — | — | No attendance requirement |
| Illinois | A | — | — | Equivalent instruction; no day/hour count |
| Indiana | B | 180 | — | Notice of intent required |
| Iowa | B | 148 | — | Portfolio option has separate hour rules |
| Kansas | D | 186 | 6 hrs/day | One of the strictest |
| Kentucky | B | 185 | — | Annual notice required |
| Louisiana | B | 180 | — | Annual enrollment required |
| Maine | B | 175 | — | Approval or assessment required |
| Maryland | E | — | — | Portfolio/assessment; no day/hour count |
| Massachusetts | E | — | — | Must seek approval; "equivalent instruction" |
| Michigan | A | — | — | No attendance requirement |
| Minnesota | A | — | — | Annual assessment required |
| Mississippi | B | 180 | — | Notice of intent required |
| Missouri | C | — | 1,000 hrs/yr (600 core) | Unique hours-only model |
| Montana | C | — | 360–1,080 hrs/yr (by grade) | Hours scale with grade band |
| Nebraska | C | — | 1,032–1,080 hrs/yr | Elementary vs. secondary |
| Nevada | A | — | — | Annual notice only |
| New Hampshire | A | — | — | Notification required; no day/hour count |
| New Jersey | A | — | — | No attendance requirement |
| New Mexico | D | 180 | 990–1,080 hrs/yr | Varies K–6 vs. 7–12 |
| New York | B | 180 | 900–990 hrs/yr | Detailed annual IHIP and quarterly reports |
| North Carolina | B | ~180 (9 months) | — | Annual testing required |
| North Dakota | D | 175 | 4 hrs/day | One of the stricter northern states |
| Ohio | C | — | 900 hrs/yr | No day minimum |
| Oklahoma | B | 180 (recommended) | — | Voluntary; no enforcement mechanism |
| Oregon | A | — | — | Annual assessment for 3rd grade+ |
| Pennsylvania | B | 180 | 900–990 hrs/yr | Most detailed recordkeeping in the US; affidavit required |
| Rhode Island | D | 180 | 5.5 hrs/day | Approval required |
| South Carolina | D | 180 | 4.5 hrs/day | Membership in association required |
| South Dakota | C | — | 437–962 hrs/yr (by grade) | Hours scale with grade band |
| Tennessee | D | 180 | 4 hrs/day | Home school association membership required |
| Texas | A | — | — | No attendance requirement |
| Utah | A | — | — | No attendance requirement |
| Vermont | A | — | — | Annual enrollment; no day/hour count |
| Virginia | B | 180 | — | Annual notice + evidence of progress |
| Washington | D | 180 | 1,000 hrs/yr | Annual assessment required |
| West Virginia | B | ~180 (county equiv.) | — | Approval from county superintendent |
| Wisconsin | C | — | 875 hrs/yr | No day minimum |
| Wyoming | A | — | — | No attendance requirement |

### Bucket summary

| Bucket | State count | Examples |
|---|---|---|
| A — None | ~20 states | TX, AK, FL, IL, NJ, OR, MI, ID, NV, AZ |
| B — Days only | ~16 states | AL, CT, IN, KY, LA, MS, NC, PA, VA, NY |
| C — Hours only | ~6 states | MO, MT, NE, OH, SD, WI |
| D — Days + Hours | ~7 states | CO, GA, KS, NM, ND, RI, SC, TN, WA |
| E — Notification/portfolio | ~5 states | CA, HI, MA, MD |

### Key observations

1. **Roughly 40% of states (Bucket A) have zero attendance requirements.** A family in Texas or
   Florida legally owes the state nothing in terms of attendance records.

2. **"Tardy" is never a legal concept in homeschool law** in any US state. It is a school
   administrative concept, not a statutory one. No state requires homeschool families to log tardiness.

3. **Hours are only legally relevant in ~13 states** (Buckets C and D). Even in those states, families
   track *total instructional hours*, not clock check-in/check-out times. Check-in/out time pickers
   add friction with no legal basis in any state.

4. **Excuses and excuse workflows** are a public-school concept. No US state requires homeschoolers to
   formally "excuse" an absent day with a document upload or approval workflow.

5. **180 days is the most common threshold** in day-counting states (Bucket B), but families rarely
   need granular per-day logging beyond a simple boolean "did school happen today?"

---

## 3. Proposed simplified attendance model

### Design principles

- **Default to the legal minimum useful case:** mark a calendar day as an instructional day or not.
- **Layer in optionals** only for families in states that legally require them.
- **Never surface school-administrative concepts** (tardy, excuse approval workflow) by default.
- **Self-hosted first:** families who don't enable a state profile get the simplest possible UI.

### Core data model (new)

```
AttendanceRecord
├── id
├── family_id
├── student_id
├── date                   -- the instructional day
├── is_instructional_day   -- boolean (replaces status enum)
├── notes                  -- optional free text
└── (timestamps)
```

`instructional_hours` becomes **optional** and is stored separately (or on the same record as a
nullable column) — only shown when a state profile requires hours.

### What gets removed / demoted

| Current field | Proposed fate |
|---|---|
| `status: tardy` | **Removed.** No legal basis for homeschool. |
| `status: excused` | **Removed.** School-admin concept; families can note in `notes`. |
| `check_in_time` / `check_out_time` | **Removed from default UI.** No state requires clock times; only hours matter. |
| `AttendanceExcuse` relation (reason, document, approval) | **Removed.** Entire excuse sub-model dropped. |
| `instructional_hours` | **Optional.** Hidden unless the family has enabled a state profile that requires hours (Buckets C/D). |

### State requirement profiles (optional feature)

A lightweight `StateRequirementProfile` table (or JSONB config) would let a family select their state
and automatically set:

- `required_days` (null if not applicable)
- `required_hours` (null if not applicable)
- `show_hours_ui` (boolean derived from the above)

The app would then surface a progress bar: "142 / 180 instructional days" and optionally
"612 / 900 instructional hours" for the school year. Families in Bucket A see neither bar.

**These are defaults, not enforcement.** The family can always override. The app does not prevent
marking more or fewer days.

### AttendanceSummary simplification

The summary response drops `tardy` and `excused` counts. It becomes:

```
AttendanceSummary
├── student_id
├── school_year_id
├── instructional_days      -- days where is_instructional_day = true
├── non_instructional_days  -- days logged but is_instructional_day = false
├── total_hours             -- sum of instructional_hours (null if hours not tracked)
└── state_profile_progress  -- { required_days, days_remaining, required_hours, hours_remaining } | null
```

### Proposed UI changes

| Area | Change |
|---|---|
| Daily attendance entry | Single toggle per student: "Instructional day ✓/✗" + optional notes |
| Calendar view | Green = instructional day, gray = non-instructional, white = no record |
| Summary widget | Days count (+ hours if profile enabled). No tardy/excused rows. |
| School year progress | Optional progress-toward-minimum bar if state profile set |
| Family settings | "State" selector → auto-populates requirement profile |
| Excuse flow | **Removed entirely** |

---

## 4. Migration path

Because `tardy` and `excused` are existing enum values in the DB with potentially live records, the
migration plan must handle existing data gracefully:

- `tardy` records → convert to `present` (a tardy day is still an instructional day)
- `excused` records → convert to the `is_instructional_day = true` or `false` based on whether an
  excuse was associated (absent-with-excuse → non-instructional day; typically treated as absent in
  terms of instruction)
- `check_in_time` / `check_out_time` → drop columns (no data migration needed; values not legally
  meaningful)
- `AttendanceExcuse` table → drop after audit export (families should export before upgrade if they
  want to retain excuse documents)
- `instructional_hours` → retain column, make nullable, hide in UI unless state profile requires it

This is a **breaking schema migration** and warrants a release note + data export reminder.

---

## 5. Recommended follow-up implementation issues

The research gate (#297) clears when this document is accepted. Suggested decomposition:

| Issue | Title | Owner | Priority |
|---|---|---|---|
| A | Backend: simplify AttendanceRecord model (drop tardy/excused/check_in/excuse table) | Ray | P3 |
| B | Backend: add StateRequirementProfile config + per-family state setting | Ray | P3 |
| C | Backend: migration — convert tardy→present, excused→absent, drop excuse table | Ray | P3 |
| D | Frontend: redesign attendance UI (instructional-day toggle, remove excuse flow) | Venkman | P3 |
| E | Frontend: state profile progress bar (days/hours toward minimum) | Venkman | P4 |
| F | Docs: update teacher-guide and admin-guide for new attendance model | Any | P5 |

Issues A, C should be a single Ray PR (model + migration together). D should be Venkman's first
attendance PR. E depends on B and D.

---

## 6. Conclusion

The current attendance model is over-engineered for the homeschool use case. **Roughly 40% of US
homeschool families are in states with no attendance requirement at all.** The remaining states
primarily require a day count (180 days is the modal threshold); only ~13 states require hours, and
none require clock check-in/out, formal "tardy" logging, or a document-backed excuse workflow.

The proposed model defaults to the universal minimum (instructional-day boolean), surfaces hours only
for states that need them, and eliminates school-administrative overhead entirely. This reduces the
daily friction for the majority of families while remaining legally sufficient for all 50 states when
paired with an optional state profile.

> ⚠️ Families must verify current state law independently. This app is a tool, not a legal
> compliance system.
