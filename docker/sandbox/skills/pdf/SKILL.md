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
- Do not embed page numbers, folios, `Page X of Y` labels, CSS page counters,
  or numbered ReportLab footers. SurfSense's PDF viewer supplies its own page
  indicator, so embedded numbering would duplicate the interface.

Escape untrusted text before placing it in HTML.

## Revisions

Start an in-place revision with `load_artifact_for_revision`. Read its
`markdown_path` for the artifact's substantive content and any other context
provided by the user, then regenerate the PDF at `expected_output_path`. PDF
revisions are rebuilds from Markdown/context, not edits inferred from rendered
pages. Do not use vision to reconstruct the old PDF; vision may still be used
by `verify_artifact` after regeneration.

Save the verified revision with the returned `artifact_id` and
`expected_generation`. A changed title, filename, or design is still the same
artifact unless the user explicitly asks for a separate copy.

## Required quality gate

After generating the requested PDF, call `verify_artifact(path=output_path)`.
Warnings are advisory and do not require regeneration. If verification reports
blocking findings, fix all blockers together, regenerate once at the same
output path, and reverify. If a blocker remains, stop and explain it instead of
entering another automatic rewrite loop. Only a verified file can be saved.

Then call `save_artifact(path=output_path, title="...",
markdown_representation="...")`. Working files may use any paths; no source
file, preview file, or matching filename stem is part of the publication
contract.

The Markdown representation must faithfully contain the document's substantive
text so the artifact remains accessible and searchable without parsing the PDF.
