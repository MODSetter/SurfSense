"""PDFs as people upload them: born-digital, scanned, filled in or turned, made
with reportlab, pypdf, matplotlib and PIL in fonts they bundle, so CI needs no
fonts of its own."""

import io
import random

import pypdfium2
from matplotlib.figure import Figure
from matplotlib.font_manager import FontProperties
from matplotlib.patches import PathPatch
from matplotlib.textpath import TextPath
from PIL import Image, ImageDraw
from pypdf import PdfReader, PdfWriter, Transformation
from pypdf.generic import DecodedStreamObject, NameObject, RectangleObject
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.utils import ImageReader, simpleSplit
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    FrameBreak,
    PageTemplate,
    Paragraph,
)

WIDTH, HEIGHT = A4
FONT, SIZE, LEADING = "Helvetica", 11, 15
MARGIN = 72

_WORDS = [
    *("harbour", "freight", "berth", "crane", "schedule", "tariff", "vessel"),
    *("cargo", "quarter", "budget", "terminal", "capacity", "inspection"),
    *("depot", "lighting", "maintenance", "backlog", "contract", "pilotage"),
    *("dredging", "customs", "clearance", "warehouse", "reefer", "throughput"),
]


def prose(paragraphs: int, seed: int) -> list[str]:
    """Report paragraphs, each opening with its number, the same for the same seed."""
    rng = random.Random(seed)
    return [
        f"Paragraph {n} on the {rng.choice(_WORDS)} plan. "
        + " ".join(
            " ".join(rng.choice(_WORDS) for _ in range(12)).capitalize() + "."
            for _ in range(3)
        )
        for n in range(1, paragraphs + 1)
    ]


def text_pages(*pages: list[str]) -> bytes:
    """Each page's paragraphs set in Helvetica, wrapped to the page."""
    out = io.BytesIO()
    drawing = canvas.Canvas(out, pagesize=A4)
    for paragraphs in pages:
        _write(drawing, paragraphs)
        drawing.showPage()
    drawing.save()
    return out.getvalue()


def set_text(*pages: list[str]) -> str:
    """The text text_pages() sets: each paragraph's lines as wrapped, a blank line
    between paragraphs and between pages."""
    return "\n\n".join(
        "\n\n".join("\n".join(_wrapped(paragraph)) for paragraph in paragraphs)
        for paragraphs in pages
    )


def two_column_page(paragraphs: list[str], *, paragraph_space: float = 0) -> bytes:
    """A title across the top, then the paragraphs flowing down two columns, with
    `paragraph_space` points after each."""
    out = io.BytesIO()
    document = BaseDocTemplate(
        out, pagesize=A4, leftMargin=50, rightMargin=50, topMargin=50, bottomMargin=50
    )
    gap = 18
    column = (WIDTH - 100 - gap) / 2
    title = Frame(50, HEIGHT - 110, WIDTH - 100, 60, id="title")
    columns = [
        Frame(50 + k * (column + gap), 50, column, HEIGHT - 164, id=f"column{k}")
        for k in range(2)
    ]
    document.addPageTemplates([PageTemplate(id="page", frames=[title, *columns])])
    body = ParagraphStyle(
        "body", fontName=FONT, fontSize=9, leading=11.4, spaceAfter=paragraph_space
    )
    heading = ParagraphStyle("title", fontName="Helvetica-Bold", fontSize=17)

    story = [Paragraph("Coastal freight corridors", heading), FrameBreak()]
    story += [Paragraph(text, body) for text in paragraphs]
    document.build(story)
    return out.getvalue()


def table_page(
    caption: str,
    rows: list[list[str]],
    *,
    caption_above: bool,
    before: list[str],
    after: list[str],
) -> bytes:
    """Paragraphs, then a table as a paper sets one, 9 pt rows under a header with a
    rule beneath it, captioned above as a paper does or below as a spec does, then
    more paragraphs."""
    out = io.BytesIO()
    drawing = canvas.Canvas(out, pagesize=A4)
    y = _paragraphs_at(drawing, before, HEIGHT - MARGIN) - 3 * LEADING
    if caption_above:
        y = _caption_at(drawing, caption, y) - 22
    drawing.setFont(FONT, 9)
    for n, row in enumerate(rows):
        for k, cell in enumerate(row):
            drawing.drawString(MARGIN + 20 + 110 * k, y, cell)
        if n == 0:  # the rule under the header
            drawing.line(MARGIN + 20, y - 5, MARGIN + 350, y - 5)
            y -= 5
        y -= 10
    if not caption_above:
        y = _caption_at(drawing, caption, y - 12) - 10
    _paragraphs_at(drawing, after, y + 10 - 3 * LEADING)
    drawing.showPage()
    drawing.save()
    return out.getvalue()


