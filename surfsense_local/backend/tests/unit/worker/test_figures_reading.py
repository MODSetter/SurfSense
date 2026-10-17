"""The reading the figures-only pass asks Docling for: layout alone on born-digital pages."""

import io
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import docx
import pytest
from docling_core.types.doc import (
    BoundingBox,
    CoordOrigin,
    DocItemLabel,
    DoclingDocument,
    ProvenanceItem,
    Size,
    TableData,
)
from PIL import Image
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from worker.ingestion.figures.backfill import reading_for_figures
from worker.ingestion.figures.pictures_reading import read_for_pictures
from worker.ingestion.figures.run_reading import LayoutReading

pytestmark = pytest.mark.unit

BACKEND = Path(__file__).resolve().parents[3]

Page = Callable[[canvas.Canvas], None]


def words(page: canvas.Canvas) -> None:
    """A line of the text layer, as any born-digital page shows."""
    page.drawString(72, 760, "Quarterly results by region.")


def photo(page: canvas.Canvas) -> None:
    """A raster picture on a quarter of the page, and no text."""
    pixels = io.BytesIO()
    Image.new("RGB", (40, 30), "orange").save(pixels, "PNG")
    page.drawImage(ImageReader(pixels), 72, 300, width=300, height=225)


def stamped_scan(page: canvas.Canvas) -> None:
    """A raster scan of the whole page, stamped with a digital page number."""
    pixels = io.BytesIO()
    Image.new("RGB", (60, 85), "white").save(pixels, "PNG")
    page.drawImage(ImageReader(pixels), 0, 0, width=A4[0], height=A4[1])
    page.drawString(500, 20, "Page 1")


def searchable_scan(page: canvas.Canvas) -> None:
    """A scanner's OCR layer: its words are there, but never shown."""
    photo(page)
    layer = page.beginText(72, 760)
    layer.setTextRenderMode(3)
    layer.textLine("Quarterly results by region.")
    page.drawText(layer)


def pdf(path: Path, *pages: Page) -> Path:
    """An A4 PDF drawn page by page."""
    drawing = canvas.Canvas(str(path), pagesize=A4)
    for draw in pages:
        draw(drawing)
        drawing.showPage()
    drawing.save()
    return path


@pytest.fixture
def readings(monkeypatch: pytest.MonkeyPatch) -> list[Any]:
    """Each reading asked for: "full", or the scanned flags of a layout reading."""
    asked: list[Any] = []

    def full(_path: Path) -> str:
        asked.append("full")
        return "the full reading"

    def for_pictures(_path: Path, scanned: list[bool], *_resumable: Any) -> str:
        asked.append(list(scanned))
        return "the pictures reading"

    monkeypatch.setattr("worker.ingestion.parsing.convert", full)
    monkeypatch.setattr(
        "worker.ingestion.figures.pictures_reading.read_for_pictures", for_pictures
    )
    return asked


def test_a_born_digital_pdf_is_read_for_its_pictures_alone(
    tmp_path: Path, readings: list[Any]
) -> None:
    """Every page shows its text layer, a raster photo beside it included."""
    source = pdf(
        tmp_path / "report.pdf", words, lambda page: (words(page), photo(page))
    )

    assert reading_for_figures(source) == "the pictures reading"
    assert readings == [[False, False]]


def test_a_scan_is_read_in_full(tmp_path: Path, readings: list[Any]) -> None:
    """No shown text, a page number on a raster page, or only an OCR layer."""
    for name, page in (
        ("photo.pdf", photo),
        ("stamped.pdf", stamped_scan),
        ("searchable.pdf", searchable_scan),
    ):
        assert reading_for_figures(pdf(tmp_path / name, page)) == "the full reading"

    assert readings == ["full", "full", "full"]


def test_only_the_scanned_pages_of_a_pdf_are_marked_for_ocr(
    tmp_path: Path, readings: list[Any]
) -> None:
    """A born-digital report with a scanned page bound in keeps its cheap pages."""
    source = pdf(tmp_path / "report.pdf", words, stamped_scan, words, photo)

    reading_for_figures(source)

    assert readings == [[False, True, False, True]]


