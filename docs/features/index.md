---
title: Features
description: An overview of Homeschool Hero's core features — academic planning, assignments, grading, reporting, and more.
---

# Features Overview

Homeschool Hero is an open-source, self-hosted platform that brings every part of homeschool administration into one connected workspace. Here is a map of what it can do.

---

## Core Feature Areas

### 📅 Academic Planning

Build the structure for your school year — calendar, terms, curriculum packages, lesson plans, and a daily planner.

**→ [Academic Planning](./academic-planning)**

Covers:
- School years, terms, and grading periods
- Holiday and closure tracking
- Curriculum packages (Package → Unit → Lesson)
- Lesson plan generation and pacing targets
- Day-by-day planner with recurring blocks
- Resource library

---

### 📝 Assignments & Grading

Create assignments, build quizzes, accept student work uploads, run AI-assisted grading, and manage a review queue for anything that needs a human eye.

**→ [Assignments & Grading](./assignments)**

Covers:
- Assignment creation with full metadata (subject, category, due date, weight, answer key)
- Recurring assignments
- Built-in quiz builder with auto-scoring
- Student work upload (photo, scan, or file)
- AI/OCR processing pipeline
- Review queue with bulk actions
- Grade book with weighted categories and trend data

---

### 📊 Reporting

From end-of-term report cards to state compliance filings, Homeschool Hero generates the documents you need and keeps the records that prove your homeschool is running well.

**→ [Reporting](./reporting)**

Covers:
- Grade book (running averages, GPA, letter grades)
- Report cards (PDF, teacher comments, finalize workflow)
- Transcripts (cumulative course history, credits, GPA)
- Compliance dashboard (traffic-light view of state requirements)
- Compliance reports (annual assessment, notice of intent, quarterly report, etc.)
- Portfolio and learning journal (work samples, milestones, shareable collections)

---

## Platform-Wide Capabilities

These features are available across all areas of the app.

### Search

Press **Ctrl / Cmd + K** or use the header search box to search across assignments, grades, students, curriculum, resources, attendance notes, notifications, and audit logs — all filtered to your family's data.

### Notifications

The bell icon in the top bar shows real-time alerts for due dates, grading completions, compliance reminders, backup status, and security notices. Configure per-type delivery (in-app or email) in **Settings → Notifications**.

### Mobile & PWA support

Homeschool Hero is fully responsive and installable as a Progressive Web App on iOS and Android. Key mobile features:
- Camera capture on the upload page (photograph paper assignments in-place)
- Pull-to-refresh on dashboard, uploads, and attendance
- Bottom tab navigation on small screens
- Swipe gestures for attendance entry

### Themes and accessibility

Go to **Settings → Appearance** to choose light, dark, or high-contrast themes, adjust font size and display density, and pick an accent color. All views meet WCAG 2.1 AA accessibility standards.

### Data portability

Go to **Data → Export** to export family data as JSON, CSV, or ZIP bundles (with PDFs and uploaded files). Import from CSV/JSON with a dry-run validation step. Scheduled and manual backups are available from **Settings → Backups**.

### Role-based access control

| Role | What they can access |
|---|---|
| **Admin** | Full platform — all families, system configuration, RBAC |
| **Parent / Teacher** | Full household — students, curriculum, grading, reports |
| **Student** | Their own data only — read-only, with optional upload access |

---

## Technology notes

- **Frontend:** React 18 + TypeScript, Vite, shadcn/ui, Tailwind CSS
- **Backend:** FastAPI (Python), PostgreSQL
- **Auth:** Email/password, Microsoft Entra OIDC, SAML
- **Self-hosted:** Docker-based single-container deployment (backend + built frontend)
- **AI grading:** Optional — uses OCR + answer-key matching; no data leaves your server