def scanned_page(paragraphs: list[str], *, ocr_layer: bool) -> bytes:
    """The paragraphs printed and scanned to one image, with or without the
    invisible text a scanner's OCR lays over it."""
    image = _rendered(text_pages(paragraphs))
    out = io.BytesIO()
    drawing = canvas.Canvas(out, pagesize=A4)
    drawing.drawImage(ImageReader(image), 0, 0, width=WIDTH, height=HEIGHT)
    if ocr_layer:
        _write(drawing, paragraphs, render_mode=3)
    drawing.showPage()
    drawing.save()
    return out.getvalue()


def cover_page(title: str, report: list[str]) -> bytes:
    """A section cover, a full-bleed photo with its title over it, then a page of report."""
    out = io.BytesIO()
    drawing = canvas.Canvas(out, pagesize=A4)
    drawing.drawImage(ImageReader(photo()), 0, 0, width=WIDTH, height=HEIGHT)
    drawing.setFont("Helvetica-Bold", 28)
    drawing.setFillColor("white")
    drawing.drawString(MARGIN, HEIGHT / 2, title)
    drawing.showPage()
    _write(drawing, report)
    drawing.showPage()
    drawing.save()
    return out.getvalue()


def form(answers: dict[str, str], *, ticked: bool) -> bytes:
    """A claim form: printed labels, a text field each, and a tick box.

    An answer left as "" is a field nobody filled in.
    """
    out = io.BytesIO()
    drawing = canvas.Canvas(out, pagesize=A4)
    drawing.setFont("Helvetica-Bold", 15)
    drawing.drawString(MARGIN, HEIGHT - 70, "Vehicle damage claim form")
    drawing.setFont(FONT, SIZE)
    y = HEIGHT - 120
    for n, (label, answer) in enumerate(answers.items()):
        drawing.drawString(MARGIN, y + 5, f"{label}:")
        drawing.acroForm.textfield(
            name=f"field{n}", value=answer, x=250, y=y, width=230, height=20
        )
        y -= 40
    drawing.drawString(MARGIN, y + 5, "The vehicle was drivable after the incident:")
    drawing.acroForm.checkbox(name="drivable", x=330, y=y, size=16, checked=ticked)
    drawing.drawString(MARGIN, y - 40, "Claims are kept for seven years.")
    drawing.showPage()
    drawing.save()
    return out.getvalue()


def turned(pdf: bytes, page: int, degrees: int) -> bytes:
    """The PDF with one page given a /Rotate, as a landscape page often is."""
    writer = PdfWriter(clone_from=PdfReader(io.BytesIO(pdf)))
    writer.pages[page].rotate(degrees)
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def misencoded(pdf: bytes, letter: str, becomes: str) -> bytes:
    """The PDF with its font's text map sending one letter to another character,
    as a broken generator writes it; the page looks the same."""
    writer = PdfWriter(clone_from=PdfReader(io.BytesIO(pdf)))
    pairs = "\n".join(
        f"<{code:02X}> <{_utf16(becomes if chr(code) == letter else chr(code))}>"
        for code in range(0x20, 0x7F)
    )
    cmap = (
        "/CIDInit /ProcSet findresource begin 12 dict begin begincmap\n"
        "/CIDSystemInfo << /Registry (Adobe) /Ordering (UCS) /Supplement 0 >> def\n"
        "/CMapName /Adobe-Identity-UCS def /CMapType 2 def\n"
        "1 begincodespacerange <00> <FF> endcodespacerange\n"
        f"95 beginbfchar\n{pairs}\nendbfchar\n"
        "endcmap CMapName currentdict /CMap defineresource pop end end"
    )
    for page in writer.pages:
        for font in page["/Resources"]["/Font"].values():
            stream = DecodedStreamObject()
            stream.set_data(cmap.encode("ascii"))
            font.get_object()[NameObject("/ToUnicode")] = writer._add_object(stream)
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def drawn_page(shapes: int) -> bytes:
    """A page of curves and no text, like lettering converted to outlines."""
    out = io.BytesIO()
    drawing = canvas.Canvas(out, pagesize=A4)
    rng = random.Random(shapes)
    for _ in range(shapes):
        x, y = rng.uniform(80, 500), rng.uniform(100, 700)
        drawing.bezier(x, y, x + 8, y + 14, x + 16, y - 6, x + 24, y + 4)
    drawing.showPage()
    drawing.save()
    return out.getvalue()


