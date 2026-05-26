---
title: Assignments & Grading
description: How Homeschool Hero handles assignment creation, quiz auto-grading, student work uploads, AI/OCR processing, the review queue, and the grade book.
---

# Assignments & Grading

Homeschool Hero's assignments and grading system covers the full arc from "create the work" to "record the grade." Assignments are created by parents or teachers, students complete the work on paper, and the system handles processing scanned submissions — automatically where it can, with a human review queue for everything else.

---

## Assignments

Go to **Assignments & Grading → Assignments**.

### What an assignment can contain

| Field | Description |
|---|---|
| **Title** | Required. Shown on dashboard and student views. |
| **Description** | Instructions, reading pages, or context for the student. |
| **Subject** | Links the grade to the right course in the gradebook. |
| **Category** | Homework, Quiz, Test, or custom — sets the weight class. |
| **Due date** | Triggers dashboard alerts for student and parent. |
| **Grading period** | Which reporting window this counts toward. |
| **Weight** | How much this assignment counts within its category. |
| **Max score** | Total points possible. |
| **Recurrence** | None, daily, or weekly — auto-generates future instances. |
| **Rubric notes** | Private grading guidance for the reviewer. |
| **Answer key** | Powers auto-grading (see below). |
| **Students** | Assign to one student or multiple — independently. |

### Creating an assignment

1. Select **New assignment**.
2. Enter the title and description.
3. Set the subject and category.
4. Pick the due date and grading period.
5. Assign to the relevant students (you can assign siblings separately, with different due dates if needed).
6. Save.

The assignment immediately appears on each assigned student's dashboard and in the Assignments list.

### Assigning to multiple students

Assignments are linked to individual students, not broadcast to all. This means:
- Each student gets their own submission entry.
- Different students can have different due dates for the same assignment.
- Status is tracked independently (one sibling can be graded while another is still submitted).

### Recurring assignments

For daily or weekly repeated work (reading logs, math drills, vocabulary practice), set a recurrence rule. Homeschool Hero generates instances on the correct days throughout the grading period without you needing to create each one manually.

### Answer keys

Answer keys make grading faster and enable AI-assisted grading. To add one:

1. Open an assignment.
2. Navigate to the **Answer key** section.
3. Add a row for each question:
   - Question number
   - Correct answer
   - Point value
   - Partial credit rules (optional)
4. Save.

When a student's work is uploaded and OCR-processed, the answer key is used to score automatically.

::: tip
Even if you do not use AI grading, answer keys help you stay consistent when scoring by hand during review.
:::

---

## Student Work Uploads

Go to **Assignments & Grading → Uploads**.

Students do their work on paper. This page is where that work enters the digital system.

### Supported file types

| Format | Notes |
|---|---|
| PDF | Multi-page supported |
| JPEG / JPG | Most common phone photo format |
| PNG | High-quality screenshots or scans |
| HEIC / HEIF | Default iPhone photo format |
| TIFF | High-resolution scanner output |
| WEBP | Web-optimized image |

**Maximum file size:** 25 MB per file.

### Uploading a submission

1. Choose the **student**.
2. Choose the **assignment** from the dropdown.
3. Add the file:
   - **Drag and drop** onto the upload area
   - **Browse** to select a file from your device
   - **Use camera** (on mobile) to photograph paper work directly
4. Review the preview — confirm the page is fully visible and not cut off.
5. Select **Upload submission**.

### Mobile camera upload

Tapping **Use camera** on a phone opens the camera app and imports the photo directly into the upload flow. Tips for the best results:
- Lay the paper flat on a solid surface.
- Use good lighting — natural light or a bright room.
- Keep all four corners in frame.
- Avoid shadows across the writing.

A clear, well-lit photo produces significantly better OCR accuracy, which means faster automatic grading.

### Resubmitting

If you need to replace a poor-quality upload:
1. Open the submission.
2. Upload a new file.

The system keeps **all versions** but uses the newest one for grading. Version history is visible in the submission detail panel.

### Submission status

After upload, the submission panel shows:
- **Version number** (1.0, 2.0, etc.)
- **File details** (size, type, timestamp)
- **Grading progress bar**
- **Confidence score** (0–100%) — how sure the AI is about its result
- **Manual review reason** — why it was flagged, if applicable

---

## AI / OCR Processing Pipeline

Homeschool Hero can process uploaded work automatically. The pipeline runs in the background after upload.

### Processing stages

```
Uploaded → OCR processing → OCR complete → AI grading → Review needed / Final
```

| Stage | What happens |
|---|---|
| **Pending** | File received, processing queued |
| **OCR processing** | Text is being extracted from the image |
| **OCR complete** | Text extracted, ready for grading |
| **AI grading** | Text compared against answer key |
| **Review needed** | AI confidence is low, or no answer key exists — needs human |
| **Reviewed** | A human has approved or overridden the AI result |
| **Final** | Grade is locked and flows to the grade book |

### When AI works best

