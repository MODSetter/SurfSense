"""A comic's pictures bound into one PDF, as Studio and the agent both bind them."""

from dataclasses import dataclass
from io import BytesIO

from PIL import Image
from reportlab.lib.units import inch
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

from modules.artifacts.comic.reading import Direction, Layout
from worker.studio.office.markdown.pdf_fonts import font_runs

# Comic-book trim width; each page is as tall as its picture.
WIDTH = 6.625 * inch
MARGIN = 0.25 * inch
GUTTER = 0.2 * inch
FONT, SIZE, LEADING = "Helvetica", 11, 15
# A scroll starts a new page every twelve pictures, so no viewer meets one huge page.
PER_SCROLL = 12
# JPEG, not PNG: four PNG pages made 10 to 28 MB in the spike.
JPEG_QUALITY = 90


@dataclass(frozen=True)
class BoundPage:
    picture: bytes
    # Set under the picture exactly: a misspelt page's, or one drawn without words.
    lines: tuple[str, ...] = ()


@dataclass(frozen=True)
class _Block:
    image: ImageReader
    height: float
    lines: list[str]
    strip: float


def bind(
    title: str, pages: list[BoundPage], *, layout: Layout, direction: Direction
) -> bytes:
    out = BytesIO()
    pdf = canvas.Canvas(out)
    pdf.setTitle(title)
    if direction == "rtl":
        pdf.setViewerPreference("Direction", "R2L")
    blocks = [_block(page) for page in pages]
    if layout == "scroll":
        for start in range(0, len(blocks), PER_SCROLL):
            _draw(pdf, blocks[start : start + PER_SCROLL], GUTTER)
    else:
        for one in blocks:
            _draw(pdf, [one], 0)
    pdf.save()
    return out.getvalue()


def _block(page: BoundPage) -> _Block:
    with Image.open(BytesIO(page.picture)) as opened:
        picture = opened.convert("RGB")
    jpeg = BytesIO()
    picture.save(jpeg, "JPEG", quality=JPEG_QUALITY)
    jpeg.seek(0)
    lines = [line for text in page.lines for line in _wrapped(text, WIDTH - 2 * MARGIN)]
    strip = len(lines) * LEADING + 2 * MARGIN if lines else 0
    return _Block(
        ImageReader(jpeg), WIDTH * picture.height / picture.width, lines, strip
    )


def _wrapped(text: str, width: float) -> list[str]:
    lines: list[str] = []
    line = ""
    for piece, glued in _breakable(text, width):
        trial = f"{line}{'' if glued else ' '}{piece}" if line else piece
        if line and _width(trial) > width:
            lines.append(line)
            line = piece
        else:
            line = trial
    return [*lines, line] if line else lines


def _breakable(text: str, width: float) -> list[tuple[str, bool]]:
    """Words, with one too wide for a line, as Chinese or Japanese is, cut into
    letters; each piece says whether it joins the one before with no space."""
    pieces: list[tuple[str, bool]] = []
    for word in text.split():
        cut = list(word) if _width(word) > width else [word]
        pieces += [(piece, n > 0) for n, piece in enumerate(cut)]
    return pieces


def _width(text: str) -> float:
    return sum(stringWidth(run, font or FONT, SIZE) for font, run in font_runs(text))


def _set_line(pdf: canvas.Canvas, x: float, y: float, line: str) -> None:
    for font, run in font_runs(line):
        pdf.setFont(font or FONT, SIZE)
        pdf.drawString(x, y, run)
        x += stringWidth(run, font or FONT, SIZE)


def _draw(pdf: canvas.Canvas, blocks: list[_Block], gutter: float) -> None:
    """Top to bottom on one page, each picture with its strip under it."""
    height = sum(b.height + b.strip for b in blocks) + gutter * (len(blocks) - 1)
    pdf.setPageSize((WIDTH, height))
    top = height
    for block in blocks:
        pdf.drawImage(block.image, 0, top - block.height, WIDTH, block.height)
        y = top - block.height - MARGIN - SIZE
        for line in block.lines:
            _set_line(pdf, MARGIN, y, line)
            y -= LEADING
        top -= block.height + block.strip + gutter
    pdf.showPage()
