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
3. Call `inspect_sandbox_images` with every emitted JPEG path and instructions
   to check clipping, overflow, blank pages, alignment, legibility, visual
   hierarchy, and factual consistency.
4. If the report identifies any defect, edit the source, regenerate, render,
   and inspect again.
5. Run `/opt/skills/pdf/scripts/check_pdf.py out.pdf` for structural checks.
6. Only then call:
   `save_artifact(path="out.pdf", title="...", markdown_representation="...")`.

The Markdown representation must faithfully contain the document's substantive
text so the artifact remains accessible and searchable without parsing the PDF.
