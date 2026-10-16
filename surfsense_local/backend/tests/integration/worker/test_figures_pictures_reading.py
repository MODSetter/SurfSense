"""The pictures reading keeps the very figures the full reading does, with real Docling."""

import io
import json
import os
import subprocess
import sys
from pathlib import Path

import pypdfium2
import pytest
import reportlab
from fontTools.pens.basePen import BasePen
from fontTools.ttLib import TTFont
from PIL import Image, ImageDraw, ImageFont
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    Flowable,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.platypus import Image as PdfImage

from tests.integration.worker.test_figures_docling import photo, report_pdf
from tests.integration.worker.test_parsing import BACKEND, PACK_ROOT

pytestmark = pytest.mark.integration

SCAN_CAPTION = "Figure 3: Vessel calls by month."
OUTLINED_CAPTION = "Figure 1: Vessel calls by month, January to June."
RASTER_CAPTION = "Figure 1: Dwell times by month, January to June."

# Both readings of every file in one child, which loads each pipeline once. It
# records the pictures reading's runs, each its kind and its first and last page.
CHILD = """
import hashlib, json, shutil, socket, sys
from pathlib import Path

def refuse(*_args, **_kwargs):
    raise OSError("this test refuses outbound network")

socket.socket.connect = refuse
socket.socket.connect_ex = refuse

from worker.ingestion import parsing
from worker.ingestion.figures import run_reading
from worker.ingestion.figures.backfill import reading_for_figures
from worker.ingestion.figures.scanned_pages import scanned_pages
from worker.ingestion.figures.store import keep_figures

asked = []
for kind, name in (("full", "read_in_full"), ("layout", "read_by_layout")):
    def recorded(pdf, first, last, kind=kind, read=getattr(run_reading, name)):
        asked.append([kind, first, last])
        return read(pdf, first, last)
    setattr(run_reading, name, recorded)

out = {}
for name in sys.argv[1:]:
    source = Path(name)
    out[source.name] = {"scanned": scanned_pages(source)}
    for how, read in (("full", parsing.convert), ("pictures", reading_for_figures)):
        folder = source.parent / how / source.stem
        folder.mkdir(parents=True)
        copy = folder / source.name
        shutil.copyfile(source, copy)
        asked.clear()
        keep_figures(copy, read(copy))
        index = json.loads((folder / "figures" / "figures.json").read_text("utf-8"))
        pngs = [
            hashlib.sha256((folder / "figures" / f"{entry['n']}.png").read_bytes()).hexdigest()
            for entry in index["figures"]
        ]
        out[source.name][how] = {"index": index, "pngs": pngs}
    out[source.name]["asked"] = asked[:]
print(json.dumps(out))
"""


def scanned_chart_page(bars: tuple[int, int, int] = (40, 90, 170)) -> bytes:
    """One page that is a raster scan of a captioned chart, stamped with a digital number."""
    width, height = 1240, 1754  # A4 at 150 dpi
    scan = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(scan)
    font = ImageFont.load_default(size=30)
    for line in range(6):
        draw.text(
            (120, 160 + line * 44),
            "Vessel calls rose through the spring as dwell times fell.",
            font=font,
            fill="black",
        )
    draw.rectangle([200, 520, 1000, 1020], outline="black", width=3)
    for bar, value in enumerate((180, 260, 340, 300, 420, 460)):
        left = 250 + bar * 120
        draw.rectangle([left, 1000 - value, left + 70, 1000], fill=bars)
    draw.text((200, 1050), SCAN_CAPTION, font=font, fill="black")
    pixels = io.BytesIO()
    scan.save(pixels, "PNG")

    out = io.BytesIO()
    page = canvas.Canvas(out, pagesize=A4)
    page.drawImage(ImageReader(pixels), 0, 0, width=A4[0], height=A4[1])
    page.drawString(500, 20, "Page 3")
    page.showPage()
    page.save()
    return out.getvalue()


def bound_together(*pdfs: bytes) -> bytes:
    """The PDFs' pages, in order, in one file."""
    joined = pypdfium2.PdfDocument.new()
    for content in pdfs:
        joined.import_pages(pypdfium2.PdfDocument(content))
    out = io.BytesIO()
    joined.save(out)
    return out.getvalue()


class _OutlinePen(BasePen):
    """Draws a glyph's outline into a ReportLab path; fontTools names its hooks."""

    def __init__(self, glyphs, path, x: float, y: float, scale: float) -> None:
        super().__init__(glyphs)
        self.path, self.x, self.y, self.scale = path, x, y, scale

    def _at(self, point: tuple[float, float]) -> tuple[float, float]:
        return self.x + point[0] * self.scale, self.y + point[1] * self.scale

    def _moveTo(self, point) -> None:  # noqa: N802
        self.path.moveTo(*self._at(point))

    def _lineTo(self, point) -> None:  # noqa: N802
        self.path.lineTo(*self._at(point))

    def _curveToOne(self, first, second, third) -> None:  # noqa: N802
        self.path.curveTo(*self._at(first), *self._at(second), *self._at(third))

    def _closePath(self) -> None:  # noqa: N802
        self.path.close()


