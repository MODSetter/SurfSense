# Binding pictures into a PDF

Render this with `surfsense_render_document`, `format: pdf`, every picture's name in `images`, in reading order. Fill in `TITLE`, `PAGES`, and for the kind of comic `LAYOUT` and `DIRECTION` ([`comics.md`](comics.md#which-kind)); change nothing else unless the user asks.

- `LAYOUT = "pages"`: one picture per page, full bleed, at comic-book width, each page as tall as its picture. `LAYOUT = "scroll"`: the pictures stacked down one long page, read by scrolling, as a webtoon is; a new page every twelve.
- `DIRECTION = "rtl"` tells a reader the book reads right to left, as a manga does, so its spreads are laid out that way.
- A picture's lines, when given, are set under it in a strip, exactly as written. Give them for a page whose lettering came out wrong, for every page drawn without words, for a picture book's text and a storyboard's notes.
- Pictures are placed as JPEG, so a book of pages stays a few megabytes.
- A picture still being drawn may be named all the same: the PDF waits for it, and appears in Studio when its last picture is drawn. Tell the user so, and stop.

```python
import os
from io import BytesIO

from PIL import Image
from reportlab.lib.units import inch
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

TITLE = "The Lighthouse Cat"
# Each picture in reading order: its name, and the lines to set under it, or none.
PAGES = [
    ("image-12", []),
    ("image-13", ["NORA: The bulb is broken!"]),
]
LAYOUT = "pages"  # "pages", or "scroll" for a webtoon
DIRECTION = "ltr"  # "ltr", or "rtl" for a manga

WIDTH = 6.625 * inch
MARGIN = 0.25 * inch
GUTTER = 0.2 * inch
FONT, SIZE, LEADING = "Helvetica", 11, 15
PER_SCROLL = 12


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


def block(name, said):
    """A picture as JPEG, its height at the page's width, and its strip's lines."""
    picture = Image.open(os.path.join(os.environ["IMAGES_DIR"], name + ".png"))
    picture = picture.convert("RGB")
    jpeg = BytesIO()
    picture.save(jpeg, "JPEG", quality=90)
    jpeg.seek(0)
    lines = [line for text in said for line in wrapped(text, WIDTH - 2 * MARGIN)]
    strip = len(lines) * LEADING + 2 * MARGIN if lines else 0
    return ImageReader(jpeg), WIDTH * picture.height / picture.width, lines, strip


def draw(pdf, blocks, gutter):
    """Top to bottom on one page, each picture with its strip under it."""
    height = sum(h + strip for _, h, _, strip in blocks) + gutter * (len(blocks) - 1)
    pdf.setPageSize((WIDTH, height))
    top = height
    for image, h, lines, strip in blocks:
        pdf.drawImage(image, 0, top - h, WIDTH, h)
        pdf.setFont(FONT, SIZE)
        y = top - h - MARGIN - SIZE
        for line in lines:
            pdf.drawString(MARGIN, y, line)
            y -= LEADING
        top -= h + strip + gutter
    pdf.showPage()


pdf = canvas.Canvas(os.environ["OUTPUT_PATH"])
pdf.setTitle(TITLE)
if DIRECTION == "rtl":
    pdf.setViewerPreference("Direction", "R2L")
blocks = [block(name, said) for name, said in PAGES]
if LAYOUT == "scroll":
    for start in range(0, len(blocks), PER_SCROLL):
        draw(pdf, blocks[start : start + PER_SCROLL], GUTTER)
else:
    for one in blocks:
        draw(pdf, [one], 0)
pdf.save()
```
