Authoring rules for PDF:

- Use ReportLab's Platypus: `SimpleDocTemplate(os.environ["OUTPUT_PATH"], pagesize=A4, ...)` with `Paragraph`, `Table`, `Spacer`, `ListFlowable` and `getSampleStyleSheet`, not hand-placed canvas coordinates.
- Use A4 unless US Letter is implied, margins of at least 18 mm, and 10 to 11 pt body text.
- Headings use the `Heading1` and `Heading2` styles. Lists use `ListFlowable`; never type bullet characters yourself.
- Tables use `Table` and `TableStyle` with a grid, a shaded header row and `repeatRows=1`.
- `Paragraph` reads its text as markup: escape `&`, `<` and `>` in text from the sources with `xml.sax.saxutils.escape`.
- The built-in fonts (Helvetica, Times) cover Latin-1 only; keep the text within it.
- Do not embed "Page X of Y" folios.
