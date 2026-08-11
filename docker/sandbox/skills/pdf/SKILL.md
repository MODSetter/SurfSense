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

Use one deliverable-derived stem for the source and output, for example
`project-brief.html` and `project-brief.pdf`; the output basename is the
filename the user downloads. After generating it, call
`verify_artifact(path="project-brief.pdf")`. Warnings are advisory and do not
require regeneration. If verification reports blocking findings, fix them in
the source and regenerate once. Reverify that revision; if a blocker remains,
stop and explain it instead of entering another automatic rewrite loop. Only a
verified file can be saved.

Then call `save_artifact(path="project-brief.pdf",
source_path="project-brief.html", title="...", markdown_representation="...")`,
using the actual `.html` or `.py` source path that produced the PDF.

The Markdown representation must faithfully contain the document's substantive
text so the artifact remains accessible and searchable without parsing the PDF.
