# Phase 3 — `docx` skill

**Parent spec:** [`artifacts-overhaul.md`](./artifacts-overhaul.md) (§7.1 skills, §8 rendering).
**Depends on:** phase 2 complete (sandbox live, `pdf` skill shipped, binary `save_artifact` path proven, `preview_path` already accepted by the tool). The verification-loop mechanism — its contract, the tool-level input limits, and step rendering — is phase 2 §2.6; this phase adds a format skill that uses it and builds none of it.
**Goal:** Word documents, verified, plus the preview-PDF pairing and the office-skill conventions that phases 4 and 5 inherit rather than reinvent.
**Ships to users:** "make me a Word doc" produces a real `.docx` with an inline preview.

---

## 1. Scope

In: the `docx` skill, the shared office-skill conventions (§2.1) the next two phases build on, the first live use of the `role=preview` file, and `PdfPreviewViewer` with its docx registry entry.

Out: `pptx` (phase 4), `xlsx` and the unviewable/download-card polish (phase 5), any deletion (phase 6).

**This is the first of three format phases (3 docx → 4 pptx → 5 xlsx).** Only phase 4's dependency on this one is real — it reuses `PdfPreviewViewer` and the preview pairing proven here. Phase 5 depends on nothing but phase 2 and is sequenced last because it carries the cumulative gates (all four formats, a clean legacy-tool roster) that clear phase 6.

---

## 2. Tasks

### 2.1 Office-skill conventions (established here, referenced by phases 4 and 5)

All three office skills follow the pdf skill's structure (frontmatter triggers, body ≤ ~500 lines, its own `{skills_root}/<name>/scripts/`, and the phase 2 §2.6 contract — each skill states whether it verifies visually or programmatically). None of them restates "never save before verifying", and none of them describes how to revise: phase 2 moved the first invariant into `save_artifact` and the second into `load_artifact_source`, both of them format-blind, so a skill body covers only how to render evidence for its format and what to look for in it. Revision costs these skills nothing to support — each already writes a generate script, that script is what `source_path` stores, and editing it back is the same operation whether it produces a workbook or a deck. Self-contained means self-contained: a skill carries its own copies rather than reaching into a sibling's `scripts/`.

### 2.2 Skill — `docx`

Create with `docx` (npm, Node; preinstalled — instruct `require('docx')` directly, never `npm install`). Body encodes the known footguns (from Anthropic's publicly documented toolchain, authored fresh):

- US Letter vs A4 default; DXA page dimensions
- One page setup for the entire document: a single page size, portrait, and no section break that changes either. Content too wide for portrait is narrowed (column widths, font size), never rotated — genuinely wide tabular data is an xlsx, not a landscape Word page. Every generated document therefore has uniform pages, which the preview PDF and its viewers can rely on
- Tables: `columnWidths` **and** per-cell `width`, both `WidthType.DXA` (PERCENTAGE breaks in Google Docs); shading `ShadingType.CLEAR` never `SOLID`
- Lists via `numbering` config + `LevelFormat.BULLET`, never literal `•`
- `PageBreak` inside a `Paragraph`; separate `Paragraph`s, never `\n`
- TOC requires built-in `HeadingLevel.*` or explicit `outlineLevel`
- Right-aligned-on-same-line via right tab stop (**not** `PositionalTab` — renders as a small gap in LibreOffice, which is what our preview and verification see)
- Verify: the phase 2 §2.6 loop unchanged — measurable checks, `soffice --headless --convert-to pdf`, `pdftoppm`, then `inspect_sandbox_images` over every page and again with `mode="together"`. A docx reflows like a PDF, so it is generated whole, never page by page
- Save: `save_artifact(path=out.docx, source_path=out.js, preview_path=out.pdf, …)`

### 2.3 Frontend — rendering

- `PdfPreviewViewer`: a thin wrapper around the existing `pdf-viewer.tsx` (relocated in phase 2) pointed at the **preview** file's `content_url`, registered for the docx MIME type. No download action inside the viewer — the panel header already serves the primary file (master spec §8.1). It differs from `PdfFileViewer` only in which file's URL it renders, which is why phase 4 adds pptx as a registry line and no component.
- No per-format work on the in-chat card or the unviewable state: both derive their label from the filename extension, so docx is covered the day the skill lands.

### 2.4 Prompt & routing

- Subagent prompt: genre → format guidance and the Level 1 roster gain the docx entry (prose documents, letters, anything the user names as Word). Forgetting the roster entry fails the phase 2 §2.6 check rather than shipping a skill nothing advertises.
- Streaming/tool-UI: nothing new (the generic `save_artifact` handler covers all formats by design).

### 2.5 Checks

- Integration test as **one new row** in the phase 2 §2.7 harness, not a new file: generate → verify loop ran (trace shows per-page inspection) → master spec §3.1 payload with correct roles → renders per the §8.3 matrix → a later-turn change revises in place, one document, source read back rather than rebuilt. A format that needs its own test file has lost the generality phase 2 built, and this is the first phase that can prove it either way.
- Preview pairing, exercised end to end for the first time: a docx artifact returns two files with roles `primary` and `preview` (plus `source`, omitted from the `editor-content` payload per phase 2 §2.3); deleting the document purges both blobs.

---

## 3. Exit criteria

1. `docx` generates, verifies, persists, renders in `PdfPreviewViewer`, and downloads the real `.docx` exactly per master spec §8.3.
2. The preview pairing holds: two blobs out, both purged on delete, and the source file never surfaces as a user download.
3. A later-turn revision edits the stored generate script in place — same `document_id`, no sibling document.
