---
target: frontend/src/pages/UploadPage.tsx
total_score: 23
p0_count: 1
p1_count: 2
timestamp: 2026-07-10T19-36-59Z
slug: frontend-src-pages-uploadpage-tsx
---
⚠️ DEGRADED: single-context (no isolated sub-agent tool invoked; assessment A and B run inline)

---

## Design Health Score — UploadPage + FileUpload

| # | Heuristic | Score | Key Issue |
|---|-----------|-------|-----------|
| 1 | Visibility of System Status | 3 | Upload progress bar, grading progress bar, version badges all present |
| 2 | Match System / Real World | 2 | Grading status labels ("ocr processing", "ai grading", "ai complete") are technical jargon post-replace |
| 3 | User Control and Freedom | 3 | Cancel resubmission button, back navigation, error retry |
| 4 | Consistency and Standards | 2 | Student/assignment must be selected before file pick but no step indicator; sequence is implicit |
| 5 | Error Prevention | 2 | File type validation present; but no guard preventing the drop zone from being used before selectors are filled |
| 6 | Recognition Rather Than Recall | 2 | Allowed file types are in a static block that will be scrolled past; camera button present but visually equal to file-browse |
| 7 | Flexibility and Efficiency | 3 | Drag-and-drop, camera capture, file browse, resubmit flow all present |
| 8 | Aesthetic and Minimalist Design | 2 | Upload form + current submissions list + detail panel all on one page; context split |
| 9 | Error Recovery | 3 | Error messages present, retry on load failure |
| 10 | Help and Documentation | 1 | No guided first-upload experience; no explanation of OCR/AI grading pipeline for parents |
| **Total** | | **23/40** | **Acceptable — significant improvements needed** |

---

## Anti-Patterns Verdict

**LLM assessment**: The upload page's most critical anti-pattern is sequence ambiguity — the form reads top-to-bottom but the most important action (choosing a file) is not obviously the final step. On mobile (the primary device for the student upload use case), the submission list below the upload card is never in view while uploading. The grading status pipeline uses back-end state machine labels that leak through the `replace(/_/g, ' ')` transform without becoming parent-readable.

**Deterministic scan**: 0 findings.

---

## Overall Impression

The upload mechanism itself is well-built (camera capture, drag-and-drop, file-sig validation, progress tracking). The problem is page architecture: a page that should be a focused 3-step task (1. Who is this for? 2. What assignment? 3. Attach the photo) instead presents as a multi-panel information hub. Students uploading from a phone will see the upload form, succeed, and then scroll into a confusing "Current submissions" / "Submission detail" panel below.

## What's Working

1. **Camera capture** — `capture="environment"` on the file input is the single most important UX decision on this page for the student use case. It works correctly.
2. **Grading progress bar** — staged progress values per grading status give meaningful feedback ("this is still being processed") vs a spinner.
3. **Resubmit flow** — the version history + resubmit workflow is clearly thought through and preserves history correctly.

## Priority Issues

