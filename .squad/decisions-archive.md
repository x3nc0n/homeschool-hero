# Archive: Decisions from v0.15.0 Release Cycle (2026-07-10)

Archived on 2026-10-06T10:25:55Z. Original dates in each section.

---

# Release Decision: v0.15.0 — UI Overhaul (PR #305)

**Date:** 2026-07-10T21:01:47Z  
**Author:** Coordinator  
**Status:** COMPLETE

## Summary

PR #305 "UI Overhaul via Impeccable" was merged to main via squash commit (32dbd7c). Version v0.15.0 was tagged and released.

## Decisions

- Merge strategy: squash commit (clean history, single changeset)
- Release promotion: v0.15.0 tagged on main; GitHub Release created; GHCR image published (ghcr.io/x3nc0n/homeschool-hero:v0.15.0 and :latest)
- Dependabot PRs: 14 PRs flagged for auto-merge (squash, delete-branch); #267 rebased to start the cascade
- Skipped for later: #268 (Tailwind 3→4), #288 (action-gh-release), #289 (checkout 6→7) — all have failing tests and need dedicated migrations

## Rationale

- Squash merge keeps main clean while preserving PR history for reference
- Auto-merge on safe dependabot bumps reduces manual overhead
- Blocking high-risk migrations (Tailwind, action versions) until they can be properly scoped and tested

---

# Decision: Skip Tailwind CSS 3→4 Migration (PR #268)

**Date:** 2026-07-10T21:01:47Z  
**Author:** Coordinator  
**Status:** PENDING MIGRATION

## Decision

PR #268 (tailwindcss 3→4) is **flagged but not merged**. The upgrade is a breaking change and introduces test failures that require a dedicated migration effort.

## Rationale

- Tailwind 4 is a major version with breaking changes to config and class names
- Current PR #268 has failing tests and is not production-ready
- Scope creep: bundling with v0.15.0 release would delay other dependency bumps
- Dedicated migration PR will ensure thorough refactoring, testing, and documentation

## Next Steps

- Create a new PR for Tailwind 4 migration targeting post-v0.15.0
- Coordinate with Venkman on component class name changes
- Add migration guide to squad decisions for future reference

---

# Decision: Android File Input Pattern — sr-only over display:none

**Date:** 2026-07-10T21:01:47Z  
**Author:** Venkman  
**Context:** PR #298 reconciliation onto main after PR #305 merge

## Decision

All file/camera <input> elements in the frontend **must** use className="sr-only" (not display:none / Tailwind hidden) and be triggered via ef.current?.click() from a plain <Button onClick>.

The old pattern of <Label htmlFor="..."><Input className="hidden" .../><Button tabIndex={-1}>...</Button></Label> is **deprecated** for file inputs.

## Rationale

Android Chrome and WebView silently ignore display:none file inputs — the OS file/camera picker never opens. sr-only keeps the input reachable in the DOM while remaining visually hidden, making it work on Android without breaking other platforms.

## Scope

rontend/src/components/features/FileUpload.tsx is the reference implementation. Apply this pattern to any future file-input component in the project.

## Related

- PR #296 / PR #298 — original Android upload bug report and fix
- PR #305 — UI overhaul that introduced step-lock; created the merge conflict
- Skill: .squad/skills/android-file-input/SKILL.md

---

# Decision: PR #298 Reconciliation — Android Fix onto Overhaul

**Date:** 2026-07-10T21:01:47Z  
**Author:** Venkman  
**PR:** #298, #305

## Context

PR #298 ("Fix assignment turn-in file upload & camera on Android") was opened against the original FileUpload.tsx, but PR #305 (UI overhaul) merged a refactored FileUpload.tsx first. A merge conflict resulted, requiring reconciliation.

## Decision

**Resolve by combining both changes**: main's step-lock + canvas security logic + #298's Android sr-only inputs + ref.current.click() buttons. The Label/hidden-Input pattern is dropped in favor of sr-only + direct button click handling.

## Rationale

- Both PRs improve FileUpload.tsx: #305 adds step progression logic and security hardening; #298 fixes Android file picker
- Combining ensures users get both security improvements and platform compatibility
- sr-only pattern is more robust than hidden for input accessibility across all platforms

## Result

- Force-push to squad/296-android-upload with combined changes
- Build + lint passed
- Auto-merge enabled; PR merged into main

---