def test_other_files_keep_the_full_reading(tmp_path: Path, readings: list[Any]) -> None:
    """Word has no pages to split, and Docling says why it cannot read a broken PDF."""
    memo = docx.Document()
    memo.add_paragraph("Quarterly results by region.")
    memo.save(tmp_path / "memo.docx")
    (tmp_path / "broken.pdf").write_bytes(b"%PDF-1.7 not really")

    assert reading_for_figures(tmp_path / "memo.docx") == "the full reading"
    assert reading_for_figures(tmp_path / "broken.pdf") == "the full reading"
    assert readings == ["full", "full"]


def test_an_image_needs_no_reading(tmp_path: Path, readings: list[Any]) -> None:
    """An image is its own figure."""
    Image.new("RGB", (40, 30)).save(tmp_path / "logo.png")

    assert reading_for_figures(tmp_path / "logo.png") is None
    assert readings == []


def test_a_failed_pictures_reading_falls_back_to_the_full_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failure is recorded for good, so only the full reading may make it."""

    def broken(_path: Path, _scanned: list[bool], *_resumable: Any) -> None:
        raise RuntimeError("the layout model ran out of memory")

    monkeypatch.setattr(
        "worker.ingestion.figures.pictures_reading.read_for_pictures", broken
    )
    monkeypatch.setattr("worker.ingestion.parsing.convert", lambda _path: "full")

    assert reading_for_figures(pdf(tmp_path / "report.pdf", words)) == "full"


def test_a_failed_page_check_falls_back_to_the_full_reading(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A bug in the cheap check must not cost a file its figures for good."""

    def broken(_path: Path) -> None:
        raise ValueError("chr() arg not in range(0x110000)")

    monkeypatch.setattr("worker.ingestion.figures.backfill.scanned_pages", broken)
    monkeypatch.setattr("worker.ingestion.parsing.convert", lambda _path: "full")

    assert reading_for_figures(pdf(tmp_path / "report.pdf", words)) == "full"


def test_the_figures_pass_imports_no_docling() -> None:
    """parsing._converter() sets the environment docling reads as it is imported.

    A frozen build has no Hugging Face cache and must start offline, so nothing
    may import docling before it.
    """
    child = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys, worker.ingestion.figures.backfill;"
            "print(sorted({'docling', 'huggingface_hub'} & set(sys.modules)))",
        ],
        cwd=BACKEND,
        capture_output=True,
        text=True,
        timeout=120,
    )

    assert child.returncode == 0, child.stderr[-2000:]
    assert child.stdout.strip() == "[]"


def box(page: int, left: float, bottom: float, size: float) -> ProvenanceItem:
    """Where Docling found an item: its page and a square from the bottom-left."""
    return ProvenanceItem(
        page_no=page,
        bbox=BoundingBox(
            l=left,
            b=bottom,
            r=left + size,
            t=bottom + size,
            coord_origin=CoordOrigin.BOTTOMLEFT,
        ),
        charspan=(0, 0),
    )