def joined(*pdfs: bytes) -> bytes:
    """The PDFs' pages, one after another."""
    writer = PdfWriter()
    for pdf in pdfs:
        writer.append(PdfReader(io.BytesIO(pdf)))
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def first_page(pdf: bytes) -> bytes:
    """The PDF cut to its first page."""
    writer = PdfWriter()
    writer.add_page(PdfReader(io.BytesIO(pdf)).pages[0])
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def lines_page(lines: list[str]) -> bytes:
    """The lines set one under another as given, a typesetter's hyphens kept."""
    out = io.BytesIO()
    drawing = canvas.Canvas(out, pagesize=A4)
    text = drawing.beginText(MARGIN, HEIGHT - MARGIN)
    text.setFont(FONT, SIZE, LEADING)
    for line in lines:
        text.textLine(line)
    drawing.drawText(text)
    drawing.showPage()
    drawing.save()
    return out.getvalue()


def illustrated(paragraphs: list[str]) -> bytes:
    """A page of report with a photo under its text, as a site visit report has."""
    out = io.BytesIO()
    drawing = canvas.Canvas(out, pagesize=A4)
    _write(drawing, paragraphs)
    drawing.drawImage(
        ImageReader(photo((400, 300))), MARGIN, MARGIN, width=300, height=225
    )
    drawing.showPage()
    drawing.save()
    return out.getvalue()


def stamped(pdf: bytes, *, header: str = "", footer: str = "") -> bytes:
    """The PDF with live text stamped at the head or foot of every page, as a court's
    filing system, DocuSign or a Bates numbering tool adds it to a scan.

    "{n}" and "{pages}" in a stamp are the page's number and the page count.
    """
    writer = PdfWriter(clone_from=PdfReader(io.BytesIO(pdf)))
    pages = len(writer.pages)
    overlay = io.BytesIO()
    drawing = canvas.Canvas(overlay, pagesize=A4)
    for n in range(1, pages + 1):
        drawing.setFont(FONT, 8)
        if header:
            drawing.drawString(36, HEIGHT - 20, header.format(n=n, pages=pages))
        if footer:
            drawing.drawString(36, 20, footer.format(n=n, pages=pages))
        drawing.showPage()
    drawing.save()
    for page, stamp in zip(writer.pages, PdfReader(overlay).pages, strict=True):
        page.merge_page(stamp)
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def outlined_page(paragraphs: list[str]) -> bytes:
    """The paragraphs as lettering turned into outlines, as a print-ready export or
    a Ghostscript pass that drops fonts leaves them: drawn, with no text layer."""
    figure = Figure(figsize=(WIDTH / 72, HEIGHT / 72))
    axes = figure.add_axes((0, 0, 1, 1))
    axes.set_xlim(0, WIDTH)
    axes.set_ylim(0, HEIGHT)
    axes.axis("off")
    font = FontProperties(family="DejaVu Sans", size=SIZE)  # matplotlib's own
    y = HEIGHT - MARGIN
    for paragraph in paragraphs:
        for line in simpleSplit(paragraph, FONT, SIZE, WIDTH - 2 * MARGIN):
            outline = TextPath((MARGIN, y), line, size=SIZE, prop=font)
            axes.add_patch(PathPatch(outline, color="black", lw=0))
            y -= LEADING
        y -= LEADING
    out = io.BytesIO()
    figure.savefig(out, format="pdf")
    return out.getvalue()


