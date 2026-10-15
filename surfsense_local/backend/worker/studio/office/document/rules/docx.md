Authoring rules for Word:

- Start from `docx.Document()` and save with `document.save(os.environ["OUTPUT_PATH"])`.
- python-docx starts on Letter: set the section to A4 (21 x 29.7 cm) unless US Letter is implied, with margins of at least 18 mm.
- Headings are real headings (`add_heading`); never fake one with bold text.
- Lists use the `List Bullet` and `List Number` styles; never type bullet characters, dashes or numbers yourself.
- Tables are real tables with the `Table Grid` style and a bold header row; set column widths deliberately and keep to about six columns.
- Put page breaks in their own paragraphs, and use separate paragraphs instead of newline characters.
- Do not add a table of contents unless it is asked for.
