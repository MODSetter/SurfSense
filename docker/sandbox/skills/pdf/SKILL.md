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

After generating the PDF, call `verify_artifact(path="out.pdf")`. Fix every
reported defect in the source, regenerate, and call `verify_artifact` again.
Only a verified file can be saved.

Then call `save_artifact(path="out.pdf", source_path="source.html", title="...",
markdown_representation="...")`, using the actual `.html` or `.py` source path
that produced the PDF.

The Markdown representation must faithfully contain the document's substantive
text so the artifact remains accessible and searchable without parsing the PDF.
