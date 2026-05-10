# Homeschool Hero — Getting Started Guide

This hands-on guide walks you through every feature using the built-in demo
data. Start the app in demo mode, open this page side-by-side, and follow
along.

## Starting Demo Mode

```bash
git clone https://github.com/x3nc0n/homeschool-hero.git
cd homeschool-hero
cp .env.example .env          # DEMO_MODE=true is already set
docker compose --profile ai up --build -d
```

Open **http://localhost:8000** and log in:

| Field    | Value                |
|----------|----------------------|
| Email    | `demo@example.com`   |
| Password | `demo1234`           |

> **Tip:** To reset demo data, run `docker compose down -v` then
> `docker compose --profile ai up --build -d`.
>
> **AI note:** Demo grading and review features require the `ai` profile so the
> `ollama` service starts. On first boot, Ollama downloads `OLLAMA_MODEL`, so AI
> features may stay degraded for a few minutes until the model is ready.

---

## Meet the Demo Family

The demo seeds the **Demo Family** from Oklahoma with three students:

| Student | Grade | Core Subjects | Electives |
|---------|-------|---------------|-----------|
| **Emma**   | 3  | ELA, Math, Science, Social Studies | Art, Music, PE |
| **Liam**   | 7  | ELA, Math, Science, Social Studies | Art, Music, PE, Health |
| **Sophia** | 10 | English II, Geometry, Biology, World History | Fine Arts, PE, Health, Spanish I |

Each student has a full set of curriculum packages with units and lessons, plus
assignments in various states (pending, complete, graded) across Q1 and Q2.

---

## 1 — Dashboard

After logging in you land on the **Dashboard**. This gives you an at-a-glance
overview of your homeschool:

- **Student cards** — one for each child showing their grade level
- **Recent activity** — latest assignments and grades
- **Upcoming due dates** — assignments that need attention

*Try it:* Look for Emma, Liam, and Sophia's cards. Notice the assignment
counts and recent grades.

---

## 2 — Students

Navigate to **Students** in the sidebar.

- You'll see all three students listed with their grade levels
- Click a student name to open their **detail page**
- The detail page shows their enrolled subjects, assignments, and grades

*Try it:* Click **Sophia** to see her grade-10 subjects, including Spanish I
and Biology.

---

## 3 — Subjects

Navigate to **Subjects** in the sidebar.

Each student has their own set of subjects. Subjects are the foundation —
curriculum, assignments, and grades all link to a subject.

- Subjects show the student they belong to and their status
- You can create, edit, or archive subjects here

*Try it:* Filter by student to see just Emma's 7 subjects vs. Sophia's 8.

---

## 4 — Curriculum

Navigate to **Curriculum** in the sidebar. This is now a tabbed page with
three sections:

### Packages tab (default)

Curriculum packages contain the structured content for each subject. Each
package has:

- **Units** — major topic groups (e.g., "Multiplication & Division")
- **Lessons** — individual lessons within each unit
- **Standards** — Oklahoma Academic Standards (OAS) alignment codes

*Try it:* Find Emma's Mathematics package. Expand it to see the three units:
"Multiplication & Division," "Fractions & Number Sense," and "Area, Perimeter
& Data." Each unit has four lessons.

### Lesson Plans tab

Lesson plans turn curriculum into daily teaching plans. They connect a
curriculum lesson to a specific date and student.

*Try it:* Switch to the Lesson Plans tab to see generated plans across
students.

### Resources tab

The resource library stores supplemental materials (links, files, documents)
that you can attach to lessons or subjects.

*Try it:* Browse the Resources tab to see how materials are organized.

---

## 5 — Calendar

Navigate to **Calendar** in the sidebar.

The calendar shows your school year schedule. The demo seeds a full academic
year with:

| Event             | Date         | Type    |
|-------------------|--------------|---------|
| Labor Day         | Sep 1, 2025  | Holiday |
| Fall Break        | Oct 16, 2025 | Closure |
| Thanksgiving      | Nov 24, 2025 | Closure |
| Winter Break      | Dec 22, 2025 | Closure |
| MLK Day           | Jan 19, 2026 | Holiday |
| Presidents Day    | Feb 16, 2026 | Holiday |
| Spring Break      | Mar 16, 2026 | Closure |
| Last Day          | May 22, 2026 | Custom  |

*Try it:* Navigate through the months to see how events and instructional days
are tracked.

---

## 6 — Assignments

Navigate to **Assignments** under Schoolwork.

The demo seeds **10 assignment blueprints** per subject, creating a realistic
mix across Q1 and Q2:

| Assignment        | Type     | Quarter | Status    |
|-------------------|----------|---------|-----------|
| Reading Response  | Homework | Q1      | Graded (92, AI) |
| Skills Check      | Quiz     | Q1      | Graded (84, Human) |
| Lab Notes         | Homework | Q1      | Complete  |
| Unit Quiz         | Quiz     | Q1      | Graded (76, AI+Human) |
| Project Plan      | Project  | Q1      | Pending   |
| Essay Draft       | Homework | Q2      | Complete  |
| Quarter Test      | Test     | Q2      | Graded (88, Human) |
| Creative Project  | Project  | Q2      | Graded (95, AI) |
| Practice Set      | Homework | Q2      | Pending   |
| Reflection Check  | Quiz     | Q2      | Graded (69, Human) |

