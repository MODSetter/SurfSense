# Phase 5 — `xlsx` skill + native grid

**Parent spec:** [`artifacts-overhaul.md`](./artifacts-overhaul.md) (§6.3 the verification loop, §7.1 skills, §8.2 viewer registry).
**Depends on:** phase 2, and on phase 3 for the verification service its adapter registers with (plus the mocked-sandbox integration tests it adds a case to, §2.7). Nothing in its *product* surface comes from phases 3 and 4 — xlsx has no preview PDF, no visual verification, and no shared viewer with the office formats — so it remains sequenceable against anything after phase 3, and is placed last because it carries the cumulative gates that clear phase 6. The skill body follows master spec §7.1.
**Goal:** spreadsheets, verified programmatically, rendered in a read-only grid — and with them, the last of the four launch formats.
**Ships to users:** "make me a spreadsheet" produces a real `.xlsx` with live formulas and an inline spreadsheet grid.

---

## 1. Scope

In: the format-general work a non-rendered format needs (§2.1), the `xlsx` skill and its adapter, `XlsxViewer`, and public-chat artifact rendering (master spec §12 open question 1 — it must land before phase 6 removes the Typst public preview).

Out: any deletion (phase 6).

Four slices, each shippable alone: format-general verification (§2.1), skill + adapter (§2.2–2.3), viewer (§2.4), public-chat rendering (§2.6). Only the first two are ordered relative to each other; §2.1 ships and is tested before any xlsx exists.

---

## 2. Tasks

### 2.1 Format-general — two pipelines, and a registry that answers for every format

Phase 4 made the *rendered* policy adapter-owned. xlsx is the first format that renders nothing, and two seams do not survive it unchanged.

**`FormatAdapter` gains a pipeline, not a fifth flag.** The four rendering knobs (`convert_to_pdf`, `rendered_min_chars`, `expects_exact_page_count`, `review_kind`) move into a `RenderedPolicy` that is `None` for a programmatic format, so a format that is never rasterized cannot also declare a visual review kind. `_verify_artifact` splits immediately after the structural check: with no rendered policy it writes the receipt and returns — `visual="not_required"` (the verdict the receipt schema has carried unused since phase 3), no page count, no preview. That branch is also what removes the current failure mode, where a page-less format dies on the `page_count is None` ceiling check written for paginated ones. Adding the axis as a fifth boolean instead would leave three fields whose meaning depends on it, silently, in the struct every later format copies.

**`get_format_adapter` becomes total.** It raises today on an unregistered suffix, and `save_artifact` calls it for every primary file — so an agent-produced `.csv` cannot be saved at all. That is the persistence layer enumerating formats, against master spec §1.2's fourth principle, and it is why exit criterion 3 fails by construction rather than by omission. An unregistered suffix instead resolves to a **generic adapter**: non-empty and within the size cap, no rendered policy, canonical MIME `application/octet-stream`. `verify_artifact` then works on anything and issues a real receipt, and `save_artifact` keeps its single universal rule — no binary is saved without one — with no format branch anywhere in persistence. Octet-stream is deliberate over guessing with `mimetypes`: a MIME comes from an adapter or not at all, so the viewer registry cannot match a guess and the download route's inline allowlist (PDF only, and commented as an XSS boundary) never sees a type it might render. A `.csv` therefore verifies, persists, and renders as a download card labelled from its filename extension, with no code changes — which is the expandability property being claimed rather than assumed.

### 2.2 Skill — `xlsx`

Create with **XlsxWriter** (BSD-2-Clause, pure Python, zero dependencies), following the master spec §7.1 conventions. Body: real formulas where the user asked for calculations, number formats, header styling (fills/bold — it renders in the grid viewer), column widths, freeze panes, multi-sheet structure.

**Every formula is written with its computed result.** `write_formula(row, col, formula, fmt, value)` stores that value in the cell's `<v>` cache beside the formula in `<f>`, and XlsxWriter separately sets the workbook's recalculate-on-load flag so Excel and LibreOffice recompute on open. The skill derives each cached value from the same data that produced the range it sums, in the same script, one line apart.

That convention is what makes this format need no recalculation step, and it is the phase's one significant departure from the earlier plan. openpyxl writes a formula *or* a value, never both, so an openpyxl workbook reaches the viewer with every formula cell blank (§8.2 renders cached values). Closing that gap meant a service that recalculates the workbook headless **in place** — and that would have made verification a step that rewrites the artifact it is checking: a new invariant inherited by every later format, an async session-carrying hook forced into an adapter contract that is otherwise pure `bytes -> StructuralCheckResult`, and a failed run able to leave a half-transformed file behind. The same guarantee is available as a **property of the file** instead of a process the service performs: a workbook whose formula cells carry no cached value is rejected (§2.3). That cannot be skipped, needs no mutation, and reads identically for every format that comes later. Generation produces complete files; verification only ever inspects them.