**[P0] Implicit upload sequence — student can interact with drop zone before selecting student/assignment**
- **What**: The drop zone is rendered below the student/assignment selectors with no step labeling. A student can drop a file (or open the camera) immediately, triggering `onFileChange` with no student or assignment selected. They'll only get an error on submit, not on drop.
- **Why it matters**: Mobile students in a hurry will tap the camera icon first — it's the most visually prominent control in the drop zone. The error "Please choose a student, assignment, and file" appears after they've already captured their photo. If the capture was camera-only, the photo is now lost (mobile cameras don't save to gallery when captured via web API by default).
- **Fix**: Disable (or visually lock) the file/drop zone until both selectors are filled. Add step numbers or a subtle stepper (1. Select student → 2. Select assignment → 3. Attach photo). Show the drop zone in a muted/disabled state with "Choose student and assignment first."
- **Suggested command**: `/impeccable onboard frontend/src/components/features/FileUpload.tsx`

**[P1] Technical grading status labels reaching the parent**
- **What**: Status values like `ocr_processing`, `ai_grading`, `ai_complete`, `review_needed` are transformed to "ocr processing", "ai grading", etc. These are still technical terms.
- **Why it matters**: A parent seeing "ocr processing" for their child's math test has no idea what that means or whether they need to do anything. "Review needed" is better but still ambiguous — review by whom?
- **Fix**: Map status values to parent-readable strings: `ocr_processing` → "Reading your file…", `ai_grading` → "AI is scoring this…", `review_needed` → "Needs your review", `final` → "Grade finalized". Apply this mapping in a shared utility used across UploadPage and SubmissionDetail.
- **Suggested command**: `/impeccable clarify frontend/src/pages/UploadPage.tsx`

**[P1] Upload form + submissions list + detail all on one page — context collision**
- **What**: The upload card, current submissions list, and submission detail panel are all visible on the same scroll-connected page. A parent uploading new work can see their previous submissions in the list, click one by accident, and suddenly the detail panel updates — making it unclear whether their upload succeeded.
- **Why it matters**: The upload success state (`latestSubmission`) and the selected-submission state (`selectedSubmissionId`) are separate and can conflict visually.
- **Fix**: For the student upload use case, make the page strictly sequential: upload form → success confirmation with submission ID and status → then "view past submissions" is a secondary tab or link. For parents managing submissions, the list+detail split view may be appropriate but should be clearly labeled as "Manage submissions" rather than mixed with the upload form.
- **Suggested command**: `/impeccable distill frontend/src/pages/UploadPage.tsx`

**[P2] Submission detail panel hidden on tablet (collapses only at xl)**
- **What**: `grid gap-4 xl:grid-cols-[0.95fr_1.05fr]` — the side-by-side layout only activates at 1280px+. Between 768px and 1280px (common tablet landscape), the two panels stack vertically. The detail panel is completely below the fold after the submissions list.
- **Why it matters**: Parents reviewing submissions on an iPad see the list but have to scroll past it to find the detail panel below — and the relationship between list item and detail is lost without the side-by-side layout.
- **Fix**: Change breakpoint to `lg:grid-cols-[…]` or restructure as a stacked master-detail with a clear visual connection (e.g., the selected item in the list is highlighted and an arrow/chevron points to the detail below).
- **Suggested command**: `/impeccable adapt frontend/src/pages/UploadPage.tsx`

## Persona Red Flags

**Student on phone (Maria, 14, submitting a math test)**: Opens Upload page on mobile. Sees "Submit student work" card. Taps the camera icon immediately (most prominent control). Captures photo. Then realizes she needs to scroll up and pick "Student" and "Assignment." Tries to re-attach the photo — but the camera capture already closed. Frustrated. Uploads a second time from gallery.

**Parent checking upload status (Jordan)**: After student uploads, navigates to Upload page to check progress. Sees the upload form first (purpose mismatch — they're here to check status, not upload). Has to scroll down to "Current submissions" and find the right item. Status shows "ocr processing" — doesn't know if this means it's fine or if they need to do something.

## Minor Observations
- The `rounded-lg border bg-muted/20 p-3 text-sm` "Allowed types" block at the top of FileUpload is the first visible element after the card header. It's an information wall that users will skip. Move this to a `?` icon tooltip on the drop zone.
- "Choose file" and the camera button are rendered as `Button type="button"` inside a `Label htmlFor`. This works but is semantically odd — the Label is acting as a button wrapper, which can confuse screen readers.
- The `Progress` bar goes from 0 to 100 on upload, then separately grading progress is a different bar. Two different progress bars on the same surface with no clear labels distinguishing them.

## Questions to Consider
- What if the Upload page was a wizard (3 steps: Student → Assignment → Attach) rather than a form? Would this reduce the sequential ambiguity?
- Should the Upload page exist separately from the Assignments page — could "upload work" be an action within the assignment detail, keeping the context together?