*Try it:* Filter assignments by student or subject. Notice the mix of
pending, complete, and graded statuses. Click an assignment to see its details.

---

## 7 — Upload

Navigate to **Upload** under Schoolwork.

This is where students (or parents) submit completed work. Submissions link
to assignments and can include file uploads.

*Try it:* Find assignments in "complete" status — these have submissions
awaiting grading.

---

## 8 — Gradebook

Navigate to **Gradebook** under Schoolwork. This tabbed page has two sections:

### Grades tab (default)

The gradebook shows grade summaries by student and subject with:

- **KPI cards** — overall averages and trends
- **Charts** — visual grade distributions
- **Subject breakdown** — per-subject averages

*Try it:* Check the scores from the demo data. Emma's Reading Response scored
92, while Liam's Reflection Check came in at 69 — a good range to see how
averages work.

### Review Queue tab

When assignments are submitted, they enter the review queue for grading. The
queue shows:

- Pending reviews with submission details
- Bulk action controls for batch grading
- Filter by student or subject

*Try it:* Switch to the Review Queue tab to see submissions waiting for
grades.

---

## 9 — Academic Records

Navigate to **Academic Records** under Records. This tabbed page combines:

### Report Cards tab

Generate formal report cards for any grading period. The system pulls grades
from the gradebook to create:

- Per-subject grades with letter and percentage
- Overall GPA calculations
- Teacher comments

*Try it:* Select a student and generate a draft report card for Q1.

### Transcripts tab

Create official transcripts for cumulative academic records:

- Course history across school years
- Credit hours and GPA
- Suitable for college applications (especially relevant for Sophia in
  grade 10)

*Try it:* Generate a transcript for Sophia to see how high school credits
are tracked.

---

## 10 — Data Management

Navigate to **Data Management** under Settings. This tabbed page consolidates:

| Tab      | Purpose |
|----------|---------|
| Import   | Upload CSV/JSON data to bulk-create students, subjects, or grades |
| Export   | Download your data as CSV or JSON for external use |
| Backups  | Create and manage full database backups |
| Restore  | Restore from a previous backup |

*Try it:* Explore the Export tab to see what data formats are available.

---

## 11 — Settings: Family & Features

Navigate to **Family & Features** under Settings.

This is where you configure your homeschool and toggle optional features
on/off:

### Family Settings

- **Family name** and **state** (Demo Family, Oklahoma)
- **Timezone** (America/Chicago)
- **Grading scale** (Letter grades: A/B/C/D/F)

### Feature Toggles

Some features are optional. Toggle them on or off based on your family's
needs:

| Feature    | Default | Description |
|------------|---------|-------------|
| Attendance | On      | Track daily attendance for each student |
| Quizzes    | On      | Built-in quiz builder and quiz-taking |
| Compliance | On      | State compliance tracking and reporting |
| Portfolio  | On      | Student portfolio for showcasing work |
| Planner    | On      | Schedule planner for daily/weekly planning |

When you turn off a feature, its nav item disappears from the sidebar. The
data is preserved — turn it back on anytime.

*Try it:* Toggle **Attendance** off and watch it disappear from the sidebar.
Toggle it back on.

---

## 12 — Appearance

Navigate to **Appearance** under Settings.

Customize the look and feel:

- **Theme** — Light, Dark, or System
- **Accent color** — personalize the color scheme
- **Font size** — Small, Medium, or Large
- **Density** — Comfortable or Compact
- **Sidebar position** — Left or Right

*Try it:* Switch to Dark mode and try Compact density to see how the layout
adjusts.

---

## Optional Features

These features are controlled by the toggles in Family & Features:

### Attendance (if enabled)

Track daily attendance per student. Mark present, absent, tardy, or excused.
Useful for states that require attendance records.

### Planner (if enabled)

Plan your weekly schedule. Assign subjects to days and time slots to create
a structured routine.

### Quizzes (if enabled)

Build custom quizzes with multiple question types. Students can take quizzes
directly in the app and results feed into the gradebook.

### Portfolio (if enabled)

Curate a portfolio of student work. Collect assignments, projects, and
achievements into shareable collections.

### Compliance (if enabled)

Track state homeschool requirements. Set up compliance rules for your state
(attendance days, required subjects, assessments) and monitor status.

---

## Tips

- **Keyboard navigation** — The app supports full keyboard navigation. Use
  Tab to move between controls and Enter to activate.
- **Search** — Use the search bar in the top navigation to quickly find
  students, subjects, or assignments.
- **Notifications** — Click the bell icon to see system notifications and
  configure preferences.
- **PWA** — Install Homeschool Hero as a progressive web app for offline
  access. Look for the install prompt in your browser.

---

## Next Steps

After exploring with demo data, you're ready to set up your real homeschool:

1. **Stop and reset** — `docker compose down -v`
2. **Disable demo mode** — Edit `.env` and set `DEMO_MODE=false`
3. **Start fresh** — `docker compose up --build -d`
4. **Run setup** — Create your family account at the setup screen
5. **Add students** — Enter your children's names and grade levels
6. **Create subjects** — Add the subjects each child is studying
7. **Set up curriculum** — Create or import curriculum packages
8. **Start assigning** — Create assignments and track progress!