class OutlinedLine(Flowable):
    """A line of text drawn as filled vector outlines: no character in the text layer."""

    def __init__(self, text: str, size: float = 10) -> None:
        super().__init__()
        self.text, self.size = text, size
        self.width, self.height = 400, size * 1.4

    def draw(self) -> None:
        font = TTFont(str(Path(reportlab.__file__).parent / "fonts" / "VeraIt.ttf"))
        glyphs, characters = font.getGlyphSet(), font.getBestCmap()
        scale = self.size / font["head"].unitsPerEm
        path = self.canv.beginPath()
        x = 0.0
        for character in self.text:
            name = characters.get(ord(character), ".notdef")
            glyphs[name].draw(_OutlinePen(glyphs, path, x, 2, scale))
            x += font["hmtx"][name][0] * scale
        self.canv.drawPath(path, stroke=0, fill=1)


def bar_chart() -> Drawing:
    """A vector bar chart, as report_pdf draws on its second page."""
    drawing = Drawing(400, 220)
    chart = VerticalBarChart()
    chart.x, chart.y, chart.width, chart.height = 40, 30, 340, 170
    chart.data = [(13, 5, 20, 22, 37), (14, 6, 21, 23, 38)]
    chart.categoryAxis.categoryNames = ["2021", "2022", "2023", "2024", "2025"]
    drawing.add(chart)
    return drawing


def outlined_caption_pdf() -> bytes:
    """A born-digital report whose first chart's caption is drawn as vector outlines.

    As print-ready and design-tool exports draw text; the page still shows its
    body text, so it is not a scan.
    """
    styles = getSampleStyleSheet()
    story = [
        Paragraph("Port operations review", styles["Title"]),
        Paragraph("Vessel calls rose as dwell times fell. " * 8, styles["BodyText"]),
        bar_chart(),
        OutlinedLine(OUTLINED_CAPTION),
        Paragraph("The terminal moved more boxes an hour. " * 8, styles["BodyText"]),
        PageBreak(),
        Paragraph("Costs by region and year. " * 10, styles["BodyText"]),
        bar_chart(),
        Paragraph("Figure 2: Yearly costs by region.", styles["Italic"]),
    ]
    out = io.BytesIO()
    SimpleDocTemplate(out, pagesize=A4).build(story)
    return out.getvalue()


def raster_caption_pdf() -> bytes:
    """A born-digital page with a chart and its caption in one raster, under half the page."""
    chart = Image.new("RGB", (900, 620), "white")
    draw = ImageDraw.Draw(chart)
    draw.rectangle([40, 20, 860, 500], outline="black", width=3)
    for bar, value in enumerate((180, 260, 340, 300, 420, 460)):
        left = 100 + bar * 120
        draw.rectangle([left, 490 - value, left + 70, 490], fill=(40, 90, 170))
    draw.text(
        (40, 530), RASTER_CAPTION, font=ImageFont.load_default(size=26), fill="black"
    )
    pixels = io.BytesIO()
    chart.save(pixels, "PNG")
    styles = getSampleStyleSheet()
    story = [
        Paragraph("Port operations review", styles["Title"]),
        Paragraph("Vessel calls rose as dwell times fell. " * 8, styles["BodyText"]),
        PdfImage(pixels, width=360, height=248),
        Paragraph("The terminal moved more boxes an hour. " * 8, styles["BodyText"]),
    ]
    out = io.BytesIO()
    SimpleDocTemplate(out, pagesize=A4).build(story)
    return out.getvalue()


def logos_in_a_table_pdf() -> bytes:
    """A numeric table with a small logo in some rows' first cell, and a photo below."""
    styles = getSampleStyleSheet()
    rows: list[list] = [["", "Depot", "Q1", "Q2", "Q3", "Q4"]]
    for row in range(10):
        logo = (
            PdfImage(io.BytesIO(photo((120, 120), 30 + 20 * row)), width=36, height=36)
            if row in (1, 4, 7)
            else ""
        )
        quarters = [str(1200 + 37 * row * quarter % 900) for quarter in range(1, 5)]
        rows.append([logo, f"Depot {row + 1}", *quarters])
    table = Table(rows, colWidths=[44, 80, 55, 55, 55, 55])
    table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    story = [
        Paragraph("Depot volumes", styles["Title"]),
        Paragraph("Table 1: Pallets by depot and quarter.", styles["Italic"]),
        table,
        Spacer(1, 12),
        PdfImage(io.BytesIO(photo((400, 300), 90)), width=200, height=150),
        Paragraph("Figure 1: The main depot.", styles["Italic"]),
    ]
    out = io.BytesIO()
    SimpleDocTemplate(out, pagesize=A4).build(story)
    return out.getvalue()


