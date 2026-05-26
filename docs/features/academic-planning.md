---
title: Academic Planning
description: How Homeschool Hero handles calendar setup, terms, curriculum packages, lesson plans, and daily scheduling.
---

# Academic Planning

Academic planning in Homeschool Hero covers everything from the big-picture school year structure down to a student's day-by-day schedule. Get this set up at the start of each year and the rest of the platform — gradebooks, report cards, compliance tracking — works automatically.

---

## Academic Calendar

Go to **Academics → Calendar**.

The calendar is the foundation of everything else. It defines what counts as a school year, which reporting periods exist, and when instructional days are.

### What to set up

| Element | Purpose |
|---|---|
| **School year** | The overall container (e.g., 2025–2026) with a start and end date |
| **Terms** | Semesters, quarters, trimesters, or custom — divide the year into sections |
| **Grading periods** | Reporting windows inside a term — these drive report card generation |
| **Calendar events** | Holidays, co-op days, closures, and non-instructional days |

### Why this matters

- The grade book **filters by grading period** — you can only see clean per-term summaries if periods are defined.
- Report cards are **generated per grading period** — no period, no report card.
- Compliance reports check **instructional day counts** against your state's calendar.
- Pacing alerts in lesson plans compare **planned lessons to remaining instructional days**.

### Step by step

1. Open **Academics → Calendar**.
2. Select **Add school year**. Enter the name, start date, and end date.
3. Inside the school year, add terms. Choose a type (semester, quarter, etc.) and enter dates.
4. Inside each term, add grading periods. Give each one a name (e.g., "Q1", "Fall Semester") and date range.
5. Add any holidays or closures as calendar events so instructional-day counts stay accurate.

::: tip
Do this before adding subjects, creating assignments, or generating lesson plans. Everything else builds on the calendar.
:::

---

## Curriculum Packages

Go to **Academics → Curriculum**.

Curriculum packages let you organize a full year's course content in one reusable structure.

### The structure

```
Package
└── Unit
    └── Lesson
```

A **package** is one subject for one school year (e.g., "Math 6 — 2025–2026"). It contains **units** for each major topic (e.g., "Fractions", "Geometry"). Each unit contains **lessons** — the individual activities or class sessions.

### Building a package

1. Select **Add curriculum package**.
2. Enter the package name, subject, and school year.
3. Add **units** inside the package.
4. Add **lessons** inside each unit. For each lesson you can set:
   - Title and description
   - Estimated duration
   - Standards tags (for states that require standards alignment)
   - Resource links
5. Save.

### Cloning packages

When you start a new school year, you can **clone** an existing package:
1. Open the package.
2. Select **Clone to school year**.
3. Choose the target year.

This preserves all units and lessons as a starting point that you then adjust for the new year. Great for textbook-based courses that follow the same structure year to year.

### Standards tags

Each lesson can be tagged with one or more standards codes. These tags flow into compliance reports that require standards alignment documentation.

---

## Lesson Plans

Go to **Academics → Lesson Plans**.

Lesson plans translate a curriculum package into a day-by-day or week-by-week schedule for a specific student. You can generate them automatically from a package or build them manually.

### Generating from a package

1. Open **Lesson Plans**.
2. Choose the student and school year.
3. Select **Generate from package**.
4. Pick the curriculum package.
5. Set a start date and pacing target.
6. Confirm — the system spreads lessons across instructional days automatically.

### Manual lesson plans

If you prefer to build manually (or supplement a generated plan):

1. Select **Add lesson plan**.
2. Choose the student, school year, and subject.
3. Add lessons individually, setting planned dates.

### Pacing targets and alerts

For each major unit, you can set a **pacing target** (e.g., finish Unit 3 by December 15). The system then:
- Shows a **pacing indicator** on lesson plan views
- Surfaces **pacing alerts** on the student dashboard and home screen
- Lets you run **Bulk reschedule** to redistribute remaining lessons if you fall behind

### Viewing lesson plans

Switch between two views:
- **Timeline view** — visual calendar with lesson blocks spread across the year
- **List view** — sortable table of all lessons with status, planned date, and notes

### Lesson statuses

| Status | Meaning |
|---|---|
| Planned | Scheduled but not yet done |
| In progress | Started but not complete |
| Complete | Done |
| Skipped | Intentionally skipped |

---

## Daily Planner

Go to **Academics → Planner**.

The Planner manages a student's actual daily schedule — which subjects happen when, and any one-off changes to that routine.

### Setting up a schedule

1. Choose the student.
2. Select **Add schedule** for the correct school year.
3. Add **recurring blocks**:
   - Subject
   - Day(s) of the week
   - Start and end time
4. Save.

The schedule repeats every week throughout the school year.

### Schedule overrides

When real life disrupts the routine, add an **override** for a specific date:
- Swap a subject for a different one
- Move a time block
- Cancel a block entirely

Overrides only affect the one date you specify.

### Agenda views

The Planner offers:
- **Daily agenda** — everything for one student on one day
- **Weekly agenda** — the full week at a glance

This view is most useful during morning check-in or end-of-week review.

---

## Attendance

Go to **Academics → Attendance**.

Attendance tracking is part of academic planning because most states require instructional day or hour records for compliance.

### Daily record

For each student and each school day, record:
- **Present / Absent / Tardy / Excused**
- **Instructional hours** (required in some states)
- **Check-in and check-out times** (optional)
- **Notes**

### Excuses

Create a formal excuse for any absence:
1. Select the absence.
2. Add a reason.
3. Optionally upload a supporting document (e.g., doctor's note).
4. Mark as approved.

Excuses are included in compliance reports and attendance logs automatically.

### Monthly view

The attendance calendar shows each day's status at a glance. Use it monthly to:
- Spot gaps before they become a compliance problem
- Confirm instructional day counts are on track
- Identify patterns in tardiness or absences

On mobile, swipe left/right to mark attendance quickly without opening each day individually.

---

## Resource Library

Go to **Data → Resources**.

The resource library is a shared file and link store for the whole family's homeschool materials.

### What to store here

- Printable worksheets (PDF)
- Reference links (websites, YouTube lessons)
- Teacher notes and answer keys
- Pacing guides and scope-and-sequence documents

### Organizing resources

Each resource can have:
- **Type** (file, link, or note)
- **Tags** (subject, grade level, topic, etc.)
- **Metadata** (title, description, source)

### Linking to lessons

From a lesson in a curriculum package, you can attach resources directly. When a teacher opens the lesson plan, the resources appear inline.

### Searching

Use the filter bar to search by type, tag, or keyword. The header global search (Ctrl/Cmd+K) also indexes resources.

---

## Planning Workflow: A Full-Year Setup in Order

If you are starting fresh for a new school year, do it in this order:

1. **Calendar** — create the school year, terms, grading periods, and holidays
2. **Students** — confirm all students are in the system
3. **Subjects** — set up each subject with grading mode, categories, and grade scale
4. **Curriculum packages** — build or clone packages for each subject
5. **Lesson plans** — generate from packages for each student
6. **Planner** — create weekly schedules and blocks
7. **Assignments** — add the first few weeks of work
8. **Done** — your year is live
