# Phase 5 — `xlsx` skill + native grid

**Parent spec:** [`artifacts-overhaul.md`](./artifacts-overhaul.md) (§7.1 skills, §8.2 viewer registry).
**Depends on:** phase 2 complete, and on phase 3 only for the mocked-sandbox integration tests this phase adds a case to (§2.4). It does **not** depend on phases 3 and 4 for anything it ships — xlsx has no preview PDF, no visual verification, and no shared viewer with the office formats, so its product surface needs nothing but the sandbox and the binary `save_artifact` path. It is sequenced last because it carries the cumulative gates that clear phase 6, not because the code needs the two phases before it. The skill body follows the master spec §7.1 conventions; the verification contract is phase 2 §2.6.
**Goal:** spreadsheets, verified programmatically, rendered in a native read-only grid — and with them, the last of the four launch formats.
**Ships to users:** "make me a spreadsheet" produces a real `.xlsx` with live formulas and an inline spreadsheet grid.

---

## 1. Scope

In: the `xlsx` skill, `XlsxViewer` (ExcelJS + `ssf` native grid), the unknown-format/unviewable card polish, and public-chat artifact rendering if it has not already landed (master spec §12 open question 1 — it must land before phase 6 removes the Typst public preview).

Out: any deletion (phase 6).

---

## 2. Tasks

### 2.1 Skill — `xlsx`

Create with `openpyxl`, following the master spec §7.1 conventions. Body: real formulas (not precomputed values) where the user asked for calculations, number formats, header styling (fills/bold — it renders in the grid viewer), column widths, freeze panes, multi-sheet structure.

Verify **programmatically, not visually**: recalculate (LibreOffice headless recalc), read back expected cells, assert. There is nothing to rasterize and no vision call to make, so this skill is the measurable half of phase 2 §2.6 with the visual half absent — per-sheet iteration is a choice about assertion coverage, not about looking at anything. The §2.6 gate still applies, and this is the skill where getting its contract wrong is fatal rather than merely untidy: **a clean exit records nothing.** `execute` registers a verification only when the run's output carries `SURFSENSE_VERIFIED: <path>` (master spec §7.1), so the assertion script must print that token as its last act. With no `inspect_sandbox_images` call anywhere in this shape, it is the only thing that ever reaches the ledger, and an assertion script that passes silently produces a `save_artifact` refusal the model has no obvious way to read.

**The recalculated file is the file saved** — openpyxl writes formulas with no cached values and `XlsxViewer` renders cached values, so saving the raw openpyxl output renders blank formula cells; recalc is a rendering prerequisite, not just QA.

No preview file — `save_artifact(path=<workbook>.xlsx, source_path=<workbook>.py, …)`, primary and source only, deliverable-named rather than `out.*` (master spec §7.1). The source matters more here than anywhere: a workbook's formulas and formats are far easier to amend in the openpyxl script than to reconstruct from a markdown outline of what the sheet contained.

### 2.2 Frontend — `XlsxViewer`

- Registry entry for the spreadsheet MIME type, lazy-loaded via `next/dynamic`: fetch the **primary** file's `content_url` (existing authenticated-fetch pattern, ETag-cached) → parse in-browser with ExcelJS (MIT — values, fills, fonts, borders, merged ranges, column widths, sheet list) → format display text with `ssf` (Apache-2.0, number-format strings → rendered text) → read-only virtualized grid with column letters, row numbers, and sheet tabs. Row-capped for huge sheets ("showing N of M rows — download for full data"); parse failure or oversize falls through to the panel's unviewable state, never an error. Charts, conditional-formatting rules, and pivot tables are out of scope (grid, not an Excel emulator — master spec §8.2). New frontend deps: `exceljs`, `ssf`.
- Unviewable/download-card polish: both the in-chat card and the unviewable state derive their label from the filename extension, so this is the polish pass on a path three formats already exercise — not per-format work. It is also the fallback the xlsx checks below drive into.

### 2.3 Prompt & routing

- Subagent prompt: genre → format guidance and the Level 1 roster gain the xlsx entry (tabular data, calculations, budgets, anything the user names as a spreadsheet). With this entry the roster covers all four launch formats.
- Phase 2 already unregistered `generate_report`/`generate_resume`; their files, routes, and table stay for phase 6 so historical tool-call parts keep rendering through the export window. What this phase closes is the *routing* question: with four formats advertised, no genre falls through to a legacy tool, which is exit criterion 4.

### 2.4 Checks

- One new case in the mocked-sandbox integration tests (phase 3 §2.5), parameters rather than a new file: master spec §3.1 payload with correct roles (primary + source, **no** preview), the gate refusing a workbook regenerated after its last verification and accepting it once the assertion script has printed the sentinel again, and a later-turn revise in place from the stored script. With this case the tests cover every launch format as parameters; a format that needed its own file would have shown the leak by now. The sentinel assertion is the one that matters most here — it is the only verification signal this format produces at all.
- Formula cells recalculate correctly when opened in LibreOffice (automated via headless recalc + value assertions).
- Render: a generated workbook renders in `XlsxViewer` with formatted number text (e.g. `"$#,##0.00"` → `"$10,413.00"`), visible header fill, and **non-blank formula cells** — this catches a skipped recalc end-to-end. A corrupt or oversized xlsx falls back to the download card, not an error. Both are Playwright or by-hand checks: `surfsense_web` has no component-test framework (master spec §8.3), and the only part of this viewer a unit test can reach cheaply is the `ssf` formatting pulled out as a plain function.
- Expandability: an unknown format the agent produces with no skill behind it (e.g. `.csv` via pandas) persists and renders as a download card with **no code changes**.

---

## 3. Exit criteria

1. `xlsx` generates, verifies programmatically, persists (primary + source), renders in `XlsxViewer` with formatted values and non-blank formula cells, and downloads the real `.xlsx` per master spec §8.3.
2. All four launch formats generate, verify, persist, render, and download exactly per the master spec §8.3 matrix.
3. An unknown format produced by the agent persists and renders as a download card with no code changes — proving the expandability property.
4. No user-visible path routes to `generate_report`/`generate_resume` anymore (grep of prompts + observed routing), clearing the way for phase 6 deletion.
