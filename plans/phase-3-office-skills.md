# Phase 3 — Office skills (docx, pptx, xlsx)

**Parent spec:** [`artifacts-overhaul.md`](./artifacts-overhaul.md) (§7.1 skills, §8 rendering).
**Depends on:** phase 2 complete (sandbox live, `pdf` skill shipped, binary `save_artifact` path proven).
**Goal:** the remaining launch formats, each with a verification loop, plus the preview-PDF pairing and office rendering.
**Ships to users:** "make me a Word doc / slide deck / spreadsheet" produces real files with inline preview (docx/pptx) or a download card (xlsx).

---

## 1. Scope

In: three skills, preview-PDF persistence (`role=preview`), `PdfPreviewViewer`, xlsx/unknown card polish, prompt demotion of legacy tools to "never use".

Out: any deletion (phase 4). Public-chat artifact rendering lands here if not already done (master spec §12 open question 1).

---

## 2. Tasks

### 2.1 Skills

All three follow the pdf skill's structure (frontmatter triggers, body ≤ ~500 lines, scripts in the image, mandatory verify-before-save).

**`docx`** — create with `docx` (npm, Node; preinstalled — instruct `require('docx')` directly, never `npm install`). Body encodes the known footguns (from Anthropic's publicly documented toolchain, authored fresh):

- US Letter vs A4 default; DXA page dimensions
- Tables: `columnWidths` **and** per-cell `width`, both `WidthType.DXA` (PERCENTAGE breaks in Google Docs); shading `ShadingType.CLEAR` never `SOLID`
- Lists via `numbering` config + `LevelFormat.BULLET`, never literal `•`
- `PageBreak` inside a `Paragraph`; separate `Paragraph`s, never `\n`
- TOC requires built-in `HeadingLevel.*` or explicit `outlineLevel`
- Right-aligned-on-same-line via right tab stop (**not** `PositionalTab` — renders as a small gap in LibreOffice, which is what our preview and verification see)
- Verify: `soffice --headless --convert-to pdf` → `pdftoppm` → inspect pages
- Save: `save_artifact(path=out.docx, preview_path=out.pdf, …)`

**`pptx`** — create with `python-pptx`. Body: slide dimensions, layout/placeholder usage, text overflow as the #1 failure to check visually, image sizing. Verify: soffice → pdf → per-slide rasterization → inspect every slide. Save with `preview_path`.

**`xlsx`** — create with `openpyxl`. Body: real formulas (not precomputed values) where the user asked for calculations, number formats, column widths, freeze panes, multi-sheet structure. Verify **programmatically, not visually**: reopen the file, recalculate (LibreOffice headless recalc), read back expected cells, assert. No preview file — `save_artifact(path=out.xlsx, …)` with primary only.

### 2.2 Frontend — rendering

- `PdfPreviewViewer` registry entries for the two office MIME types (docx, pptx): existing PDF viewer on the **preview** file's `content_url`; `toolbarActions` gets "Download {primary.filename}" hitting the primary URL.
- `FileDownloadCard` final polish: extension icon set, size formatting, hover states; this is the permanent home for xlsx and every unknown/future format.
- Artifact card badges for the three new MIME types.

### 2.3 Prompt & routing

- Subagent prompt: format-selection guidance covers all four formats; legacy `generate_report`/`generate_resume` marked "never use — kept only for backward compatibility until removal".
- Streaming/tool-UI: nothing new (generic `save_artifact` handler covers all formats by design).

### 2.4 Checks

- Per-skill integration test: generate → verify loop ran (trace shows page/cell inspection) → §3.1 payload with correct roles → renders per the §8.3 matrix.
- xlsx: formula cells recalculate correctly when opened in LibreOffice (automated via headless recalc + value assertions).
- Preview pairing: docx artifact returns two files; deleting the document purges both blobs.

---

## 3. Exit criteria

1. All four launch formats generate, verify, persist, render, and download exactly per the master spec §8.3 matrix.
2. An unknown format produced by the agent (e.g. `.csv` via pandas — no skill exists) persists and renders as a download card with no code changes — proving the expandability property.
3. No user-visible path routes to `generate_report`/`generate_resume` anymore (grep of prompts + observed routing), clearing the way for phase 4 deletion.
