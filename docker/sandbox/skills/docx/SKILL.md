---
name: docx
description: Create polished, editable Microsoft Word documents such as reports, letters, proposals, and handbooks.
---

# DOCX

Create the requested Word document in `/workspace` with the preinstalled
`python-docx` package. Never install or download dependencies.

## Authoring rules

- Use one page size and orientation for the document unless the user asks for a
  different layout. Prefer portrait; narrow wide content instead of silently
  switching sections to landscape.
- Choose the page size the user requests, or the locale-appropriate default
  when they do not specify one.
- Set margins of at least 18 mm and use built-in heading levels.
- Set table and cell widths deliberately and use a visible table grid.
- Use Word numbering/list styles; never insert literal `•` characters.
- Put page breaks in their own paragraphs. Use separate paragraphs instead of
  newline characters for separate blocks.
- Do not add a table of contents unless the user asks. If requested, use
  built-in heading levels and state that page numbers populate when Word opens
  and updates the field.
- For right-aligned text on the same line, use a right tab stop.
- Generate the document as one whole document. Do not assemble or save one
  DOCX per intended page; Word controls pagination through reflow.

## Revisions

Start an in-place revision with `load_artifact_for_revision`. Use
`python-docx` to open `primary_path`, make common edits directly to the existing
document, and write the result to `expected_output_path`. Common edits include
paragraph text and styles, headings, ordinary tables, lists, headers/footers,
section settings, and embedded images that `python-docx` can safely preserve.

If the requested edit touches a structure `python-docx` cannot safely interpret
or preserve—such as macros, SmartArt, complex fields, tracked changes, content
controls, or unsupported drawing/layout XML—stop and report the blocker. Do not
silently rebuild from `markdown_path` and do not fall back to a Markdown-only
deliverable. Rebuild the DOCX from Markdown/context only when the user
explicitly requested or accepted that lossy rebuild.

Do not use vision to reconstruct the document; `verify_artifact` may use vision
after the revision is written. Save the verified revision with the returned
`artifact_id` and `expected_generation`. A changed title, filename, or design
is still the same artifact unless the user explicitly asks for a separate copy.

## Verify and save

Call `verify_artifact(path=output_path)`. Warnings are advisory. If it reports
blocking findings, fix all blockers together, regenerate once at the same
output path, and reverify. If a blocker remains, stop and explain it instead of
entering another automatic rewrite loop.

Then call `save_artifact(path=output_path, title="...",
markdown_representation="...")`. Working files may use any paths; no source
file, preview file, or matching filename stem is part of the publication
contract. The Markdown representation must faithfully contain the document's
substantive text for accessibility and search.