- The uploaded image is clear and well-lit.
- An answer key is attached to the assignment.
- Answers are short and unambiguous (fill-in, multiple choice, short answer).

### When manual review happens

- Confidence score is below the threshold.
- No answer key is attached.
- The OCR could not reliably read the handwriting.
- The answer requires judgment (open-ended response).

Every AI-graded item is flagged for parent review until you approve it. The AI is an accelerator, not the final authority.

---

## Quizzes

Go to **Assignments & Grading → Quizzes**.

The built-in quiz tool is for structured, auto-scored assessments taken on screen (or with a parent entering responses).

### Building a quiz

1. Enter a title.
2. Optionally assign a subject (links the score to the gradebook).
3. Add questions. Supported types:

| Question type | Description |
|---|---|
| **Multiple choice** | 2–5 answer options, one correct |
| **True / False** | Binary choice |
| **Short answer** | Free text — auto-scored by exact match or keyword |

4. For each question, set the point value.
5. Save the quiz.

Quizzes can be reused across students and grading periods.

### Running a quiz session

1. Choose the **student**.
2. Choose the **quiz**.
3. Enter responses — the student can type answers, or a parent reads the quiz aloud and enters them.
4. Submit the quiz.
5. Multiple-choice and true/false questions are scored automatically. Short-answer questions may route to the review queue.

The score is added to the grade book immediately for auto-scored questions.

---

## Review Queue

Go to **Assignments & Grading → Review Queue**.

The review queue is where everything that needs a human goes — low-confidence AI results, manually submitted work without an answer key, and open-ended quiz responses.

### What you see in the queue

Each item shows:
- Student name
- Assignment title and subject
- Submission date
- AI confidence score
- Priority flag (high-priority items surface first)

### Filtering the queue

| Filter | Options |
|---|---|
| Status | Pending review, reviewed, all |
| Priority | High, normal |
| Student | Any specific student |
| Subject | Any subject |
| Search | Keyword search across titles |

### Reviewing an item

Select any item to open the review panel. You see:
- **Uploaded image** — the student's actual work
- **OCR transcript** — what the system read from the image
- **AI feedback** — the AI's interpretation and suggested score
- **Confidence score** — how certain the AI was (0–100%)
- **Answer key** — the correct answers for comparison
- **Reviewer notes** — your private notes
- **Comments** — visible to other reviewers (co-parent, tutor)

### Your actions

| Action | When to use it |
|---|---|
| **Approve** | AI result is correct — accept the score |
| **Re-grade** | Override with a manual score |
| **Reject / request resubmission** | Work is incomplete, illegible, or wrong file |
| **Assign to reviewer** | Route to a co-parent or tutor |
| **Add comment** | Leave a note for a collaborator |

### Bulk actions

When you have a stack of similar items:
1. Use the filter to narrow to the group.
2. Select multiple items.
3. Choose **Bulk approve** or **Bulk assign**.

Bulk approve is useful at end of week for a set of routine assignments you have spot-checked.

---

## Grade Book

Go to **Assignments & Grading → Grade Book**.

The grade book aggregates all graded work into the clearest possible summary of how each student is performing.

### What the grade book shows

| View | What you see |
|---|---|
| **Summary** | GPA, overall average, attendance rate |
| **By subject** | Average, percentage, letter grade per subject |
| **By category** | Homework average, quiz average, test average — with weights |
| **Trend chart** | Score history over the grading period |
| **Assignment list** | Every graded item with score, max, and running total |

### Using the grade book

1. Choose a **student**.
2. Optionally filter by **subject** to focus on one course.
3. Optionally filter by **grading period** (fall semester, Q2, etc.).
4. Review subject cards — each shows the weighted average, letter grade, and category breakdown.
5. Expand a subject card to see individual assignment scores.
6. Select **Recalculate** to refresh if you have just approved items in the review queue.

### Category weighting

Each subject's grade is calculated from its categories (Homework, Quiz, Test) with the weights you set during subject setup. Example:
- Homework: 20%
- Quiz: 30%
- Test: 50%

The grade book applies these weights automatically and shows you both the raw average and the weighted result.

### Drop-lowest rule

If you set a "drop lowest" count on a category, the grade book removes that many lowest scores before calculating the average. Useful for weekly homework categories where one bad day should not heavily penalize a student.

### Letter grades

Letter grades are derived from your family's grade scale (or a subject-specific override). The scale maps percentage ranges to letters (A, B, C, etc.) and GPA point values.

---

## Grading Workflow: End-to-Week Routine

A practical routine for processing a week's worth of work:

1. **Upload** all paper assignments from the week (or confirm students have uploaded their own).
2. Wait a minute — OCR and AI grading run in the background.
3. Open **Review Queue** and filter to "Pending review."
4. Work through the queue: approve clean AI results, re-grade anything that looks off, reject any illegible scans.
5. Open **Grade Book** and select **Recalculate** to refresh all averages.
6. Glance at each subject card — anything unexpected is worth investigating before the week ends.
