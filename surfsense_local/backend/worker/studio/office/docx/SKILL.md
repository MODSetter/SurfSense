---
name: docx
description: Create polished, editable Microsoft Word documents such as reports, letters, proposals, and handbooks.
---

# DOCX

Author the Word document with `python-docx`, then save it to a `BytesIO`.

## Authoring rules

- Use one page size and orientation unless the content asks for a different
  layout. Prefer portrait; narrow wide content instead of switching to landscape.
- Set margins of at least 18 mm and use built-in heading levels.
- Set table and cell widths deliberately and use a visible table grid.
- Use Word numbering/list styles; never insert literal `•` characters.
- Put page breaks in their own paragraphs. Use separate paragraphs instead of
  newline characters for separate blocks.
- Do not add a table of contents unless it is asked for.
- For right-aligned text on the same line, use a right tab stop.
- Generate the document as one whole document. Do not assemble one DOCX per
  intended page; Word controls pagination through reflow.
- Open with a title, then organise the facts into clear, headed sections.
