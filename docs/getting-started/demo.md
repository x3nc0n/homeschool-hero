---
title: Try the Demo
description: Explore Homeschool Hero with pre-loaded demo data — no setup required.
---

# Try the Demo

Homeschool Hero ships with a demo mode that seeds a complete family with students, curriculum,
assignments, grades, and calendar events so you can explore every feature without entering a
single piece of real data.

## Start demo mode

```bash
git clone https://github.com/x3nc0n/homeschool-hero.git
cd homeschool-hero
cp .env.example .env          # DEMO_MODE=true is already set in .env.example
docker compose --profile ai up --build -d
```

Then open `http://localhost:8000` and log in:

| Field    | Value              |
|----------|--------------------|
| Email    | `demo@example.com` |
| Password | `demo1234`         |

::: tip First boot takes a few minutes
The `ai` profile pulls and initializes the Ollama LLM model on first start. AI grading features
will show as degraded until the model download completes. You can watch progress with:
`docker compose logs -f ollama`
:::

::: info Resetting demo data
To restore the demo to its original state: `docker compose down -v` then re-run the startup
command above. All demo data is re-seeded from scratch.
:::

---

## Meet the demo family

The demo seeds the **Demo Family** from Oklahoma with three students across different grade levels:

| Student | Grade | Core Subjects | Electives |
|---------|-------|---------------|-----------|
| **Emma** | 3 | ELA, Math, Science, Social Studies | Art, Music, PE |
| **Liam** | 7 | ELA, Math, Science, Social Studies | Art, Music, PE, Health |
| **Sophia** | 10 | English II, Geometry, Biology, World History | Fine Arts, PE, Health, Spanish I |

Each student has a complete curriculum with units, lessons, and Oklahoma Academic Standards (OAS)
alignment codes, plus assignments spread across Q1 and Q2 in various states.

---

## Feature tour

### 1 — Dashboard

After logging in you land on the **Dashboard** — your at-a-glance homeschool overview:

- **Student cards** — one per child showing grade level and recent activity
- **Upcoming due dates** — assignments that need attention
- **Recent grades** — latest graded work

*Try it:* Look for Emma, Liam, and Sophia's cards. Notice the assignment counts and recent grades.

---

### 2 — Students

Navigate to **Students** in the sidebar.

- All three students are listed with their grade levels
- Click a student name to open their **detail page**
- The detail page shows enrolled subjects, assignment counts, and grade summaries

*Try it:* Click **Sophia** to see her grade-10 subjects, including Spanish I and Biology.

---

### 3 — Subjects

Navigate to **Subjects** in the sidebar.

Subjects are the organizing layer — curriculum packages, assignments, and grades all link to a
subject. Each subject belongs to one student.

*Try it:* Filter by student to see just Emma's 7 subjects vs. Sophia's 8.

---

### 4 — Curriculum

Navigate to **Curriculum** in the sidebar. The tabbed page has three sections:

**Packages** (default tab) — structured curriculum content organized as:
- **Units** — major topic groups (e.g., "Multiplication & Division")
- **Lessons** — individual lessons within each unit
- **Standards** — OAS alignment codes

*Try it:* Find Emma's Mathematics package. Expand it to see three units ("Multiplication &
Division," "Fractions & Number Sense," "Area, Perimeter & Data"), each with four lessons.

**Lesson Plans** — teaching plans that connect a curriculum lesson to a specific date and student.

**Resources** — supplemental materials (links, files, documents) attached to lessons or subjects.

---

### 5 — Calendar

Navigate to **Calendar** in the sidebar.

The calendar shows your school year schedule. The demo seeds a full academic year:

| Event | Date | Type |
|-------|------|------|
| Labor Day | Sep 1, 2025 | Holiday |
| Fall Break | Oct 16, 2025 | Closure |
| Thanksgiving | Nov 24, 2025 | Closure |
| Winter Break | Dec 22, 2025 | Closure |
| MLK Day | Jan 19, 2026 | Holiday |
| Presidents Day | Feb 16, 2026 | Holiday |
| Spring Break | Mar 16, 2026 | Closure |
| Last Day | May 22, 2026 | Custom |