Verified programmatically, and the shape is the service's (master spec §6.3): nothing is rasterized and no vision call is made, while the skill body says nothing about any of it — the same one call it would make for a PDF.

No preview file — `save_artifact(path=<workbook>.xlsx, source_path=<workbook>.py, …)`, primary and source only, deliverable-named rather than `out.*` (master spec §7.1). The source matters more here than anywhere: a workbook's formulas and formats are far easier to amend in the generating script than to reconstruct from a markdown outline of what the sheet contained. XlsxWriter being write-only costs nothing for the same reason — a revision re-runs the stored script rather than reopening the workbook, exactly as docx and pptx already do.

### 2.3 Adapter — `formats/xlsx.py`

Reuses `formats/ooxml.py`'s trust boundary (phase 4 §2.2) with `xl/workbook.xml` as the required part, then checks what OOXML can answer reliably:

- at least one sheet, and at least one non-empty cell;
- every cell carrying `<f>` also carries `<v>` — the rendering prerequisite, and the gate a workbook that skipped §2.2's convention cannot pass;
- no cached value is an Excel error literal (`#REF!`, `#DIV/0!`, `#NAME?`, `#VALUE!`, `#NULL!`, `#NUM!`, `#N/A`) — precisely the set XlsxWriter's `value` parameter accepts, so this is a value a generating script can really produce;
- total cell count within a ceiling. This is the xlsx analogue of the page ceiling and it bounds the browser parse downstream, not a vision spend. The viewer's row cap is a display decision and no substitute: a cap applied after parsing cannot bound parsing.

Registers suffix `.xlsx`, canonical MIME `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`, and `rendered=None`. Stdlib `zipfile` + `xml.etree`, as `formats/pptx.py` already uses.

The adapter does **not** claim that a cached value equals what Excel would compute from the formula string — nothing short of a calculation engine can, and the two credible Python engines are copyleft (`formulas` is EUPL-1.2, `pycel` GPL-3.0) in an image we distribute. Three things bound the exposure: the skill writes both from one expression, the recalculate-on-load flag means Excel and LibreOffice correct any drift the moment the user opens the file, and the arithmetic subset that is cheaply checkable (`SUM`/`AVERAGE`/`COUNT`/`MIN`/`MAX` over a contiguous same-sheet range) can be cross-checked in the adapter later without changing any signature. Deferred, not overlooked.

### 2.4 Frontend — `XlsxViewer`

Registry entry for the spreadsheet MIME type, lazy-loaded via `next/dynamic`: fetch the **primary** file's `content_url` (existing authenticated-fetch pattern, ETag-cached) → parse in-browser with **ExcelJS** → format display text with **`ssf`** → read-only grid with column letters, row numbers, and sheet tabs. Row-capped for large sheets ("showing N of M rows — download for full data"); parse failure or oversize falls through to the panel's unviewable state, never an error. Charts, conditional-formatting rules, and pivot tables are out of scope (grid, not an Excel emulator — master spec §8.2). New frontend deps: `exceljs`, `ssf`.

Three constraints on how it is built, each answering a way this viewer could go wrong later:

- **ExcelJS never appears outside one module.** A `parseWorkbook(bytes): WorkbookView` boundary returns sheets, cells with display text, and the handful of style bits the grid renders; the component imports that, not ExcelJS. It is the only part of this viewer a unit test can reach cheaply (master spec §8.3 — `surfsense_web` has no component-test framework), and it is what makes the 10.6 KB fallback in §2.4's evidence a one-file swap rather than a rewrite. Carries a `ponytail:` comment naming the ceiling — whole workbook in memory, no streaming — and that upgrade path.
- **Size is checked before the viewer mounts.** `size_bytes` is already in the manifest; above the threshold the panel goes straight to the download card. A row cap cannot help here, because the rows must be parsed before they can be capped, and `wb.xlsx.load()` is CPU-bound enough to jank the main thread on a large sheet.
- **No grid dependency and no editing surface.** A capped plain `<table>` with `content-visibility: auto` on rows needs no virtualizer; `@tanstack/react-table` is installed but is a headless data table (sorting, filtering, pagination), which is the wrong shape for a fixed spreadsheet grid. Nothing from Plate, Monaco, Handsontable, Univer, or Luckysheet goes near this: it is a renderer with no edit path to disable, per master spec §8.4.

