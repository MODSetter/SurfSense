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
loop is not optional. Every step treats every page the same way — page count
changes how long it takes, never what you do:

1. Generate the PDF.
2. Run `/opt/skills/pdf/scripts/check_pdf.py out.pdf`. It measures what does not
   need eyes: text past the margins or page edge, blank and near-blank pages,
   page count, missing embedded fonts. Fix whatever it reports and run it again —
   these are far cheaper to find here than with a vision call.
3. Run `/opt/skills/pdf/scripts/render_pages.sh out.pdf /tmp/pdf-pages`.
4. Pass **every** rendered page to `inspect_sandbox_images`, asking about
   alignment, legibility, visual hierarchy, spacing, and factual consistency.
   The tool reviews each page on its own, so every report names one page.
5. Call it once more with `mode="together"` to compare the pages against each
   other — font and colour drift, inconsistent spacing, and "this should be one
   page, not two" are invisible when pages are seen one at a time.
6. Any defect from step 4 or 5: edit the source and repeat from step 2.
7. Only then call:
   `save_artifact(path="out.pdf", title="...", markdown_representation="...")`.

The Markdown representation must faithfully contain the document's substantive
text so the artifact remains accessible and searchable without parsing the PDF.