@pytest.fixture(scope="module")
def kept(tmp_path_factory: pytest.TempPathFactory) -> dict[str, dict]:
    """For each generated PDF, its scanned pages and the figures each reading keeps."""
    if PACK_ROOT is None:
        pytest.skip("run scripts/fetch_docling_models.py to exercise the real parser")

    root = tmp_path_factory.mktemp("pictures-reading")
    files = {
        "report.pdf": report_pdf(),
        "bound.pdf": bound_together(report_pdf(), scanned_chart_page()),
        "scans-around.pdf": bound_together(
            scanned_chart_page(), report_pdf(), scanned_chart_page((170, 60, 40))
        ),
        "outlined.pdf": outlined_caption_pdf(),
        "raster-caption.pdf": raster_caption_pdf(),
        "logos-table.pdf": logos_in_a_table_pdf(),
    }
    for name, content in files.items():
        (root / name).write_bytes(content)
    empty_cache = root / "hf"
    empty_cache.mkdir()
    # As a frozen build starts: offline only because ingest says so before it
    # first imports docling.
    env = {key: value for key, value in os.environ.items() if key != "HF_HUB_OFFLINE"}
    child = subprocess.run(
        [sys.executable, "-c", CHILD, *(str(root / name) for name in files)],
        cwd=BACKEND,
        env={
            **env,
            "SURFSENSE_LOCAL_DATA_DIR": str(root / "data"),
            "SURFSENSE_LOCAL_MODELS_DIR": str(PACK_ROOT),
            "HF_HOME": str(empty_cache),
        },
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=900,
    )
    assert child.returncode == 0, child.stderr[-4000:]
    return json.loads(child.stdout.strip().splitlines()[-1])


def test_layout_alone_keeps_a_born_digital_pdfs_photo_and_chart_as_they_were(
    kept: dict[str, dict],
) -> None:
    """The same figures index, and the same PNG bytes, figure by figure."""
    report = kept["report.pdf"]

    assert report["scanned"] == [False, False]
    assert len(report["full"]["index"]["figures"]) == 2
    assert report["pictures"] == report["full"]
    assert report["asked"] == [["layout", 1, 2]]


def test_a_scanned_page_bound_into_a_report_keeps_its_ocr_caption(
    kept: dict[str, dict],
) -> None:
    """Its run is read in full and joined to the layout-only runs in page order."""
    bound = kept["bound.pdf"]
    figures = bound["full"]["index"]["figures"]

    assert bound["scanned"] == [False, False, True]
    assert [(entry["page"], entry["caption"]) for entry in figures][2] == (
        3,
        SCAN_CAPTION,
    )
    assert bound["pictures"] == bound["full"]


def test_born_digital_pages_between_scans_keep_their_place(
    kept: dict[str, dict],
) -> None:
    """A layout-only run after a full one, and a full one after it."""
    bound = kept["scans-around.pdf"]

    assert bound["scanned"] == [True, False, False, True]
    assert [entry["page"] for entry in bound["full"]["index"]["figures"]] == [
        1,
        2,
        3,
        4,
    ]
    assert bound["pictures"] == bound["full"]
    assert bound["asked"] == [["full", 1, 1], ["layout", 2, 3], ["full", 4, 4]]


def test_a_caption_drawn_as_outlines_is_read_by_ocr_on_its_page(
    kept: dict[str, dict],
) -> None:
    """Layout alone drops a caption with no characters; its page is read again in full."""
    outlined = kept["outlined.pdf"]
    figures = outlined["full"]["index"]["figures"]

    assert outlined["scanned"] == [False, False]
    assert (figures[0]["page"], figures[0]["caption"]) == (1, OUTLINED_CAPTION)
    assert outlined["pictures"] == outlined["full"]
    assert outlined["asked"] == [["layout", 1, 2], ["full", 1, 1]]


def test_a_caption_drawn_in_a_rasters_pixels_is_read_by_ocr_on_its_page(
    kept: dict[str, dict],
) -> None:
    """The raster covers less than half the page, so the page is not a scan."""
    raster = kept["raster-caption.pdf"]
    figures = raster["full"]["index"]["figures"]

    assert raster["scanned"] == [False]
    assert [entry["caption"] for entry in figures] == [RASTER_CAPTION]
    assert raster["pictures"] == raster["full"]
    assert raster["asked"] == [["layout", 1, 1], ["full", 1, 1]]


def test_logos_inside_a_table_keep_their_order(kept: dict[str, dict]) -> None:
    """TableFormer files such a picture under its cell: the page is read in full."""
    table = kept["logos-table.pdf"]

    assert table["scanned"] == [False]
    assert table["pictures"] == table["full"]
    assert table["asked"] == [["layout", 1, 1], ["full", 1, 1]]
