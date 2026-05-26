---
title: Setup Wizard
description: Walk through the first-run owner bootstrap and initial family configuration.
---

# Setup Wizard

The first time you open Homeschool Hero after installation, the app detects that no owner account
exists and redirects you to the **setup wizard**. This one-time flow creates the platform owner,
defines your family, and gets you ready to add students.

::: info Check bootstrap status
You can check whether setup is still required at any time:
```bash
curl http://localhost:8000/api/auth/bootstrap
# {"bootstrap_required": true}  → setup not yet complete
# {"bootstrap_required": false} → setup complete
```
:::

---

## Step 1 — Create the owner account

The first page of the wizard collects your owner account details:

| Field | Notes |
|-------|-------|
| **Email** | Used to log in. Defaults to `BOOTSTRAP_OWNER_EMAIL` from `.env` if set. |
| **Display name** | Shown in the UI. Defaults to `BOOTSTRAP_OWNER_DISPLAY_NAME`. |
| **Password** | Minimum 12 characters (configurable via `PASSWORD_MIN_LENGTH`). |
| **Confirm password** | Must match. |

::: warning This is permanent
Once the owner account is created, `/api/auth/register` is disabled for open self-registration.
Future family members are added via the invitation system. Choose your email carefully — it
becomes the permanent owner identity.
:::

After this step, the app creates:
- A `User` record with `is_owner = true`
- A `Family` record using the `BOOTSTRAP_FAMILY_NAME` default
- A `FamilyMembership` linking the user to the family as `role = parent`

---

## Step 2 — Configure your family

The second page sets up your family profile:

**Family name** — the display name for your household (e.g., "The Johnson Family").

**State** — your US state. This matters for compliance tracking. The platform uses state codes
to load state-specific academic standards and compliance rules (e.g., Oklahoma Academic Standards).

**Timezone** — your local timezone for calendar events, due dates, and scheduled tasks.
All timestamps in the database are stored in UTC; the timezone converts display values in the UI.

**Grading scale** — how grades are displayed and reported:

| Scale | Example | Best for |
|-------|---------|---------|
| `letter` | A, B, C, D, F | Standard US grading |
| `percentage` | 92%, 84%, 76% | Numeric tracking |
| `custom` | defined per subject | Mixed or non-standard grading |

These defaults can all be changed later in **Settings → Family & Features**.

---

## Step 3 — Feature toggles

The wizard offers a quick preview of optional features. You can enable or disable them now or
change them any time from **Settings → Family & Features**:

| Feature | Default | Purpose |
|---------|---------|---------|
| **Attendance** | On | Daily attendance tracking per student |
| **Quizzes** | On | Built-in quiz builder and quiz taking |
| **Compliance** | On | State homeschool compliance tracking |
| **Portfolio** | On | Student portfolio collections |
| **Planner** | On | Daily/weekly schedule planner |

When a feature is disabled, its sidebar entries are hidden but data is preserved. Re-enabling the
feature immediately restores access.

---

## Step 4 — Add your first student

Add at least one student to complete setup:

| Field | Notes |
|-------|-------|
| **First name** | Student's display name |
| **Last name** | Used in records, transcripts, and report cards |
| **Grade level** | Used to pre-filter curriculum and standards (can be updated each year) |
| **Date of birth** | Optional; used in compliance records |

You can add more students later from **Students → Add Student**. There is no limit on students
per family.

---

## After the wizard completes

Once all steps are done, you're redirected to the **Dashboard**. Here's what to do next:

### Add more family members

Invite a co-parent, spouse, or tutor via **Settings → Invitations**. Each person gets their own
account with a role appropriate to their relationship:

| Role | What they can do |
|------|-----------------|
| **Parent / Co-parent** | Full household management: students, curriculum, grading, invitations |
| **Tutor** | Educational work only: curriculum, assignments, grading. No household admin. |

### Set up subjects

Go to **Subjects** and create the academic subjects for each student. Subjects are the
organizational backbone — curriculum and assignments attach to subjects.

### Create curriculum

Go to **Curriculum → Packages** to create or import curriculum packages. A package contains:
- Units (major topic groups)
- Lessons (individual lessons within each unit)
- Standards alignment codes

You can build curriculum from scratch or import from CSV.

### Create assignments

Go to **Assignments → New Assignment** to create your first assignment. Link it to a student,
subject, and optionally a curriculum lesson. Set a due date and assignment type (homework, quiz,
test, project).

---

## Troubleshooting

**The wizard doesn't appear — I see the login page instead.**
The owner account already exists. Log in with the email set in `BOOTSTRAP_OWNER_EMAIL` and the
password you configured. If you've lost access, see [Operations → Reset Owner Access](/admin/operations#reset-owner-access).

**I need to change my owner email after setup.**
Email changes for the owner account require a direct database update or a support script. Contact
your administrator or see the operations guide.

**The timezone I need isn't in the list.**
The dropdown covers IANA timezone identifiers (e.g., `America/Chicago`). If you need a less
common timezone, you can set it directly in `BOOTSTRAP_TIMEZONE` in `.env` before first boot, or
update it via the Settings page after setup.
