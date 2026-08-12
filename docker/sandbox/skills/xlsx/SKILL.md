---
name: xlsx
description: Create polished Excel workbooks for budgets, trackers, tables, and explicit .xlsx spreadsheet requests.
---

# XLSX

Create the requested workbook in `/workspace` with the preinstalled
`xlsxwriter` package. Never install or download dependencies. Do not use
openpyxl to author deliverables; XlsxWriter writes complete formula caches that
verification and the browser grid require.

Use one deliverable-derived stem for deterministic Python source and output, for
example `budget.py` and `budget.xlsx`. The source must regenerate the complete
workbook so later revisions edit rather than reconstruct it.

## Authoring rules

- Prefer one clear sheet purpose per worksheet. Name sheets for the user, not
  `Sheet1` / `Sheet2`, unless the request is a blank template.
- Set column widths deliberately. Freeze header rows when tables are scrolled.
- Style headers once (bold, fill, borders) and reuse the style objects. Prefer
  number formats (`#,##0.00`, `0%`, dates) over pre-formatted strings.
- Write formulas with **both** the formula string and a computed cached value:
  `worksheet.write_formula("B2", "=A2*1.1", cell_format, 110)`. Verification
  rejects formula cells that lack a cached result, and the in-browser grid
  shows the cache rather than recalculating.
- Also call `workbook.set_calc_mode("auto")` (or the equivalent recalculation
  on open) so Excel/LibreOffice recompute when the file is opened.
- Never leave Excel error literals (`#DIV/0!`, `#REF!`, `#VALUE!`, `#N/A`, …)
  as cached results. Fix the formula or the inputs instead.
- Keep workbooks under the verification cell ceiling (100 000 cells). Prefer
  compact tables over giant empty ranges.
- Charts, pivot tables, macros, and VBA are out of scope for this skill. Stick
  to values, formulas, formats, panes, and multiple sheets.

When revising, `load_artifact_source` returns the existing `artifact_id` and a
`source_path` with a name such as `artifact-42-budget.py`. Copy that source to
`budget.py` before editing so the `artifact-42-` prefix does not compound, then
pass the returned `artifact_id` to `save_artifact`. A changed title, filename,
or design is still the same artifact unless the user explicitly asks for a
separate copy.

## Verify and save

Call `verify_artifact(path="budget.xlsx")`. Spreadsheet verification is
structural only: there is no PDF preview and no vision pass. Warnings are
advisory. If it reports blocking findings, fix them in the Python source and
regenerate once. Reverify that revision; if a blocker remains, stop and explain
it instead of entering another automatic rewrite loop.

Then call `save_artifact` with the XLSX path and Python source path only — omit
`preview_path`. The Markdown representation must faithfully summarize the
workbook's sheets, column meanings, and key figures for accessibility and
search.
