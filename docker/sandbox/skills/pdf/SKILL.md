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

`save_artifact` rejects a PDF that changed after its last inspection, so this
loop is not optional:

1. Generate the PDF.
2. Run `/opt/skills/pdf/scripts/render_pages.sh out.pdf /tmp/pdf-pages`.
3. Inspect **one page per call** with `inspect_sandbox_images`, checking
   clipping, overflow, blank pages, alignment, legibility, visual hierarchy, and
   factual consistency. One page at a time keeps each report focused on one
   fixable defect.
4. If a report identifies any defect, edit the source, regenerate, render, and
   inspect again.
5. If the document has more than one page, make one final call with a small set
   of pages together — the first page, the last page, and any page you changed —
   to catch what single-page inspection cannot see: drift in fonts, spacing, and
   page count, and "this should be one page, not two". Keep this set small; pages
   are only compared against each other within a single call. A one-page document
   has nothing to compare against, so step 3 was already the whole check.
6. Run `/opt/skills/pdf/scripts/check_pdf.py out.pdf` for structural checks.
7. Only then call:
   `save_artifact(path="out.pdf", title="...", markdown_representation="...")`.

The Markdown representation must faithfully contain the document's substantive
text so the artifact remains accessible and searchable without parsing the PDF.
