"""Text stamped on a copy of a PDF: a watermark, page numbers, a header or a footer."""

import math
from io import BytesIO

import pypdf
from pypdf import Transformation
from pypdf.generic import (
    ArrayObject,
    DecodedStreamObject,
    FloatObject,
    IndirectObject,
    NameObject,
)
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

from modules.pdf_tools.drawn_over import draw_over
from modules.pdf_tools.page_operations import written
from modules.pdf_tools.refusal import PdfRefusedError
from modules.pdf_tools.stamp_font import font_for

KINDS = ("watermark", "page_numbers", "header", "footer")
POSITIONS = (
    "top-left",
    "top-center",
    "top-right",
    "bottom-left",
    "bottom-center",
    "bottom-right",
)
DEFAULT_POSITION = {
    "header": "top-center",
    "footer": "bottom-center",
    "page_numbers": "bottom-center",
}
PAGE_NUMBER_TEXT = "{page} / {total}"
TEXT_CHARS = 200
# About 1 cm in from the edge, inside most printers' margins.
MARGIN = 28
LINE_SIZE = 10
SMALLEST_SIZE = 6
WATERMARK_LARGEST = 120


def stamp(
    reader: pypdf.PdfReader,
    kind: str,
    text: str | None,
    position: str | None,
    pages: list[int],
) -> bytes:
    """The whole PDF with `text` drawn on the pages named, upright as each page is shown.

    For page numbers, `{page}` is the page's own number and `{total}` the count.
    A watermark always runs corner to corner, whatever `position` says.
    """
    text = _text(kind, text)
    if kind != "watermark":
        position = position or DEFAULT_POSITION[kind]
        if position not in POSITIONS:
            raise PdfRefusedError(f"position must be one of: {', '.join(POSITIONS)}.")
    font = font_for(text)
    if font is None:
        raise PdfRefusedError(
            "This computer has no font with every character of that text, so it "
            "cannot be stamped. Write it in Latin letters, or tell the user."
        )
    if stringWidth(text, font, LINE_SIZE) <= 0:
        raise PdfRefusedError(
            "That text has nothing to draw: its characters have no width. Give "
            "visible words."
        )
    writer = pypdf.PdfWriter(clone_from=reader)
    targets = list(dict.fromkeys(pages))
    total = len(writer.pages)
    overlay = _overlay(
        [
            (_shown_size(writer.pages[number - 1]), _filled(text, number, total))
            for number in targets
        ],
        kind,
        position,
        font,
    )
    for number, drawn in zip(targets, overlay.pages, strict=True):
        page = writer.pages[number - 1]
        draw_over(page, writer, [(_form(writer, drawn), _onto(page).ctm)])
    return written(writer)


def _text(kind: str, text: str | None) -> str:
    if kind not in KINDS:
        raise PdfRefusedError(f"kind must be one of: {', '.join(KINDS)}.")
    if kind == "page_numbers":
        text = text if text and text.strip() else PAGE_NUMBER_TEXT
        if "{page}" not in text:
            raise PdfRefusedError(
                "Page number text must hold {page}, and may hold {total}: such as "
                '"Page {page} of {total}".'
            )
    if text is None or not text.strip():
        raise PdfRefusedError(f"Give the text to stamp as the {kind}.")
    text = " ".join(text.split())
    if len(text) > TEXT_CHARS:
        raise PdfRefusedError(f"Stamp at most {TEXT_CHARS} characters.")
    return text


def _filled(text: str, number: int, total: int) -> str:
    return text.replace("{page}", str(number)).replace("{total}", str(total))


def _shown_size(page: pypdf.PageObject) -> tuple[float, float]:
    """The page's size as a viewer shows it, after its own turn."""
    width, height = float(page.cropbox.width), float(page.cropbox.height)
    return (height, width) if page.rotation % 180 == 90 else (width, height)


def _form(writer: pypdf.PdfWriter, drawn: pypdf.PageObject) -> IndirectObject:
    """One overlay page as a form XObject of the copy, clipped to its page."""
    box = drawn.mediabox
    form = DecodedStreamObject()
    form.set_data(drawn.get_contents().get_data())
    form.update(
        {
            NameObject("/Type"): NameObject("/XObject"),
            NameObject("/Subtype"): NameObject("/Form"),
            NameObject("/BBox"): ArrayObject(
                FloatObject(v) for v in (box.left, box.bottom, box.right, box.top)
            ),
            NameObject("/Resources"): drawn["/Resources"].clone(writer),
        }
    )
    return writer._add_object(form)


def _onto(page: pypdf.PageObject) -> Transformation:
    """From the shown page's space, origin bottom left, into the page's own space.

    /Rotate turns the page clockwise for display, so the stamp turns the other way.
    """
    box = page.cropbox
    width, height = float(box.width), float(box.height)
    a, b, c, d, e, f = {
        0: (1, 0, 0, 1, 0, 0),
        90: (0, 1, -1, 0, width, 0),
        180: (-1, 0, 0, -1, width, height),
        270: (0, -1, 1, 0, 0, height),
    }[page.rotation % 360]
    return Transformation((a, b, c, d, e + float(box.left), f + float(box.bottom)))


def _overlay(
    pages: list[tuple[tuple[float, float], str]],
    kind: str,
    position: str | None,
    font: str,
) -> pypdf.PdfReader:
    """One page of text per page stamped, each its target's shown size."""
    out = BytesIO()
    drawing = canvas.Canvas(out)
    for (width, height), text in pages:
        drawing.setPageSize((width, height))
        if kind == "watermark":
            _watermark(drawing, width, height, text, font)
        else:
            _line(drawing, width, height, text, font, position or "bottom-center")
        drawing.showPage()
    drawing.save()
    return pypdf.PdfReader(BytesIO(out.getvalue()))


def _watermark(
    drawing: canvas.Canvas, width: float, height: float, text: str, font: str
) -> None:
    """Large, pale and diagonal, corner to corner, so the page beneath stays readable."""
    diagonal = math.hypot(width, height)
    size = min(WATERMARK_LARGEST, 0.7 * diagonal / stringWidth(text, font, 1))
    drawing.saveState()
    drawing.setFillGray(0.5)
    drawing.setFillAlpha(0.3)
    drawing.setFont(font, size)
    drawing.translate(width / 2, height / 2)
    drawing.rotate(math.degrees(math.atan2(height, width)))
    drawing.drawCentredString(0, -size * 0.35, text)
    drawing.restoreState()


def _line(
    drawing: canvas.Canvas,
    width: float,
    height: float,
    text: str,
    font: str,
    position: str,
) -> None:
    """One line at the margin, made smaller when it would not fit across the page."""
    room = width - 2 * MARGIN
    fitted = LINE_SIZE * room / stringWidth(text, font, LINE_SIZE)
    size = max(SMALLEST_SIZE, min(LINE_SIZE, fitted))
    vertical, horizontal = position.split("-")
    y = height - MARGIN - size if vertical == "top" else MARGIN
    drawing.setFillGray(0.25)
    drawing.setFont(font, size)
    if horizontal == "left":
        drawing.drawString(MARGIN, y, text)
    elif horizontal == "right":
        drawing.drawRightString(width - MARGIN, y, text)
    else:
        drawing.drawCentredString(width / 2, y, text)
