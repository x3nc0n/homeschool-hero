---
title: Parent & Teacher Guide
description: A task-oriented guide for parents and teachers managing students, curriculum, assignments, grading, and reports in Homeschool Hero.
---

# Parent & Teacher Guide

This guide covers everything parents and teachers do day-to-day in Homeschool Hero: setting up your workspace, planning the year, managing assignments, grading work, and generating reports.

::: tip First time?
Start with **[Setting Up Your Workspace](#setting-up-your-workspace)** before anything else. Getting your calendar, students, and subjects in place first makes every other task much smoother.
:::

---

## Signing In

Homeschool Hero supports three sign-in methods:

- **Email + password** — the default for most self-hosted setups
- **OIDC single sign-on** (e.g. Microsoft Entra ID) — if your administrator has enabled it
- **SAML single sign-on** — for organization-managed deployments

If this is a brand-new installation, you will see a **first-time setup screen** instead of the normal login page. Follow the prompts to create your family account, then sign in.

### Accepting an invitation

If a co-parent or admin invited you:

1. Open the invitation link.
2. Enter your email and display name.
3. Create a password.
4. Submit — you will land directly in your family workspace.

---

## Getting Around

The navigation sidebar groups everything into logical sections:

| Section | What's here |
|---|---|
| **Dashboard** | Overview, notifications |
| **Students** | Roster, student profiles |
| **Academics** | Calendar, planner, curriculum, lesson plans, attendance |
| **Assignments & Grading** | Assignments, quizzes, uploads, review queue, grade book |
| **Reports** | Report cards, transcripts, compliance, portfolio |
| **Data** | Import/export, resource library |
| **Settings** | Family, invitations, appearance, backups |

**Quick tips:**
- Press **Ctrl / Cmd + K** to open global search from anywhere
- The **notifications bell** (top right) shows due-date alerts, grading updates, and system notices
- On mobile, use the **bottom tab bar** or the hamburger menu to navigate

---

## Setting Up Your Workspace

Complete this once at the start of each school year.

### 1. Build your academic calendar

Go to **Academics → Calendar**.

1. Create a **school year** with start and end dates.
2. Add **terms** (semester, quarter, trimester, or custom).
3. Add **grading periods** inside each term.
4. Mark any **holidays or non-instructional days**.

The calendar powers gradebook filters, compliance tracking, and report generation — get it right first.

### 2. Add students {#managing-students}

Go to **Students**.

1. Select **Add student**.
2. Enter the student's name.
3. Repeat for each learner.

From the student list you can:
- Open any student's **detail dashboard** (GPA, attendance, assignments due, pacing status)
- Rename or remove a student

### 3. Set up subjects {#setting-up-subjects}

Go to **Academics → Curriculum** (or **Subjects** in the sidebar, depending on your install).

For each subject:

1. Enter a **subject name** and pick a **color**.
2. Choose a **grading mode**: points-based or percentage-based.
3. Apply a **grade scale** (family default or a custom one).
4. Add **grade categories** such as Homework, Quiz, and Test — each with a weight and an optional "drop lowest" rule.

Consistent subject setup leads to clean gradebooks and accurate report cards later.

### 4. Set family-wide preferences

Go to **Settings → Family**.

Configure:
- **State code** — used for compliance report generation
- **Grade scales** — default scales applied when no subject-specific scale is set
- **Language** — interface language for your workspace

### 5. Invite other adults

Go to **Settings → Invitations**.

You can invite:
- **Co-parents** — full household management access
- **Tutors** — teaching and grading, more limited family administration
- **Student viewers** — read-only, scoped to one student

When creating an invitation, set the role, expiration window, and (for student viewers) which student they can see. Copy the link or email it directly.

---

## Planning the Year

### Academic calendar

Go to **Academics → Calendar**.

Use the calendar to define the year's structure. Beyond setup, return here to add unexpected closures, adjust term boundaries, or review the instructional-day count.

### Curriculum packages

Go to **Academics → Curriculum**.

Curriculum is organized as **Package → Unit → Lesson**.

To build a package:

1. Create a **curriculum package** (tied to a subject and school year).
2. Add **units** for each major topic.
3. Add **lessons** inside each unit.
4. Tag lessons with **standards** if you track them.
5. Clone the package into the next school year when it's time.

This structure feeds directly into lesson plan generation.

### Lesson plans and pacing

Go to **Academics → Lesson Plans**.

1. Choose a student and school year.
2. Select **Generate from package** to turn a curriculum package into a lesson-by-lesson plan automatically, or add lessons manually.
3. Set **pacing targets** for major units.
4. Use the **pacing view** to spot lessons falling behind schedule.
5. Use **Bulk reschedule** when life disrupts the plan.
6. Switch between **timeline** and **list** views based on what you need to see.

### Daily planner

Go to **Academics → Planner**.

1. Choose a student.
2. Create a **schedule** for the correct school year.
3. Add **recurring blocks** (e.g., "Math — weekdays 9–10 AM").
4. Add **date-specific overrides** when things change.
5. Review the **daily** and **weekly agenda** views.

The Planner shows what is actually happening each day; Lesson Plans tracks the bigger curriculum arc.

### Resource library

Go to **Data → Resources**.

Store worksheets, links, printable packets, and teacher notes here. Tag them, attach them to specific lessons, and search by type or tag. A well-organized resource library saves significant prep time across the year.

---

## Creating Assignments {#creating-assignments}

Go to **Assignments & Grading → Assignments**.

### What you can set on an assignment

| Field | Notes |
|---|---|
| Title | Required |
| Description | Instructions for the student |
| Subject | Links to gradebook category |
| Category | Homework, Quiz, Test, etc. |
| Due date | Drives dashboard alerts |
| Grading period | For gradebook filtering |
| Weight | Adjusts impact on category average |
| Maximum score | Total points possible |
| Recurrence | None, daily, or weekly |
| Rubric notes | Guidance for grading |
| Answer key | Powers auto-grading (see below) |
| Students | Assign to one or multiple students |

### Step-by-step

1. Select **New assignment**.
2. Fill in the title, description, and due date.
3. Choose the subject and category.
4. Assign to the relevant students (siblings can be assigned independently).
5. Save.

### Answer keys

For any assignment you want to auto-grade or review efficiently, add an answer key:

1. Open the assignment.
2. Add rows for each question: question number, correct answer, point value, and optional partial-credit rules.

Answer keys are used by the AI-assisted grading system when a scan is uploaded.

### Recurring assignments

For daily reading logs, weekly vocabulary drills, or similar repeated work, set a recurrence rule. The system generates assignment instances on the appropriate days automatically.

---

## Uploading Student Work {#uploading-student-work}

Go to **Assignments & Grading → Uploads**.

Students do their work on paper and bring it to you (or you photograph it). This page handles the submission.

### Supported file types

PDF, JPEG/JPG, PNG, HEIC/HEIF, TIFF, WEBP — up to **25 MB** per file.

### Uploading a submission

1. Choose the **student**.
2. Choose the matching **assignment**.
3. Add the file by dragging it in, browsing, or tapping **Use camera** on mobile.
4. Review the **preview**.
5. Select **Upload submission**.

After upload, the submission panel shows:
- Current version number
- Grading progress bar
- Confidence score (when AI grading is active)
- Manual review reason (if flagged)

### Resubmitting work

You can upload a **new version** at any time. Older versions are preserved; the newest becomes the active one used for grading.

::: tip Mobile upload tip
Taking a phone photo straight from the Upload page is the fastest way to capture handwritten work on a busy school day. Use good lighting and keep the page flat for better OCR results.
:::

---

## Grading and the Review Queue {#grading-and-the-review-queue}

### How grading works

After a file is uploaded, Homeschool Hero can:
1. **OCR** the document to extract text
2. **AI-grade** it against the answer key
3. Flag it for **manual review** if confidence is low

A submission moves through statuses: *Pending → OCR processing → OCR complete → AI grading → Review needed → Reviewed → Final*.

### Review queue

Go to **Assignments & Grading → Review Queue**.

Filter by status, priority, student, subject, or search term. Then:

- **Open an item** to see the uploaded image, OCR text, AI confidence score, AI feedback, and the answer-key suggestion side-by-side.
- **Approve** if the AI result looks correct.
- **Re-grade** to override the score manually.
- **Reject / request resubmission** if the work needs to come back.
- Add **reviewer notes** or **comments** for co-teachers.
- Use **Bulk approve** or **Bulk assign** to process a stack of items quickly.

### Grade book

Go to **Assignments & Grading → Grade Book**.

1. Choose a student.
2. Optionally filter by subject and grading period.
3. Review **subject cards** with running averages, category breakdowns, and letter grades.
4. Select **Recalculate** to refresh computed scores.

The grade book is your best single-screen summary of how a student is actually doing.

---

## Quizzes

Go to **Assignments & Grading → Quizzes**.

### Building a quiz

1. Enter a title and optionally assign a subject.
2. Add questions: **multiple choice**, **short answer**, or **true/false**.
3. Save the quiz.

### Running a quiz

1. Choose the student.
2. Choose the quiz.
3. Enter responses (parent-assisted or student-entered on screen).
4. Submit — the system auto-scores what it can immediately.

---

## Attendance

Go to **Academics → Attendance**.

Record for each student per day:

- **Present / Absent / Tardy / Excused**
- **Instructional hours** (for hour-based state tracking)
- **Check-in / check-out times**
- **Notes**

### Excuses

Create an excuse with a reason and an optional uploaded document. Excuses can be approved and attached to a compliance report.

### Monthly calendar view

The attendance calendar lets you spot patterns, review each day's status, and identify gaps before they become compliance issues. On mobile, swipe gestures speed up daily entry.

---

## Reports

### Report cards

Go to **Reports → Report Cards**.

1. Select the student.
2. Select the grading period.
3. Click **Generate** to create a draft.
4. Review the draft: subject grades, percentages, letter grades, GPA points, attendance summary.
5. Add **teacher comments** and general notes.
6. Save the draft.
7. **Finalize** when ready — finalized report cards are locked for record integrity.
8. **Download PDF** for printing or filing.

### Transcripts

Go to **Reports → Transcripts**.

Transcripts provide a cumulative academic record with course titles, credits, honors/AP flags, GPA, and notes. Essential for older students, college applications, and long-term records.

### Compliance dashboard

Go to **Reports → Compliance**.

A traffic-light overview of your state requirements:
- **Green** — compliant
- **Yellow** — warning, action may be needed
- **Red** — non-compliant, action required

Switch school years using the year selector at the top.

### Compliance reports

Go to **Reports → Compliance Reports**.

Available types:
- Annual assessment
- Quarterly progress report
- Notice of intent
- Attendance log
- Portfolio review

Workflow: choose student → school year → report type → grading period (if needed) → Generate draft → review → add notes → Finalize → Download PDF.

### Portfolio

Go to **Reports → Portfolio**.

Collect learning evidence over time:

| Entry type | Good for |
|---|---|
| Work sample | A finished piece of work |
| Journal | Written reflection |
| Milestone | Skill mastered, goal reached |
| Photo | Hands-on project, field trip |
| Note | Teacher observation |

Group entries into **Collections** (e.g., "Fall science highlights"). Mark a collection **public** to generate a shareable link for grandparents, reviewers, or portfolio evaluators.

---

## Suggested Routines

### Weekly planning (15 min)

1. Open **Dashboard** — check pacing alerts and upcoming due dates.
2. Open **Lesson Plans** — adjust the week if anything has shifted.
3. Check **Planner** — confirm no schedule conflicts.
4. Add or update **assignments** for each student.

### Daily grading (10–20 min)

1. Upload student work from **Uploads** (or photograph it with your phone).
2. Watch for auto-grading progress.
3. Open **Review Queue** for anything flagged.
4. Approve or adjust scores.
5. Glance at **Grade Book** for updated averages.

### Monthly record-keeping (30 min)

1. Review the **Compliance** dashboard for any yellow or red items.
2. Update **Attendance** for any missed days.
3. Generate **compliance reports** or **report cards** as needed.
4. Run an **Export** or **Backup** to preserve records.

---

## Tips and Best Practices

- **Set up the calendar first.** Terms and grading periods make reporting much smoother later.
- **Use categories consistently.** Homework/Quiz/Test as separate weighted categories gives you accurate subject grades.
- **Add answer keys when you can.** They speed up grading and give AI better context.
- **Use mobile camera upload on busy days.** It is the fastest way to capture handwritten work.
- **Review low-confidence AI results before finalizing.** AI is a helper — your judgment is the final word.
- **Keep attendance current.** It is much harder to reconstruct later than to record in the moment.
- **Use Portfolio for proof of learning.** It is ideal for state portfolio reviews and annual evaluations.
- **Back up regularly.** Go to **Settings → Backups** and set a schedule so your records are always safe.

---

## When Something Looks Wrong

1. Refresh the page.
2. Check **Settings → System status** for health and availability.
3. Look for notices on the page about reduced AI, OCR, email, or backup availability.
4. Check **Notifications** for related alerts.
5. Ask your Homeschool Hero administrator for help if the issue persists.