@pytest.fixture
def docling(monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    """Docling reading a picture on each page, captioned with its reading's kind.

    `bare` pages hold no picture, `in_tables` pages hold it inside a table,
    `for_ocr` pages have a caption only OCR could read, and `lost` pages are
    missing from any reading of them. `asked` records each reading: its kind,
    and its pages.
    """
    seen = SimpleNamespace(
        asked=[], bare=set(), in_tables=set(), for_ocr=set(), lost=set()
    )

    def reading(kind: str, first: int, last: int) -> DoclingDocument:
        seen.asked.append((kind, (first, last)))
        document = DoclingDocument(name="report")
        for page in set(range(first, last + 1)) - seen.lost:
            document.add_page(page_no=page, size=Size(width=A4[0], height=A4[1]))
            if page in seen.bare:
                continue
            if page in seen.in_tables:
                document.add_table(data=TableData(), prov=box(page, 50, 50, 400))
            caption = document.add_text(
                label=DocItemLabel.CAPTION,
                text=f"{kind} {page}",
                prov=box(page, 100, 60, 20),
            )
            document.add_picture(prov=box(page, 100, 100, 40), caption=caption)
        return document

    def by_layout(_pdf: Path, first: int, last: int) -> LayoutReading:
        pages = set(range(first, last + 1))
        return LayoutReading(
            reading("layout", first, last), frozenset(seen.for_ocr & pages)
        )

    monkeypatch.setattr(
        "worker.ingestion.figures.run_reading.read_in_full",
        lambda _pdf, first, last: reading("full", first, last),
    )
    monkeypatch.setattr(
        "worker.ingestion.figures.run_reading.read_by_layout", by_layout
    )
    return seen


def kept(joined: DoclingDocument) -> list[tuple[int, str]]:
    """Each picture's page, and the reading its caption came from."""
    return [
        (picture.prov[0].page_no, picture.caption_text(joined))
        for picture in joined.pictures
    ]


def test_runs_of_like_pages_are_read_apart_and_joined_in_page_order(
    tmp_path: Path, docling: SimpleNamespace
) -> None:
    """The scanned run gets OCR; the born-digital runs get layout alone."""
    joined = read_for_pictures(tmp_path / "report.pdf", [False, True, True, False])

    assert docling.asked == [("layout", (1, 1)), ("full", (2, 3)), ("layout", (4, 4))]
    assert kept(joined) == [
        (1, "layout 1"),
        (2, "full 2"),
        (3, "full 3"),
        (4, "layout 4"),
    ]
    assert sorted(joined.pages) == [1, 2, 3, 4]


def test_only_a_page_with_a_picture_inside_a_table_is_read_again_in_full(
    tmp_path: Path, docling: SimpleNamespace
) -> None:
    """TableFormer files such a picture under the table's cell, which can move it."""
    docling.in_tables = {2}

    joined = read_for_pictures(tmp_path / "report.pdf", [False, False, False])

    assert docling.asked == [("layout", (1, 3)), ("full", (2, 2))]
    assert kept(joined) == [(1, "layout 1"), (2, "full 2"), (3, "layout 3")]
    assert sorted(joined.pages) == [1, 2, 3]


def test_a_picture_page_with_a_caption_only_ocr_could_read_is_read_again_in_full(
    tmp_path: Path, docling: SimpleNamespace
) -> None:
    """Such a caption is drawn as outlines or pixels, so layout alone drops it."""
    docling.for_ocr = {3, 4}
    docling.bare = {4}

    joined = read_for_pictures(tmp_path / "report.pdf", [True, False, False, False])

    # Page 4's caption has no picture to belong to.
    assert docling.asked == [("full", (1, 1)), ("layout", (2, 4)), ("full", (3, 3))]
    assert kept(joined) == [(1, "full 1"), (2, "layout 2"), (3, "full 3")]
    assert sorted(joined.pages) == [1, 2, 3, 4]


def test_a_page_a_reading_lacks_is_kept_empty_and_no_full_reading_follows(
    tmp_path: Path, docling: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Joining would shift every later page, and the crops with them; a reading of
    the whole file, which never gives way, lacks the page all the same."""
    docling.lost = {1}
    monkeypatch.setattr("worker.ingestion.parsing.convert", lambda _path: "full")

    source = pdf(tmp_path / "report.pdf", words, words, stamped_scan)
    joined = reading_for_figures(source)

    assert docling.asked == [("layout", (1, 2)), ("full", (3, 3))]
    assert kept(joined) == [(2, "layout 2"), (3, "full 3")]
    assert sorted(joined.pages) == [1, 2, 3]


@pytest.mark.parametrize("lost", [8, 9], ids=["last-of-a-batch", "first-of-a-batch"])
def test_a_long_scan_that_lost_a_page_keeps_its_batches_and_pages(
    tmp_path: Path, docling: SimpleNamespace, lost: int
) -> None:
    """Read in full a batch at a time, each picture on its own page."""
    docling.lost = {lost}

    joined = read_for_pictures(tmp_path / "scan.pdf", [True] * 20)

    assert docling.asked == [("full", (1, 8)), ("full", (9, 16)), ("full", (17, 20))]
    assert kept(joined) == [(n, f"full {n}") for n in range(1, 21) if n != lost]
    assert sorted(joined.pages) == list(range(1, 21))