*Try it:* Navigate through the months to see how holidays and instructional days are tracked.

---

### 6 — Assignments

Navigate to **Assignments** under Schoolwork.

The demo seeds **10 assignment blueprints per subject**, creating a realistic mix across Q1 and Q2:

| Assignment | Type | Quarter | Status |
|------------|------|---------|--------|
| Reading Response | Homework | Q1 | Graded (92, AI) |
| Skills Check | Quiz | Q1 | Graded (84, Human) |
| Lab Notes | Homework | Q1 | Complete |
| Unit Quiz | Quiz | Q1 | Graded (76, AI+Human) |
| Project Plan | Project | Q1 | Pending |
| Essay Draft | Homework | Q2 | Complete |
| Quarter Test | Test | Q2 | Graded (88, Human) |
| Creative Project | Project | Q2 | Graded (95, AI) |
| Practice Set | Homework | Q2 | Pending |
| Reflection Check | Quiz | Q2 | Graded (69, Human) |

*Try it:* Filter assignments by student or subject. Click an assignment to see its details and
submission history.

---

### 7 — Uploads & Submissions

Navigate to **Upload** under Schoolwork.

This is where parents or students submit completed work. Submissions link to assignments and
support PDF and image uploads (JPEG, PNG, HEIC, TIFF, WebP).

The workflow:
1. Select an assignment
2. Upload a scan or photo of the completed work
3. The system queues OCR and AI grading automatically
4. Results appear in the Gradebook; low-confidence grades go to the Review Queue

*Try it:* Find assignments in "complete" status — these have submissions awaiting or with grades.

---

### 8 — Gradebook

Navigate to **Gradebook** under Schoolwork. The tabbed page has two sections:

**Grades tab** (default) — grade summaries by student and subject with KPI cards, charts, and
per-subject averages.

**Review Queue tab** — submissions flagged for human review because AI confidence was below the
threshold (default: 80%). The queue shows pending reviews with bulk action controls.

*Try it:* Check Emma's Reading Response (scored 92, AI-graded) and Liam's Reflection Check
(scored 69, human-reviewed) to see how the two grading paths look.

---

### 9 — Academic Records

Navigate to **Academic Records** under Records.

**Report Cards tab** — generate formal report cards for any grading period with per-subject
grades, letter grades, percentage scores, GPA, and teacher comments.

**Transcripts tab** — create official transcripts with cumulative course history, credit hours,
and GPA. Especially useful for high school students like Sophia applying to college.

*Try it:* Generate a draft report card for Sophia for Q1.

---

### 10 — Data Management

Navigate to **Data Management** under Settings.

| Tab | Purpose |
|-----|---------|
| Import | Bulk-create students, subjects, or grades from CSV/JSON |
| Export | Download data as CSV or JSON |
| Backups | Create and manage full database backups |
| Restore | Restore from a previous backup |

---

### 11 — Settings: Family & Features

Navigate to **Family & Features** under Settings.

**Family Settings** — family name, state (Oklahoma), timezone (America/Chicago), and grading
scale (letter grades A/B/C/D/F).

**Feature Toggles** — optionally enable or disable platform features:

| Feature | Default | Purpose |
|---------|---------|---------|
| Attendance | On | Track daily student attendance |
| Quizzes | On | Built-in quiz builder |
| Compliance | On | State homeschool compliance tracking |
| Portfolio | On | Student portfolio collections |
| Planner | On | Daily/weekly schedule planner |

*Try it:* Toggle **Attendance** off and watch its sidebar entry disappear. Toggle it back on — data
is preserved.

---

### 12 — Appearance

Navigate to **Appearance** under Settings to customize theme (Light/Dark/System), accent color,
font size, density (Comfortable/Compact), and sidebar position.

---

## Ready to set up your real homeschool?

1. Stop the demo stack: `docker compose down -v`
2. Edit `.env` and set `DEMO_MODE=false`
3. Continue with the **[Setup Wizard →](./setup-wizard)**
