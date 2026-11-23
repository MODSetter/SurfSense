# Scripts that write the libraries themselves

For what the `surfsense_docs` helper cannot do, the script writes python-docx (Word), ReportLab (PDF) or python-pptx (PowerPoint) itself: the user's own file as a template, a PowerPoint chart they can edit, the look of a source you can only see, a layout of your own. Follow [`SKILL.md`](SKILL.md) for rendering, changing and failed runs; this file is what such a script must do by hand.

## The contract

- Save the file at the path in the `OUTPUT_PATH` environment variable. Nothing else the script writes is kept.
- Use only Python's standard library, python-docx, ReportLab, python-pptx, xlsxwriter or openpyxl, matplotlib (charts), Pillow and numpy. Do not use the network.
- To place an image from the sources, find its name with `surfsense_list_images`, list every name you use in the call's `images`, and open it at `os.path.join(os.environ["IMAGES_DIR"], name + ".png")`.
- A picture from `surfsense_make_image` goes the same way: list the name it gave, `image-<id>`, in `images`, and open it at the same path. If the render says it is still being drawn, tell the user and stop.
- With `template_source_id`, a copy of that source's file is at `os.environ["TEMPLATE_PATH"]` (see [Starting from the user's own file](#starting-from-the-users-own-file)).
- Save a chart or any other intermediate file in the working folder, then place it.

## Clean documents

- Headings are real headings: `add_heading` in Word, the `Heading1`/`Heading2` styles in ReportLab. Never fake one with bold text.
- Lists use list styles (`List Bullet`, `List Number`, or ReportLab's `ListFlowable`). Never type bullet characters, dashes or numbers yourself.
- Tables are real tables with a header row: bold in Word, a shaded first row with `repeatRows=1` in ReportLab. Keep to about six columns on a portrait page.
- Use A4 unless the user is in the US or Canada or asks for Letter. python-docx starts on Letter, so set the section's size and margins.
- Scale every image and chart to at most the text width, keeping its proportions.
- In ReportLab, `Paragraph` reads its text as markup: escape `&`, `<` and `>` in text from the sources with `xml.sax.saxutils.escape`.

## PowerPoint decks

- Make slides 16:9 (13.333 x 7.5 inches) unless the user asks otherwise or a template sets the size; python-pptx starts at 4:3.
- Add each slide from a layout chosen by name (`Title Slide`, `Title and Content`, `Title Only`, `Blank`) and fill its title and body placeholders. A bullet is a paragraph of the body; indent with `paragraph.level`. Never type bullet characters.
- One idea per slide, at most about six bullets, and no text running off the slide: split a long slide in two.
- A table is `shapes.add_table` with a bold header row. A picture is `shapes.add_picture` given only a width or a height, so it keeps its proportions, placed inside the slide.
- A chart is either a matplotlib PNG placed as a picture, or a native chart (`CategoryChartData` and `shapes.add_chart`) when the user will want to edit its numbers in PowerPoint.
- Put what the presenter says in the speaker notes: `slide.notes_slide.notes_text_frame.text`.

## Starting from the user's own file

When the user asks for their template, letterhead or brand deck, and a selected source is that Word file (.docx) or PowerPoint deck (.pptx), pass its number as `template_source_id` with the same format. The script opens the copy at `TEMPLATE_PATH`, removes the template's own content, adds the new content in the template's styles and layouts, and saves to `OUTPUT_PATH`. The source itself is never changed. The next version of that document starts from the same template without naming it again. PDF and Excel take no template.

- **Word:** keep the template's styles, headers, footers and page settings; remove every block of its body except the last `sectPr`, as the example below does. Use the template's own style names; a name it lacks raises a `KeyError`.
- **PowerPoint:** remove the template's own slides as the example below does, then add slides from its layouts by name. A name the template lacks falls back to its first layout, so check the slide previews.

## Matching a look you can only see

When the user wants the look of a source that cannot be a template, such as a PDF brand guide, or wants a deck in the style of a Word report, call `surfsense_source_pages` with that source; its pages come back as images with the result. Note the fonts (use the closest you have), the colours as hex values, the margins, the heading sizes and where the logo sits, then write them into the script. Ask only for the pages you need, at most four at a time, and do not draw the same pages again: every image you open stays in the conversation.

## Charts

Draw with matplotlib, save a PNG, close the figure, then place the PNG like any image. Give the chart a title and labelled axes, and save at `dpi=200` so it stays sharp.

When the numbers are only in a source's figure and it labels none you can read exactly, place that figure with its caption instead of drawing a chart from other numbers, and tell the user you did. If the document already holds that figure, keep it and say so.

## Checking what you made

Look at every preview after the first version and after any change to the layout, for tables that run off the page, text running off a slide, squashed columns, images missing or out of place, empty pages, headings stranded at the foot of a page, unreadable charts and leftover placeholder text. A short last page is not a fault. The result names what drew the pages. Pages drawn by SurfSense's Word viewer or by LibreOffice show headers, footers and watermarks, so check those too.

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

## Example: PowerPoint

```python
import os

from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.enum.chart import XL_CHART_TYPE
from pptx.util import Inches, Pt

deck = Presentation()
deck.slide_width, deck.slide_height = Inches(13.333), Inches(7.5)
layouts = {layout.name: layout for layout in deck.slide_layouts}

cover = deck.slides.add_slide(layouts["Title Slide"])
cover.shapes.title.text = "Rollout plan"
cover.placeholders[1].text = "Halvorsen Freight, 2026"

points = deck.slides.add_slide(layouts["Title and Content"])
points.shapes.title.text = "Why now"
body = points.placeholders[1].text_frame
body.text = "Costs rose 12% in two years"
for text, level in (("Mostly in the north", 1), ("A pilot proves the saving", 0)):
    paragraph = body.add_paragraph()
    paragraph.text, paragraph.level = text, level
points.notes_slide.notes_text_frame.text = "Start with the cost rise."

pricing = deck.slides.add_slide(layouts["Title Only"])
pricing.shapes.title.text = "Pricing"
rows = [("Phase", "Cost"), ("Pilot", "12,000 EUR"), ("Rollout", "48,000 EUR")]
table = pricing.shapes.add_table(
    len(rows), 2, Inches(0.8), Inches(1.8), Inches(5.5), Inches(1.5)
).table
for r, row in enumerate(rows):
    for c, value in enumerate(row):
        table.cell(r, c).text = value
        table.cell(r, c).text_frame.paragraphs[0].runs[0].font.bold = r == 0

chart_data = CategoryChartData()
chart_data.categories = ["2024", "2025", "2026"]
chart_data.add_series("Thousand EUR", (120, 135, 150))
chart = pricing.shapes.add_chart(
    XL_CHART_TYPE.COLUMN_CLUSTERED,
    Inches(7),
    Inches(1.8),
    Inches(5.5),
    Inches(4.5),
    chart_data,
).chart
chart.has_title = True
chart.chart_title.text_frame.text = "Yearly costs"
chart.chart_title.text_frame.paragraphs[0].runs[0].font.size = Pt(16)

deck.save(os.environ["OUTPUT_PATH"])
```

## Example: Word from a template

```python
import os

import docx

document = docx.Document(os.environ["TEMPLATE_PATH"])
body = document.element.body
# Keep the last sectPr: it holds the page size, margins, headers and footers.
for block in list(body):
    if not block.tag.endswith("}sectPr"):
        body.remove(block)

document.add_heading("Client proposal", level=1)
document.add_paragraph("We propose a two-phase rollout.")
document.save(os.environ["OUTPUT_PATH"])
```

## Example: PowerPoint from a template

```python
import os

from pptx import Presentation

deck = Presentation(os.environ["TEMPLATE_PATH"])
# Remove the template's own slides; its masters and layouts stay.
slide_ids = deck.slides._sldIdLst
for slide_id in list(slide_ids):
    deck.part.drop_rel(slide_id.rId)
    slide_ids.remove(slide_id)
# Its sections list the removed slides; PowerPoint would call the file damaged.
SECTIONS = "{http://schemas.microsoft.com/office/powerpoint/2010/main}sectionLst"
for sections in list(deck.part._element.iter(SECTIONS)):
    extension = sections.getparent()
    extension.getparent().remove(extension)

layouts = {layout.name: layout for layout in deck.slide_layouts}


def layout(name):
    return layouts.get(name, deck.slide_layouts[0])


cover = deck.slides.add_slide(layout("Title Slide"))
cover.shapes.title.text = "Rollout plan"
points = deck.slides.add_slide(layout("Title and Content"))
points.shapes.title.text = "Why now"
points.placeholders[1].text_frame.text = "Costs rose 12% in two years"
deck.save(os.environ["OUTPUT_PATH"])
```
