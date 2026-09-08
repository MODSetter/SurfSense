---
name: pdf
description: Create polished PDF documents such as reports, letters, one-pagers, and printable summaries.
---

# PDF

Author the PDF with `reportlab`, then get its bytes. Prefer the Platypus
flowable API (`SimpleDocTemplate` over a `BytesIO`, with `Paragraph`, `Table`,
`Spacer`, and `getSampleStyleSheet`) over hand-placed canvas coordinates.

## Authoring rules

- Use A4 unless US Letter is implied. Use margins of at least 18 mm (0.7 in),
  10–11 pt body text, and 1.3–1.5 line height.
- Structure the document with a title, headings, justified body text, and
  tables built from `Table`/`TableStyle` where the data invites them.
- ReportLab's `Paragraph` parses a small XML markup, so escape `&`, `<`, and `>`
  in any source text (`xml.sax.saxutils.escape`) before placing it.
- The built-in fonts (Helvetica, Times) are Latin-1 only. For broader Unicode,
  register a TrueType font with `pdfmetrics.registerFont(TTFont(...))` if one is
  available; otherwise keep the text within Latin-1.
- Do not embed `Page X of Y` folios; the viewer supplies its own page indicator.
- Build to a `BytesIO` and read the bytes back; do not write a file to disk.
