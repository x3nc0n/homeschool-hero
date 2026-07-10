# Skill: Android-Compatible File Input (sr-only + ref-click)

## Problem

Android Chrome and many Android WebView builds **silently ignore `display:none` file `<input>` elements**. When a file/camera input is hidden via CSS `display:none` (Tailwind class `hidden`) and activated by clicking a `<Label htmlFor="...">` wrapper, the OS picker never opens. The click event fires but is swallowed. This is a well-known Android limitation.

## Solution Pattern

Use `className="sr-only"` on the bare HTML `<input>` element (NOT the shadcn `Input` component), attach a `ref`, and trigger it programmatically from a `<Button onClick>`.

### Code

```tsx
import { useRef } from 'react'
import { Button } from '@/components/ui/button'
import { FileText, Camera } from 'lucide-react'

// Refs declared alongside other component refs:
const fileInputRef = useRef<HTMLInputElement | null>(null)
const cameraInputRef = useRef<HTMLInputElement | null>(null)

// In JSX:
{/* File inputs use sr-only, NOT display:none — Android Chrome silently ignores
    display:none file inputs so the OS picker never opens. sr-only keeps them
    reachable in the DOM while remaining visually hidden. */}
<input
  ref={fileInputRef}
  id="file-upload"
  type="file"
  className="sr-only"
  accept=".pdf,.jpg,.jpeg,.png,.heic,.heif,.tif,.tiff,.webp,application/pdf,image/jpeg,image/png,image/heic,image/heif,image/tiff,image/webp"
  onChange={(event) => void onFileChange(event.target.files?.[0])}
/>
<input
  ref={cameraInputRef}
  id="camera-upload"
  type="file"
  className="sr-only"
  accept="image/jpeg,image/png,image/heic,image/heif,image/tiff,image/webp"
  capture="environment"
  onChange={(event) => void onFileChange(event.target.files?.[0])}
/>
<Button type="button" variant="secondary" onClick={() => fileInputRef.current?.click()}>
  <FileText className="mr-2 h-4 w-4" aria-hidden="true" />
  Choose file
</Button>
<Button type="button" variant="outline" onClick={() => cameraInputRef.current?.click()}>
  <Camera className="mr-2 h-4 w-4" aria-hidden="true" />
  Use camera
</Button>
```

## Rules

1. **Never** use `className="hidden"` (or any `display:none`) on a file `<input>`.
2. **Always** use `className="sr-only"` to keep the input in the DOM flow.
3. **Always** use a `useRef<HTMLInputElement | null>(null)` ref + `ref.current?.click()` trigger.
4. **Do not** wrap file inputs in `<Label htmlFor>` for visual button styling — use a separate `<Button onClick>` instead.
5. Use the native `<input>` element, NOT the shadcn `Input` component (which wraps the element and can interfere with the click dispatch).
6. The `onChange` handler for async file processors should use `void`: `onChange={(event) => void onFileChange(event.target.files?.[0])}`.

## Accessibility

`sr-only` is screen-reader accessible (unlike `display:none` / `visibility:hidden`). The pattern is compatible with keyboard navigation because the `<Button>` receives focus normally and calls `click()` on the input.

## Reference Implementation

`frontend/src/components/features/FileUpload.tsx` — PR #298 (reconciled onto main 2026-07-10).

## Platforms Tested

- Desktop browsers: Chrome, Firefox, Safari — works (same as before)
- Android Chrome / WebView — **fixed** (was broken with `display:none`)
- iOS Safari — works (iOS ignores capture attribute for camera; renders standard file picker)
