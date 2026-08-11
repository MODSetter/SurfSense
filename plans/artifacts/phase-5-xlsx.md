# Phase 5 — `xlsx` skill + native grid

**Parent spec:** [`artifacts-overhaul.md`](./artifacts-overhaul.md) (§6.3 the verification loop, §7.1 skills, §8.2 viewer registry).
**Depends on:** phase 2, and now on phase 3 for the verification service its adapter registers with (plus the mocked-sandbox integration tests it adds a case to, §2.4). Nothing in its *product* surface comes from phases 3 and 4 — xlsx has no preview PDF, no visual verification, and no shared viewer with the office formats — so it remains sequenceable against anything after phase 3, and is placed last because it carries the cumulative gates that clear phase 6. The skill body follows master spec §7.1.
**Goal:** spreadsheets, verified programmatically, rendered in a native read-only grid — and with them, the last of the four launch formats.
**Ships to users:** "make me a spreadsheet" produces a real `.xlsx` with live formulas and an inline spreadsheet grid.

---

## 1. Scope

In: the `xlsx` skill and its verification adapter, `XlsxViewer` (ExcelJS + `ssf` native grid), the unknown-format/unviewable card polish, and public-chat artifact rendering if it has not already landed (master spec §12 open question 1 — it must land before phase 6 removes the Typst public preview).

Out: any deletion (phase 6).

---

## 2. Tasks

### 2.1 Skill — `xlsx`

Create with `openpyxl`, following the master spec §7.1 conventions. Body: real formulas (not precomputed values) where the user asked for calculations, number formats, header styling (fills/bold — it renders in the grid viewer), column widths, freeze panes, multi-sheet structure.

Verified **programmatically, not visually**, and the shape is the service's (master spec §6.3): `formats/xlsx.py` registers as a non-converting format, so `verify_artifact` recalculates the workbook headless in place, reads the expected cells back, and issues a receipt whose visual verdict is *not applicable to this format*. Nothing is rasterized and no vision call is made. The skill body says nothing about any of it — the same one call it would make for a PDF.

This is the format where the old design's contract was most dangerous and where the new one costs nothing: under the sentinel-and-ledger scheme (phase 2 §2.6) a silent assertion script recorded nothing, so a passing verification produced a save refusal the model had no way to read, and this shape had no vision call to fall back on. A receipt is written by the service or not at all, so there is nothing left to forget.

**The recalculated file is the file saved** — openpyxl writes formulas with no cached values and `XlsxViewer` renders cached values, so the raw openpyxl output renders blank formula cells. Recalc is a rendering prerequisite, not just QA, and the receipt is what enforces it: it hashes the workbook the service recalculated, so bytes that skipped the recalc cannot pass the gate.

No preview file — `save_artifact(path=<workbook>.xlsx, source_path=<workbook>.py, …)`, primary and source only, deliverable-named rather than `out.*` (master spec §7.1). The source matters more here than anywhere: a workbook's formulas and formats are far easier to amend in the openpyxl script than to reconstruct from a markdown outline of what the sheet contained.

### 2.2 Frontend — `XlsxViewer`

- Registry entry for the spreadsheet MIME type, lazy-loaded via `next/dynamic`: fetch the **primary** file's `content_url` (existing authenticated-fetch pattern, ETag-cached) → parse in-browser with ExcelJS (MIT — values, fills, fonts, borders, merged ranges, column widths, sheet list) → format display text with `ssf` (Apache-2.0, number-format strings → rendered text) → read-only virtualized grid with column letters, row numbers, and sheet tabs. Row-capped for huge sheets ("showing N of M rows — download for full data"); parse failure or oversize falls through to the panel's unviewable state, never an error. Charts, conditional-formatting rules, and pivot tables are out of scope (grid, not an Excel emulator — master spec §8.2). New frontend deps: `exceljs`, `ssf`.
- Unviewable/download-card polish: both the in-chat card and the unviewable state derive their label from the filename extension, so this is the polish pass on a path three formats already exercise — not per-format work. It is also the fallback the xlsx checks below drive into.

### 2.3 Prompt & routing

- Subagent prompt: genre → format guidance and the Level 1 roster gain the xlsx entry (tabular data, calculations, budgets, anything the user names as a spreadsheet). With this entry the roster covers all four launch formats.
- Phase 2 already unregistered `generate_report`/`generate_resume`; their files, routes, and table stay for phase 6 so historical tool-call parts keep rendering through the export window. What this phase closes is the *routing* question: with four formats advertised, no genre falls through to a legacy tool, which is exit criterion 4.

### 2.4 Checks

- Unit tests for the adapter's cell-readback assertions, and one new case in the mocked-sandbox integration tests (phase 3 §3.6), parameters rather than a new file: master spec §3.1 payload with correct roles (primary + source, **no** preview), a receipt with no preview hash accepted for this format, the gate refusing bytes that do not match the receipt, and a later-turn revise in place from the stored script. With this case the tests cover every launch format as parameters; a format that needed its own file would have shown the leak by now.
- Formula cells recalculate correctly when opened in LibreOffice (automated via headless recalc + value assertions).
- Render: a generated workbook renders in `XlsxViewer` with formatted number text (e.g. `"$#,##0.00"` → `"$10,413.00"`), visible header fill, and **non-blank formula cells** — this catches a skipped recalc end-to-end. A corrupt or oversized xlsx falls back to the download card, not an error. Both are Playwright or by-hand checks: `surfsense_web` has no component-test framework (master spec §8.3), and the only part of this viewer a unit test can reach cheaply is the `ssf` formatting pulled out as a plain function.
- Expandability: an unknown format the agent produces with no skill behind it (e.g. `.csv` via pandas) persists and renders as a download card with **no code changes**.

---

## 3. Exit criteria

1. `xlsx` generates, verifies programmatically, persists (primary + source), renders in `XlsxViewer` with formatted values and non-blank formula cells, and downloads the real `.xlsx` per master spec §8.3.
2. All four launch formats generate, verify, persist, render, and download exactly per the master spec §8.3 matrix.
3. An unknown format produced by the agent persists and renders as a download card with no code changes — proving the expandability property.
4. No user-visible path routes to `generate_report`/`generate_resume` anymore (grep of prompts + observed routing), clearing the way for phase 6 deletion.
