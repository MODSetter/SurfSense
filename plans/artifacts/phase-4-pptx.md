# Phase 4 — `pptx` skill

**Parent spec:** [`artifacts-overhaul.md`](./artifacts-overhaul.md) (§6.3 the verification loop, §7.1 skills, §8 rendering).
**Depends on:** phase 3 complete — the verification service exists and `PdfPreviewViewer` with it, so this phase adds one adapter, one skill body and one registry line. The skill conventions every body follows are master spec §7.1.
**Goal:** slide decks, verified slide by slide and then as a set.
**Ships to users:** "make me a slide deck" produces a real `.pptx` with an inline preview.

---

## 1. Scope

In: the `pptx` skill, its structural adapter in the verification service, its `PdfPreviewViewer` registry entry, its roster entry, and one integration-test case.

Out: `xlsx` and the unviewable/download-card polish (phase 5), any deletion (phase 6).

**This is the phase that measures the architecture.** Everything a second office format needs was built in phases 2 and 3; if pptx costs more than one adapter, one skill body, one registry line, one prompt entry and one test case, the generality claimed in those phases was not there.

---

## 2. Tasks

### 2.1 Adapter — `formats/pptx.py`

The structural checks that read the OOXML directly, registered as a PDF-converting format (phase 3 §3.1 is the pattern, and registering is the whole of what the service needs to know: the conversion, the rasterize, the review, the page ceiling and the receipt are format-blind already). What is measurable in a deck's markup: text boxes whose content cannot fit their frame at the given font size, placeholders left empty, images scaled outside their frame, slide dimensions inconsistent across the deck. Text overflow is the #1 pptx failure and it is exactly the class that a vision pass reports vaguely ("this slide looks crowded") and the markup reports precisely.

### 2.2 Skill — `pptx`

Create with `python-pptx`, following master spec §7.1. Body: slide dimensions, layout and placeholder usage, text overflow as the failure to design against, image sizing — authoring guidance only, since verification and revision belong to the tools (§7.1).

Slides are independent — no reflow — so the skill builds and verifies **incrementally** rather than generating the whole deck and checking at the end. That is the one thing this skill's shape does differently from docx's, and it is a property of generation, not of verification: `verify_artifact` behaves identically whether it is called on a three-slide draft or a thirty-slide deck. It is also the format where master spec §12's deferred hash-skip would pay most, precisely because a slide that did not change did not move.

Save: `save_artifact(path=<deck>.pptx, source_path=<deck>.py, preview_path=<the returned preview>, …)` — deliverable-named, never `out.*` (master spec §7.1).

### 2.3 Frontend — rendering

- One `PdfPreviewViewer` registry entry for the pptx MIME type. No new component: phase 3 built the viewer, and a deck's preview PDF is a PDF like any other.
- Register the OOXML presentation MIME with `mimetypes.add_type` beside phase 3's docx entry, for the reason master spec §8.2 gives: without it the stored type is `application/zip` and this registry line silently never matches.

### 2.4 Prompt & routing

- Subagent prompt: genre → format guidance and the Level 1 roster gain the pptx entry (slides, decks, presentations). Forgetting the roster entry fails the installed-frontmatter check rather than shipping a skill nothing advertises.

### 2.5 Checks

- Unit tests for the adapter against fixture bytes — an overflowing text box, an empty placeholder, a clean deck — which is the whole of what this phase adds to CI, and is possible at all because the checks are functions rather than a script in the image.
- One new case in the mocked-sandbox integration tests phase 3 added under `tests/integration/artifacts/` — parameters, not a new file: primary + preview + source with the master spec §3.1 roles, the gate refusing bytes that do not match the receipt, and a later-turn revise in place from the stored script. No sandbox and no model, so it runs in CI. If pptx needs its own test file, the phase 3 boundary leaked and the test says where.
- Incremental generation — slides checked as they are built — needs a live model to observe and is checked in the exit-criteria walk-through against a real sandbox, not in CI.

---

## 3. Exit criteria

1. `pptx` generates, verifies per-slide and together, persists, renders in `PdfPreviewViewer`, and downloads the real `.pptx` exactly per master spec §8.3.
2. The whole phase is one adapter, one skill body, one registry line, one prompt entry and one integration-test case — no new viewer, no new test file, no change to the verification service itself.
