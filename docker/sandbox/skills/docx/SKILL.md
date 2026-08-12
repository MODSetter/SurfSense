---
name: docx
description: Create polished, editable Microsoft Word documents such as reports, letters, proposals, and handbooks.
---

# DOCX

Create the requested Word document in `/workspace` with the preinstalled `docx`
npm package. Never install or download dependencies.

Use one deliverable-derived stem for the source and output, for example
`project-brief.js` and `project-brief.docx`. Write deterministic JavaScript
source so revisions change the source and regenerate the document.

## Authoring rules

- Use one page size and orientation for the document unless the user asks for a
  different layout. Prefer portrait; narrow wide content instead of silently
  switching sections to landscape.
- Set explicit DXA page dimensions: US Letter is 12,240 × 15,840; A4 is
  11,906 × 16,838. Choose the size the user requests, or the locale-appropriate
  default when they do not specify one.
- Set margins of at least 18 mm and use built-in heading levels.
- Tables need `columnWidths`, a matching `width` on every cell, and
  `WidthType.DXA` for both. Include a table grid. Never use percentage widths.
- Use `ShadingType.CLEAR`, never `ShadingType.SOLID`.
- Build lists through the document's `numbering` configuration with
  `LevelFormat.BULLET`; never insert literal `•` characters.
- Put `PageBreak` inside its own `Paragraph`. Use separate paragraphs instead
  of newline characters for separate blocks.
- Do not add a table of contents unless the user asks. If requested, use
  built-in heading levels and state that page numbers populate when Word opens
  and updates the field.
- For right-aligned text on the same line, use a right tab stop rather than
  `PositionalTab`, which LibreOffice renders incorrectly.
- Generate the document as one whole document. Do not assemble or save one
  DOCX per intended page; Word controls pagination through reflow.

When revising, `load_artifact_source` returns the existing `document_id` and a
`source_path` with a name such as `artifact-42-project-brief.js`. Copy that
source to `project-brief.js` before editing so the `artifact-42-` prefix does not
compound, then pass the returned `document_id` to `save_artifact`. A changed
title, filename, or design is still the same artifact unless the user explicitly
asks for a separate copy.

## Verify and save

Call `verify_artifact(path="project-brief.docx")`. Warnings are advisory. If it
reports blocking findings, fix them in the JavaScript source and regenerate
once. Reverify that revision; if a blocker remains, stop and explain it instead
of entering another automatic rewrite loop. Then call `save_artifact` with the
DOCX path, JavaScript source path, and the exact `preview_path` returned by
verification. The Markdown representation must faithfully contain the
document's substantive text for accessibility and search.