def nested(pdf: bytes, depth: int) -> bytes:
    """The PDF with each page drawn from Form XObjects `depth` deep, as N-up
    imposition, or LaTeX including a PDF that itself includes one, leaves it."""
    for _ in range(depth):
        pdf = _drawn_as_forms(pdf)
    return pdf


def moved(pdf: bytes, x: float, y: float) -> bytes:
    """The PDF with every page's content and boxes moved off the origin, as some
    scanners and imposition tools write a page; each page looks the same."""
    writer = PdfWriter(clone_from=PdfReader(io.BytesIO(pdf)))
    for page in writer.pages:
        left, bottom, right, top = (float(edge) for edge in page.mediabox)
        page.add_transformation(Transformation().translate(x, y))
        box = RectangleObject([left + x, bottom + y, right + x, top + y])
        page.mediabox = box
        page.cropbox = box
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def ab_text(pdf: bytes) -> str:
    """The answer-quality A/B's text arm: each page's text layer, a blank line apart."""
    document = pypdfium2.PdfDocument(pdf)
    try:
        pages = []
        for page in document:
            textpage = page.get_textpage()
            pages.append(textpage.get_text_range())
            textpage.close()
    finally:
        document.close()
    return "\n\n".join(text.replace("\r\n", "\n").replace("\r", "\n") for text in pages)


def photo(size: tuple[int, int] = (600, 840)) -> Image.Image:
    """A raster picture with enough shape that layout reads it as one."""
    image = Image.new("RGB", size, "white")
    draw = ImageDraw.Draw(image)
    for x in range(0, size[0], 20):
        draw.rectangle([x, 0, x + 10, size[1]], fill=(x % 255, 100, 200))
    draw.ellipse(
        [size[0] // 4, size[1] // 6, size[0] * 3 // 4, size[1] * 5 // 6], "orange"
    )
    return image


def _write(drawing: canvas.Canvas, paragraphs: list[str], render_mode: int = 0) -> None:
    text = drawing.beginText(MARGIN, HEIGHT - MARGIN)
    text.setFont(FONT, SIZE, LEADING)
    text.setTextRenderMode(render_mode)
    for paragraph in paragraphs:
        for line in _wrapped(paragraph):
            text.textLine(line)
        text.textLine("")
    drawing.drawText(text)


def _paragraphs_at(drawing: canvas.Canvas, paragraphs: list[str], y: float) -> float:
    """Sets the paragraphs from baseline y down, a blank line apart; returns the
    last baseline."""
    drawing.setFont(FONT, SIZE)
    for n, paragraph in enumerate(paragraphs):
        if n:
            y -= LEADING
        for line in _wrapped(paragraph):
            drawing.drawString(MARGIN, y, line)
            y -= LEADING
    return y + LEADING


def _caption_at(drawing: canvas.Canvas, caption: str, y: float) -> float:
    """Sets a 9 pt caption from baseline y down; returns its last baseline."""
    drawing.setFont(FONT, 9)
    for line in simpleSplit(caption, FONT, 9, 300):
        drawing.drawString(MARGIN + 20, y, line)
        y -= 10
    return y + 10


def _wrapped(paragraph: str) -> list[str]:
    return simpleSplit(paragraph, FONT, SIZE, WIDTH - 2 * MARGIN)


def _utf16(char: str) -> str:
    """A ToUnicode destination: UTF-16BE in hex, a surrogate pair past U+FFFF."""
    return char.encode("utf-16-be").hex().upper()


def _drawn_as_forms(pdf: bytes) -> bytes:
    source = pypdfium2.PdfDocument(pdf)
    wrapped = pypdfium2.PdfDocument.new()
    try:
        for index in range(len(source)):
            width, height = source[index].get_size()
            form = source.page_as_xobject(index, wrapped)
            page = wrapped.new_page(width, height)
            page.insert_obj(form.as_pageobject())
            page.gen_content()
        out = io.BytesIO()
        wrapped.save(out)
        return out.getvalue()
    finally:
        wrapped.close()
        source.close()


def _rendered(pdf: bytes) -> Image.Image:
    document = pypdfium2.PdfDocument(pdf)
    try:
        return document[0].render(scale=150 / 72).to_pil().convert("RGB")
    finally:
        document.close()
