---
name: xlsx
description: Create polished Excel workbooks for budgets, trackers, and data tables.
---

# XLSX

Author the workbook with `xlsxwriter`, saving to a `BytesIO` opened with
`{"in_memory": True}`. XlsxWriter is preferred because it writes the explicit
formula caches the in-browser grid needs.

## Authoring rules

- Prefer one clear purpose per worksheet. Name sheets for their content, not
  `Sheet1` / `Sheet2`.
- Set column widths deliberately. Freeze header rows when tables are scrolled.
- Style headers once (bold, fill, borders) and reuse the format objects. Prefer
  number formats (`#,##0.00`, `0%`, dates) over pre-formatted strings.
- Write formulas with **both** the formula string and a computed cached value:
  `worksheet.write_formula("B2", "=A2*1.1", fmt, 110)`. The grid shows the cache
  rather than recalculating, so a missing cache renders blank.
- Never leave Excel error literals (`#DIV/0!`, `#REF!`, `#VALUE!`, `#N/A`) as
  cached results. Fix the formula or the inputs instead.
- Keep workbooks compact — prefer tight tables over giant empty ranges.
- Charts, pivot tables, macros, and VBA are out of scope; stick to values,
  formulas, formats, panes, and multiple sheets.
