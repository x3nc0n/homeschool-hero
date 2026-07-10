---
name: "sequential-form-lock"
description: "Lock a later form step until earlier steps are complete — especially important for mobile camera capture flows."
domain: "frontend/ux"
confidence: "high"
source: "earned"
---

## Context

Use this when a multi-step form has a step that should only become interactive after prerequisite steps are complete. The canonical case is mobile file upload: a parent can open the camera, take a photo, and *then* see a validation error asking them to fill in earlier fields — at which point the photo is gone. Locking the file zone until prerequisites are done prevents this data-loss scenario.

## Pattern

Compute a `ready` boolean from all prerequisite fields:

```tsx
const readyForFile = Boolean(selectedStudent && selectedAssignment)
```

Use conditional render — **not** `disabled` props on a wrapper — to control whether interactive elements inside the locked zone are present in the DOM:

```tsx
{!readyForFile ? (
  <>
    <Lock className="mx-auto mb-2 h-7 w-7 text-muted-foreground/40" aria-hidden="true" />
    <p id="file-zone-hint" className="text-sm text-muted-foreground">
      {t('upload.stepZoneLocked')}  {/* "Choose a student and assignment first" */}
    </p>
  </>
) : (
  <> {/* full dropzone content, file inputs, camera button */} </>
)}
```

Also guard drag events:

```tsx
onDragOver={(e) => { if (!readyForFile) return; e.preventDefault(); setIsDragging(true) }}
onDrop={(e) => { e.preventDefault(); if (!readyForFile) return; ... }}
```

## Accessibility

- Do **not** put `aria-disabled` on a container with `role="region"` — jsx-a11y will error. Conditional render is the correct technique.
- When locked, the zone content is replaced by descriptive text (the hint). Screen readers encounter that text and understand why the zone is inactive.
- Pair with a `StepIndicator` row so sighted users also understand the sequence.

## Step Progress Indicator

```tsx
type StepState = 'done' | 'current' | 'upcoming'

function StepIndicator({ num, state, label }: { num: number; state: StepState; label: string }) {
  return (
    <div className="flex flex-col items-center gap-1.5">
      <div className={`flex h-8 w-8 items-center justify-center rounded-full text-xs font-semibold transition-colors ${
        state === 'done' ? 'bg-primary text-primary-foreground' :
        state === 'current' ? 'border-2 border-primary text-primary' :
        'border-2 border-muted-foreground/30 text-muted-foreground/50'
      }`} aria-hidden="true">
        {state === 'done' ? <Check className="h-4 w-4" /> : num}
      </div>
      <span className={`text-center text-xs leading-tight ${
        state === 'done' ? 'font-medium text-primary' :
        state === 'current' ? 'font-medium text-foreground' :
        'text-muted-foreground/60'
      }`}>{label}</span>
    </div>
  )
}
```

Use numbered indicators only when the steps are a genuine required sequence — not as decorative scaffolding (impeccable absolute-ban on reflexive numbered eyebrows).

## Examples

- `frontend/src/components/features/FileUpload.tsx` — `readyForFile` lock on file zone, `StepIndicator` row for 3-step upload flow.
