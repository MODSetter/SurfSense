# Binding pictures into a PDF

Render this with `surfsense_render_document`, `format: pdf`, every page's name in `images`, in order. Fill in `TITLE` and `PAGES`, and change nothing else unless the user asks: it is the layout every comic and picture book uses.

- One picture per page, full bleed, at comic-book width, each page as tall as its picture.
- A page's lines, when given, are set under its picture in a strip, exactly as written. Give them for a page whose lettering came out wrong, or for every page drawn without words.
- Pictures are placed as JPEG, so a book of pages stays a few megabytes.
- A page still being drawn may be named all the same: the PDF waits for it, and appears in Studio when its last page is drawn. Tell the user so, and stop.

```python
import os
from io import BytesIO

from PIL import Image
from reportlab.lib.units import inch
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

TITLE = "The Lighthouse Cat"
# Each page in order: its picture's name, and the lines to set under it, or none.
PAGES = [
    ("image-12", []),
    ("image-13", ["NORA: The bulb is broken!"]),
]

WIDTH = 6.625 * inch
MARGIN = 0.25 * inch
FONT, SIZE, LEADING = "Helvetica", 11, 15


def wrapped(text, width):
    lines, line = [], ""
    for word in text.split():
        trial = f"{line} {word}".strip()
        if line and stringWidth(trial, FONT, SIZE) > width:
            lines.append(line)
            line = word
        else:
            line = trial
    return lines + [line] if line else lines


pdf = canvas.Canvas(os.environ["OUTPUT_PATH"])
pdf.setTitle(TITLE)
for name, said in PAGES:
    path = os.path.join(os.environ["IMAGES_DIR"], name + ".png")
    picture = Image.open(path).convert("RGB")
    jpeg = BytesIO()
    picture.save(jpeg, "JPEG", quality=90)
    jpeg.seek(0)
    height = WIDTH * picture.height / picture.width
    lines = [line for text in said for line in wrapped(text, WIDTH - 2 * MARGIN)]
    strip = len(lines) * LEADING + 2 * MARGIN if lines else 0
    pdf.setPageSize((WIDTH, height + strip))
    pdf.drawImage(ImageReader(jpeg), 0, strip, WIDTH, height)
    pdf.setFont(FONT, SIZE)
    y = strip - MARGIN - SIZE
    for line in lines:
        pdf.drawString(MARGIN, y, line)
        y -= LEADING
    pdf.showPage()
pdf.save()
```
