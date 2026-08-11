# Phase 4 — `pptx` skill

**Parent spec:** [`artifacts-overhaul.md`](./artifacts-overhaul.md) (§7.1 skills, §8 rendering).
**Depends on:** phase 3 complete — `PdfPreviewViewer` exists and the preview-PDF pairing is proven, so this phase adds a skill and a registry line and nothing else. The verification-loop mechanism is phase 2 §2.6; the office-skill conventions every skill body follows are phase 3 §2.1.
**Goal:** slide decks, verified slide by slide and then as a set.
**Ships to users:** "make me a slide deck" produces a real `.pptx` with an inline preview.

---

## 1. Scope

In: the `pptx` skill, its `PdfPreviewViewer` registry entry, its roster entry, and one harness row.

Out: `xlsx` and the unviewable/download-card polish (phase 5), any deletion (phase 6).

**This is the phase that measures the architecture.** Everything a second preview-PDF format needs was built in phases 2 and 3; if pptx costs more than one skill directory, one registry line, one prompt entry, and one harness row, the generality claimed in those phases was not there.

---

## 2. Tasks

### 2.1 Skill — `pptx`

Create with `python-pptx`, following the phase 3 §2.1 conventions. Body: slide dimensions, layout/placeholder usage, text overflow as the #1 failure to check visually, image sizing.

Verify: `soffice` to PDF, per-slide rasterization, then the phase 2 §2.6 loop over the slides — every slide reviewed on its own, then compared with `mode="together"` for the font and colour drift that is invisible one slide at a time. Slides are independent — no reflow — so the skill builds and verifies incrementally rather than rendering all of them and checking at the end, and it is the format where the deferred hash-skip of master spec §12 would pay most.

Save: `save_artifact(path=out.pptx, source_path=out.py, preview_path=out.pdf, …)`.

### 2.2 Frontend — rendering

- One `PdfPreviewViewer` registry entry for the pptx MIME type. No new component: phase 3 built the viewer, and a deck's preview PDF is a PDF like any other.

### 2.3 Prompt & routing

- Subagent prompt: genre → format guidance and the Level 1 roster gain the pptx entry (slides, decks, presentations). Forgetting the roster entry fails the phase 2 §2.6 check rather than shipping a skill nothing advertises.

### 2.4 Checks

- One new row in the phase 2 §2.7 harness: generate → verify loop ran (trace shows per-slide inspection **and** a `mode="together"` comparison) → master spec §3.1 payload with correct roles → renders per the §8.3 matrix → a later-turn change revises in place from the stored script.
- Incremental verification is visible in the trace: slides are inspected as they are built, not all at the end — the assertion that distinguishes this skill's loop from docx's.

---

## 3. Exit criteria

1. `pptx` generates, verifies per-slide and together, persists, renders in `PdfPreviewViewer`, and downloads the real `.pptx` exactly per master spec §8.3.
2. The whole phase is one skill directory, one registry line, one prompt entry, and one harness row — no new viewer, no new test file, no backend change.
