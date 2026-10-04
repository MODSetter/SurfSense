---
name: surfsense-documents
description: Make or change a Word document (.docx) or a PDF by writing a Python script that surfsense_render_document runs. Load it whenever the user asks for a Word file or a PDF, or for a change to one you made.
---

# Word documents and PDFs as scripts

You make a document by writing a Python script and passing it to `surfsense_render_document`. SurfSense runs the script, keeps the file it writes as a version in Studio, and keeps the script beside it. To change the document later you change the script and render it again, which makes the next version.

## The contract

- Save the document at the path in the `OUTPUT_PATH` environment variable. Nothing else the script writes is kept.
- Use only Python's standard library, python-docx (Word), ReportLab (PDF), matplotlib (charts), Pillow and numpy. Do not use the network.
- The script runs alone, from an empty folder, for at most 120 seconds. It cannot read the user's sources: write the content into the script, from what you found in them.
- To place an image from the sources, find its name with `surfsense_list_images`, list every name you use in the call's `images`, and open it at `os.path.join(os.environ["IMAGES_DIR"], name + ".png")`.
- To look at a source image yourself, open the copy `surfsense_list_images` names, `sources/figures/<name>.png`, with `read`. These copies are read-only.
- Save a chart or any other intermediate file in the working folder, then place it.

## Clean documents

- Headings are real headings: `add_heading` in Word, the `Heading1`/`Heading2` styles in ReportLab. Never fake one with bold text.
- Lists use list styles (`List Bullet`, `List Number`, or ReportLab's `ListFlowable`). Never type bullet characters, dashes or numbers yourself.
- Tables are real tables with a header row: bold in Word, a shaded first row with `repeatRows=1` in ReportLab. Keep to about six columns on a portrait page.
- Use A4 unless the user is in the US or Canada or asks for Letter. python-docx starts on Letter, so set the section's size and margins.
- Scale every image and chart to at most the text width, keeping its proportions.
- Write only what the sources and the user support. Chart only numbers you found or were given.
- In ReportLab, `Paragraph` reads its text as markup: escape `&`, `<` and `>` in text from the sources with `xml.sax.saxutils.escape`.

## Charts

Draw with matplotlib, save a PNG, close the figure, then place the PNG like any image. Give the chart a title and labelled axes, and save at `dpi=200` so it stays sharp.

A drawn chart in a source rarely leaves its numbers in the source's text. When the numbers the user wants charted are only in a source's figure, as its caption from `surfsense_list_images` shows, open the figure with `read` and chart the values it labels. If `read` cannot show you the image, place that figure with its caption and tell the user you could not read its values. When it labels none you can read exactly, place that figure with its caption instead of drawing a chart from other numbers, and tell the user you did. If the document already holds that figure, keep it and say so.

## Editing a document you made

1. Call `surfsense_read_document` with its artifact id. It returns the newest version's script.
2. Change only what the user asked for. Keep every other line as it was.
   Make every change asked for in this render, reading loose words the natural way: "the cover" of a document without a cover page is the top of its first page, and a section the user names that the document lacks is the closest one or a new one. Say in a line what you assumed. Ask first only when something cannot be done as asked.
3. Render with the same title and format and `artifact_id` set to that document: the result is its next version. A different format, such as a PDF of a Word document, is a new document: render it without `artifact_id`.

## Checking what you made

A successful render lists page previews under `outputs/previews/`. Open every page it lists with `read`, not only the first, after the first version and after any change to the layout, and look for tables that run off the page, squashed columns, images missing or out of place, empty pages, headings stranded at the foot of a page, unreadable charts and leftover placeholder text. A short last page is not a fault. When something is wrong, fix the script without dropping content the user did not ask to change, render again, then open every page of that new version too: answer only once you have looked at the version you end on. Word previews leave out headers and footers, so a logo or page number placed there does not show in them; that is not a fault to fix. When the result says there are no previews, check the text it returned instead. When `read` cannot show you the previews, check the script against the list above and the text the result returned, and do not open them again.

## When a run fails

The result gives the error and the last lines of the traceback; their line numbers point into your script. Fix the cause and render again with the `artifact_id` the result names. After a third failed run for the same request, stop: tell the user in a sentence what failed, and wait for their next message.

## Example: Word

```python
import os

import docx
import matplotlib.pyplot as plt
from docx.shared import Cm

years = ["2024", "2025", "2026"]
costs = [120, 135, 150]

fig, ax = plt.subplots(figsize=(6.4, 3.2))
ax.bar(years, costs, color="#3b6ea5")
ax.set_title("Yearly costs")
ax.set_xlabel("Year")
ax.set_ylabel("Thousand EUR")
fig.tight_layout()
fig.savefig("costs.png", dpi=200)
plt.close(fig)

document = docx.Document()
section = document.sections[0]
section.page_width, section.page_height = Cm(21), Cm(29.7)
for side in ("left_margin", "right_margin", "top_margin", "bottom_margin"):
    setattr(section, side, Cm(2.5))
text_width = section.page_width - section.left_margin - section.right_margin

document.add_heading("Client proposal", level=0)
document.add_heading("Executive summary", level=1)
document.add_paragraph("We propose a two-phase rollout.")
for point in ("A pilot in one depot", "Every depot by June"):
    document.add_paragraph(point, style="List Bullet")

document.add_heading("Pricing", level=1)
table = document.add_table(rows=1, cols=2)
table.style = "Table Grid"
for cell, label in zip(table.rows[0].cells, ("Phase", "Cost")):
    cell.paragraphs[0].add_run(label).bold = True
for phase, cost in (("Pilot", "12,000 EUR"), ("Rollout", "48,000 EUR")):
    row = table.add_row().cells
    row[0].text, row[1].text = phase, cost

document.add_picture("costs.png", width=text_width)
document.save(os.environ["OUTPUT_PATH"])
```

## Example: PDF

```python
import os
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    ListFlowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

styles = getSampleStyleSheet()
doc = SimpleDocTemplate(
    os.environ["OUTPUT_PATH"],
    pagesize=A4,
    leftMargin=2 * cm,
    rightMargin=2 * cm,
    topMargin=2 * cm,
    bottomMargin=2 * cm,
    title="Client proposal",
)

rows = [["Phase", "Cost"], ["Pilot", "12,000 EUR"], ["Rollout", "48,000 EUR"]]
table = Table(rows, colWidths=[doc.width / 2] * 2, repeatRows=1)
table.setStyle(
    TableStyle(
        [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#dde6f0")),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ]
    )
)

doc.build(
    [
        Paragraph("Client proposal", styles["Title"]),
        Paragraph("Executive summary", styles["Heading1"]),
        Paragraph(escape("Costs & timeline for the rollout."), styles["BodyText"]),
        ListFlowable(
            [Paragraph(p, styles["BodyText"]) for p in ("A pilot", "Every depot")],
            bulletType="bullet",
        ),
        Spacer(1, 0.5 * cm),
        table,
    ]
)
```
