# Phase 4 — `pptx` skill

**Parent spec:** [`artifacts-overhaul.md`](./artifacts-overhaul.md) (§7.1 skills, §8 rendering).
**Depends on:** phase 3 complete — `PdfPreviewViewer` exists and the preview-PDF pairing is proven, so this phase adds a skill and a registry line and nothing else. The verification-loop mechanism is phase 2 §2.6; the skill conventions every body follows are master spec §7.1.
**Goal:** slide decks, verified slide by slide and then as a set.
**Ships to users:** "make me a slide deck" produces a real `.pptx` with an inline preview.

---

## 1. Scope

In: the `pptx` skill, its `PdfPreviewViewer` registry entry, its roster entry, and one integration-test case.

Out: `xlsx` and the unviewable/download-card polish (phase 5), any deletion (phase 6).

**This is the phase that measures the architecture.** Everything a second preview-PDF format needs was built in phases 2 and 3; if pptx costs more than one skill directory, one registry line, one prompt entry, and one test case, the generality claimed in those phases was not there.

---

## 2. Tasks

### 2.1 Skill — `pptx`

Create with `python-pptx`, following the master spec §7.1 conventions. Body: slide dimensions, layout/placeholder usage, text overflow as the #1 failure to check visually, image sizing.

Verify: `soffice` to PDF, per-slide rasterization, then the phase 2 §2.6 loop over the slides — every slide reviewed on its own, then compared with `mode="together"` for the font and colour drift that is invisible one slide at a time. Slides are independent — no reflow — so the skill builds and verifies incrementally rather than rendering all of them and checking at the end, and it is the format where the deferred hash-skip of master spec §12 would pay most. Incremental rebuilds make the §7.1 two-hop rule sharper here than in docx, not softer: a deck reconverts many times per run, so a stale preview PDF has that many chances to slip through as this round's evidence. Delete the PDF and the slide renders, reconvert with a private profile and explicit `--outdir`, assert the result is non-empty and newer than the `.pptx`.

Save: `save_artifact(path=<deck>.pptx, source_path=<deck>.py, preview_path=<deck>.pdf, …)` — deliverable-named, never `out.*` (master spec §7.1).

### 2.2 Frontend — rendering

- One `PdfPreviewViewer` registry entry for the pptx MIME type. No new component: phase 3 built the viewer, and a deck's preview PDF is a PDF like any other.

### 2.3 Prompt & routing

- Subagent prompt: genre → format guidance and the Level 1 roster gain the pptx entry (slides, decks, presentations). Forgetting the roster entry fails the phase 2 §2.6 check rather than shipping a skill nothing advertises.

### 2.4 Checks

- One new case in the mocked-sandbox integration tests phase 3 added under `tests/integration/artifacts/` — parameters, not a new file: primary + preview + source with the master spec §3.1 roles, the gate refusing a `.pptx` regenerated after its last verification, and a later-turn revise in place from the stored script. No sandbox and no model, so it runs in CI. If pptx needs its own test file, the phase 2 §2.6 boundary leaked and the test says where.
- Incremental verification — slides inspected as they are built rather than all at the end, and a `mode="together"` pass over the set — is the one assertion that distinguishes this skill's loop from docx's, and the one that needs a live model to observe. It is checked in the exit-criteria walk-through against a real sandbox, not in CI.

---

## 3. Exit criteria

1. `pptx` generates, verifies per-slide and together, persists, renders in `PdfPreviewViewer`, and downloads the real `.pptx` exactly per master spec §8.3.
2. The whole phase is one skill directory, one registry line, one prompt entry, and one integration-test case — no new viewer, no new test file, no backend change.
