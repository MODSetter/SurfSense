# Phase 3 — Office skills (docx, pptx, xlsx)

**Parent spec:** [`artifacts-overhaul.md`](./artifacts-overhaul.md) (§7.1 skills, §8 rendering).
**Depends on:** phase 2 complete (sandbox live, `pdf` skill shipped, binary `save_artifact` path proven). The verification-loop mechanism — its contract, the tool-level input limits, and step rendering — is phase 2 §2.6; this phase adds format skills that use it and builds none of it.
**Goal:** the remaining launch formats, each with a verification loop, plus the preview-PDF pairing and office rendering.
**Ships to users:** "make me a Word doc / slide deck / spreadsheet" produces real files with inline preview for all three — docx/pptx via the preview PDF, xlsx via a native read-only spreadsheet grid.

---

## 1. Scope

In: three skills, preview-PDF persistence (`role=preview`), `PdfPreviewViewer`, `XlsxViewer` (ExcelJS + ssf native grid), unknown-format card polish, prompt demotion of legacy tools to "never use".

Out: any deletion (phase 4). Public-chat artifact rendering lands here if not already done (master spec §12 open question 1).

---

## 2. Tasks

### 2.1 Skills

All three follow the pdf skill's structure (frontmatter triggers, body ≤ ~500 lines, its own `{skills_root}/<name>/scripts/`, and the phase 2 §2.6 contract — each skill states whether it verifies visually or programmatically). None of them restates "never save before verifying": phase 2 moved that invariant into `save_artifact`, so a skill body covers only how to render evidence for its format and what to look for in it. Self-contained means self-contained: a skill carries its own copies rather than reaching into a sibling's `scripts/`.

**`docx`** — create with `docx` (npm, Node; preinstalled — instruct `require('docx')` directly, never `npm install`). Body encodes the known footguns (from Anthropic's publicly documented toolchain, authored fresh):

- US Letter vs A4 default; DXA page dimensions
- Tables: `columnWidths` **and** per-cell `width`, both `WidthType.DXA` (PERCENTAGE breaks in Google Docs); shading `ShadingType.CLEAR` never `SOLID`
- Lists via `numbering` config + `LevelFormat.BULLET`, never literal `•`
- `PageBreak` inside a `Paragraph`; separate `Paragraph`s, never `\n`
- TOC requires built-in `HeadingLevel.*` or explicit `outlineLevel`
- Right-aligned-on-same-line via right tab stop (**not** `PositionalTab` — renders as a small gap in LibreOffice, which is what our preview and verification see)
- Verify: the phase 2 §2.6 loop unchanged — measurable checks, `soffice --headless --convert-to pdf`, `pdftoppm`, then `inspect_sandbox_images` over every page and again with `mode="together"`. A docx reflows like a PDF, so it is generated whole, never page by page
- Save: `save_artifact(path=out.docx, preview_path=out.pdf, …)`

**`pptx`** — create with `python-pptx`. Body: slide dimensions, layout/placeholder usage, text overflow as the #1 failure to check visually, image sizing. Verify: soffice to PDF, per-slide rasterization, then the phase 2 §2.6 loop over the slides — every slide reviewed on its own, then compared with `mode="together"` for the font and colour drift that is invisible one slide at a time. Slides are independent — no reflow — so the skill builds and verifies incrementally rather than rendering all of them and checking at the end, and it is the format where the deferred hash-skip of master spec §12 would pay most. Save with `preview_path`.

**`xlsx`** — create with `openpyxl`. Body: real formulas (not precomputed values) where the user asked for calculations, number formats, header styling (fills/bold — it renders in the grid viewer), column widths, freeze panes, multi-sheet structure. Verify **programmatically, not visually**: recalculate (LibreOffice headless recalc), read back expected cells, assert. There is nothing to rasterize and no vision call to make, so this skill is the measurable half of §2.6 with the visual half absent — per-sheet iteration is a choice about assertion coverage, not about looking at anything. The §2.6 gate still applies: the assertion script's clean exit is this skill's verification. **The recalculated file is the file saved** — openpyxl writes formulas with no cached values and `XlsxViewer` renders cached values, so saving the raw openpyxl output renders blank formula cells; recalc is a rendering prerequisite, not just QA. No preview file — `save_artifact(path=out.xlsx, …)` with primary only.

### 2.2 Frontend — rendering

- `PdfPreviewViewer` registry entries for the two office MIME types (docx, pptx): existing PDF viewer on the **preview** file's `content_url`; `toolbarActions` gets "Download {primary.filename}" hitting the primary URL.
- `XlsxViewer` registry entry for the spreadsheet MIME type, lazy-loaded via `next/dynamic`: fetch the **primary** file's `content_url` (existing authenticated-fetch pattern, ETag-cached) → parse in-browser with ExcelJS (MIT — values, fills, fonts, borders, merged ranges, column widths, sheet list) → format display text with `ssf` (Apache-2.0, number-format strings → rendered text) → read-only virtualized grid with column letters, row numbers, and sheet tabs. Row-capped for huge sheets ("showing N of M rows — download for full data"); parse failure or oversize falls through to `FileDownloadCard`, never an error. Charts, conditional-formatting rules, and pivot tables are out of scope (grid, not an Excel emulator — master spec §8.2). New frontend deps: `exceljs`, `ssf`.
- `FileDownloadCard` final polish: extension icon set, size formatting, hover states; this is the permanent home for every unknown/future format and the xlsx parse-failure/oversize fallback.
- Artifact card badges for the three new MIME types.

### 2.3 Prompt & routing

- Subagent prompt: genre → format guidance and the Level 1 roster cover all four formats (slides → pptx, tabular → xlsx, and so on). Forgetting a roster entry fails the phase 2 §2.6 check rather than shipping a skill nothing advertises. Legacy `generate_report`/`generate_resume` marked "never use — kept only for backward compatibility until removal".
- Streaming/tool-UI: nothing new (generic `save_artifact` handler covers all formats by design).

### 2.4 Checks

- Per-skill integration test, parameterizing the phase 2 §2.7 harness rather than rebuilding it: generate → verify loop ran (trace shows page/cell inspection) → §3.1 payload with correct roles → renders per the §8.3 matrix.
- xlsx: formula cells recalculate correctly when opened in LibreOffice (automated via headless recalc + value assertions).
- xlsx render: a generated workbook renders in `XlsxViewer` with formatted number text (e.g. `"$#,##0.00"` → `"$10,413.00"`), visible header fill, and **non-blank formula cells** — this catches a skipped recalc end-to-end. A corrupt or oversized xlsx falls back to the download card, not an error.
- Preview pairing: docx artifact returns two files; deleting the document purges both blobs.

---

## 3. Exit criteria

1. All four launch formats generate, verify, persist, render, and download exactly per the master spec §8.3 matrix.
2. An unknown format produced by the agent (e.g. `.csv` via pandas — no skill exists) persists and renders as a download card with no code changes — proving the expandability property.
3. No user-visible path routes to `generate_report`/`generate_resume` anymore (grep of prompts + observed routing), clearing the way for phase 4 deletion.