**Evidence for keeping ExcelJS** (re-measured 2026-08-12 with esbuild, minified, `platform=browser`, gzipped, since the spec's original choice predates several new entrants): ExcelJS 270 KB — against `xlsx-js-style` 347 KB (npm release frozen at 2022-04), SheetJS CE 335 KB (cell styling is Pro-only), `@extend-ai/react-xlsx` 723 KB plus a 4.3 MB WASM package (created 2026-04, 15 stars, bundles `regl` and four `d3-*` packages for charts this viewer does not render), `xlsx-preview` 275 KB (ExcelJS plus an HTML-string renderer; its GitHub repo 404s), and `@file-viewer/renderer-spreadsheet` (seven weeks old, canvas grid — no text selection, no copy, no find-in-page). Lighter options exist only by giving something up: `read-excel-file` is 14 KB but exposes no styles, and `fflate` + `ssf` is 10.6 KB but means owning a parser. ExcelJS is dormant (last release 4.4.0, 2023-10; last commit 2025-01; 800 open issues) and that is the accepted cost — it is MIT, 13.2M weekly downloads, has no live advisory (its only one, GHSA-2j2j-8rrv-264g, was fixed in 1.6.0 in 2018), and it only ever parses workbooks this system generated, which is the long tail those open issues are made of. `ssf` is still required: ExcelJS exposes `numFmt` as a raw string and has no engine to render `10413` + `"$#,##0.00"` as `"$10,413.00"`.

Also rejected, because it is otherwise attractive: having the backend emit a JSON grid as the preview file, giving the viewer zero parsing dependencies. It reuses the existing preview role and receipt hash, and it would put format knowledge in the backend where §1.2 says it belongs — but it freezes rendering fidelity at generation time, so a viewer improvement would never reach an artifact already made, and it adds a second blob per artifact to a system whose storage accounting is still open (master spec §12, question 3).

### 2.5 Prompt & routing

The genre → format guidance and the Level 1 roster gain the xlsx entry (tabular data, calculations, budgets, anything the user names as a spreadsheet), in the four places the pptx entry occupies: the deliverables subagent's `system_prompt.md` and `description.md`, and the main agent's `routing.md` and `identity/team.md`. With this entry the roster covers all four launch formats, and `tests/unit/sandbox/test_deliverables_skill_roster.py` enforces the pairing by set equality — an installed skill nothing advertises fails the build, as does the reverse.

Phase 2 already unregistered `generate_report`/`generate_resume`; their files, routes, and table stay for phase 6 so historical tool-call parts keep rendering through the export window. What this phase closes is the *routing* question: with four formats advertised, no genre falls through to a legacy tool, which is exit criterion 4.

### 2.6 Public-chat artifact rendering

Master spec §12's first open question, deferred in phase 1 and due here. A token-scoped variant of the §5 content route (share token → thread → the artifacts that thread produced) returning the identical response shape, plus a panel that takes its query options from a provider instead of reading `activeWorkspaceIdAtom` directly. The viewer registry, the viewers, and the download button are untouched — forking the panel would mean maintaining two copies of every future viewer's wiring.

### 2.7 Checks

- Unit tests for the adapter: clean workbooks, a formula cell with no cached value, each error literal, zero sheets, an all-empty sheet, the cell ceiling, and the OOXML defects `ooxml.py` already covers.
- Unit tests for the split pipeline: a programmatic adapter produces a `not_required` receipt with no preview and no page count, and never calls the renderer; a rendered adapter is unchanged.
- One new case in the mocked-sandbox integration tests (phase 3 §3.6), parameters rather than a new file: master spec §3.1 payload with correct roles (primary + source, **no** preview), a receipt with no preview hash accepted, the gate refusing bytes that do not match the receipt, and a later-turn revise in place from the stored script. The shared helper takes an optional preview, which is the one shape change phase 4 §6 did not anticipate.
- An unknown-format save round trip (`.csv` bytes → generic adapter → receipt → persisted → `application/octet-stream`), proving exit criterion 3 without xlsx involved.
- Formula cells recalculate correctly when opened in LibreOffice (automated via headless recalc + value assertions) — the delivered file's behaviour in a real spreadsheet application, which the cached-value convention does not by itself prove.
- Render: a generated workbook renders in `XlsxViewer` with formatted number text (e.g. `"$#,##0.00"` → `"$10,413.00"`), visible header fill, and **non-blank formula cells**. A corrupt or oversized xlsx falls back to the download card, not an error. Both are Playwright or by-hand checks (master spec §8.3); `parseWorkbook` and the `ssf` formatting are plain functions and are unit-tested as such.
- Expandability: an unknown format the agent produces with no skill behind it (e.g. `.csv` via pandas) persists and renders as a download card with **no code changes**.

---

## 3. Exit criteria

1. `xlsx` generates, verifies programmatically, persists (primary + source), renders in `XlsxViewer` with formatted values and non-blank formula cells, and downloads the real `.xlsx` per master spec §8.3.
2. All four launch formats generate, verify, persist, render, and download exactly per the master spec §8.3 matrix.
3. An unknown format produced by the agent persists and renders as a download card with no code changes — proving the expandability property.
4. No user-visible path routes to `generate_report`/`generate_resume` anymore (grep of prompts + observed routing), clearing the way for phase 6 deletion.
5. Share-token visitors see and download a thread's artifacts, so phase 6 can remove the Typst public preview without losing a surface.
