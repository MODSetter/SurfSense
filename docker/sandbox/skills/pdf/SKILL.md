---
name: pdf
description: Create polished PDF files for requests such as PDFs, resumes, CVs, reports, letters, one-pagers, and printable documents.
---

# PDF

Create the requested PDF in `/workspace`. Everything required is preinstalled;
never run `pip install`, `npm install`, or download dependencies.

## Choose the renderer

- Use **WeasyPrint** for typography-heavy documents authored naturally as
  HTML/CSS: resumes, CVs, letters, one-pagers, and styled reports.
- Use **ReportLab** for programmatic layouts, drawing, charts, coordinates, or
  documents assembled directly from Python data.
- Use A4 unless the user or source context implies US Letter. Use margins of at
  least 18 mm (0.7 in), 10–11 pt body text, and 1.3–1.5 line height.
- Available families include DejaVu, Liberation, and Noto (including CJK).
  Prefer Liberation Sans/Serif for office-style documents and Noto for broad
  Unicode coverage.

Write deterministic source alongside the output (`.py` or `.html`) so defects
can be fixed without rebuilding from scratch. Escape untrusted text before
placing it in HTML.

## Required quality gate

Do not call `save_artifact` until every step passes:

1. Generate the PDF.
2. Run `/opt/skills/pdf/scripts/render_pages.sh out.pdf /tmp/pdf-pages`.
3. Call `inspect_sandbox_images` with instructions to check clipping, overflow,
   blank pages, alignment, legibility, visual hierarchy, and factual
   consistency. Up to four pages, pass every path in one call — page breaks in a
   PDF depend on everything above them, so seeing the pages together is what
   catches "this should be one page, not two". Beyond four, inspect one page per
   call so each report names one fixable defect, then make a final call over a
   sample — first page, last page, and any page you changed, at most 20 paths —
   to catch drift in fonts, spacing, and page count.
4. If a report identifies any defect, edit the source, regenerate, render, and
   inspect again.
5. Run `/opt/skills/pdf/scripts/check_pdf.py out.pdf` for structural checks.
6. Only then call:
   `save_artifact(path="out.pdf", title="...", markdown_representation="...")`.

The Markdown representation must faithfully contain the document's substantive
text so the artifact remains accessible and searchable without parsing the PDF.
