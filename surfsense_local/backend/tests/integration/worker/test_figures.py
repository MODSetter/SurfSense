"""Figures kept beside a source's original, by ingest and by the figures-only pass.

Docling stands in as a fixed reading built with docling-core, so these run
without its models; test_figures_docling.py runs the real parser.
"""

import io
import json
from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from docling_core.types.doc import (
    BoundingBox,
    ContentLayer,
    CoordOrigin,
    DocItemLabel,
    DoclingDocument,
    ImageRef,
    ProvenanceItem,
    Size,
)
from PIL import Image
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from modules.chunks.models import Chunk
from modules.documents.models import Document, DocumentStatus, DocumentType
from modules.documents.tasks import extract_figures
from modules.workspaces.models import Workspace
from shared.config import get_storage_settings
from shared.db import create_session_factory
from worker.ingestion import run

pytestmark = pytest.mark.integration


@pytest.fixture
def session(engine: Engine) -> Iterator[Session]:
    """A session on the migrated database ingest opens again by path."""
    with create_session_factory(engine)() as opened:
        yield opened


def add_source(
    session: Session,
    filename: str,
    content: bytes,
    status: DocumentStatus = DocumentStatus.PENDING,
) -> Document:
    """An upload with its original on disk, as the upload route leaves it."""
    workspace = Workspace(name="Reports")
    session.add(workspace)
    session.flush()
    source = Document(
        workspace_id=workspace.id,
        title=filename,
        document_type=DocumentType.FILE,
        status=status,
        content="The text ingest extracted."
        if status is DocumentStatus.READY
        else None,
    )
    session.add(source)
    session.commit()
    folder = get_storage_settings().document_dir(workspace.id, source.id)
    folder.mkdir(parents=True)
    (folder / filename).write_bytes(content)
    return source


def figures_dir(source: Document) -> Path:
    """Where ingest keeps this source's figures."""
    return (
        get_storage_settings().document_dir(source.workspace_id, source.id) / "figures"
    )


def index(source: Document) -> dict:
    """The figures index ingest wrote for this source."""
    return json.loads((figures_dir(source) / "figures.json").read_text("utf-8"))


def png(size: tuple[int, int], color: str = "red") -> Image.Image:
    """A plain picture of a given size and colour."""
    return Image.new("RGB", size, color)


# A drawn rectangle on a PDF page: page number, colour, and its corners in
# points from the page's bottom-left, as PDF and Docling's PDF reading place it.
Rect = tuple[int, str, tuple[float, float, float, float]]


def pdf_of(pages: int, *rects: Rect) -> bytes:
    """An A4 PDF with filled rectangles where pictures would be."""
    out = io.BytesIO()
    drawing = canvas.Canvas(out, pagesize=A4)
    for page in range(1, pages + 1):
        for on_page, color, (left, bottom, right, top) in rects:
            if on_page == page:
                drawing.setFillColor(color)
                drawing.rect(left, bottom, right - left, top - bottom, stroke=0, fill=1)
        drawing.showPage()
    drawing.save()
    return out.getvalue()


def provenance(
    page: int, box: tuple[float, float, float, float] = (0, 0, 10, 10)
) -> ProvenanceItem:
    """Where Docling found an item: its page and its box from the bottom-left."""
    left, bottom, right, top = box
    return ProvenanceItem(
        page_no=page,
        bbox=BoundingBox(
            l=left, b=bottom, r=right, t=top, coord_origin=CoordOrigin.BOTTOMLEFT
        ),
        charspan=(0, 0),
    )


def reading(*pictures: dict[str, Any]) -> DoclingDocument:
    """Docling's reading of a file: one paragraph, then the given pictures.

    A PDF picture carries no pixels, as ingest asks Docling for none; a Word or
    PowerPoint picture carries the pixels the file embeds.
    """
    document = DoclingDocument(name="report")
    for page in range(1, 4):
        document.add_page(page_no=page, size=Size(width=A4[0], height=A4[1]))
    document.add_text(label=DocItemLabel.TEXT, text="Quarterly results.")
    for picture in pictures:
        caption = (
            document.add_text(label=DocItemLabel.CAPTION, text=picture["caption"])
            if picture.get("caption")
            else None
        )
        document.add_picture(
            image=picture.get("image"),
            caption=caption,
            prov=provenance(picture["page"], picture.get("box", (0, 0, 10, 10)))
            if picture.get("page")
            else None,
            content_layer=picture.get("layer"),
        )
    return document


@pytest.fixture
def docling(monkeypatch: pytest.MonkeyPatch) -> list[Any]:
    """Make Docling read every file as the reading the test appends here."""
    readings: list[Any] = []

    def convert(_source: object) -> SimpleNamespace:
        if not readings:
            raise AssertionError("Docling was asked to read a file")
        return SimpleNamespace(document=readings.pop(0))

    monkeypatch.setattr(
        "worker.ingestion.parsing._converter",
        lambda: SimpleNamespace(convert=convert),
    )
    return readings


def test_a_pdfs_pictures_are_cropped_from_their_pages_at_twice_their_size(
    session: Session, stub_model: None, docling: list[Any]
) -> None:
    """Each picture's region of its page, rendered alone at 144 dpi, with the
    caption and page Docling found; a picture with no place on a page is skipped."""
    docling.append(
        reading(
            {
                "caption": "Figure 1: The harbour at dawn.",
                "page": 1,
                "box": (100, 500, 160, 540),
            },
            {"caption": "Figure 2: Nowhere on a page."},
            {"page": 2, "box": (300, 100, 330, 120)},
        )
    )
    original = pdf_of(
        2, (1, "red", (100, 500, 160, 540)), (2, "blue", (300, 100, 330, 120))
    )
    source = add_source(session, "report.pdf", original)

    run(source.id)

    session.expire_all()
    assert source.status is DocumentStatus.READY
    assert "Quarterly results." in (source.content or "")
    assert index(source) == {
        "version": 1,
        "figures": [
            {
                "n": 1,
                "caption": "Figure 1: The harbour at dawn.",
                "page": 1,
                "width": 120,
                "height": 80,
            },
            {"n": 2, "caption": None, "page": 2, "width": 60, "height": 40},
        ],
    }
    assert sorted(path.name for path in figures_dir(source).iterdir()) == [
        "1.png",
        "2.png",
        "figures.json",
    ]
    for n, color in ((1, (255, 0, 0)), (2, (0, 0, 255))):
        with Image.open(figures_dir(source) / f"{n}.png") as kept:
            assert kept.format == "PNG"
            assert kept.getpixel((kept.width // 2, kept.height // 2)) == color


def test_a_letterhead_logo_on_every_page_is_kept_once(
    session: Session, stub_model: None, docling: list[Any]
) -> None:
    """Page furniture counts: a logo there is the picture a user asks for."""
    logo = (40, 780, 80, 800)
    docling.append(
        reading(
            *(
                {"page": page, "box": logo, "layer": ContentLayer.FURNITURE}
                for page in (1, 2, 3)
            ),
            {"page": 2, "box": (100, 300, 130, 320)},
        )
    )
    original = pdf_of(
        3,
        *((page, "green", logo) for page in (1, 2, 3)),
        (2, "red", (100, 300, 130, 320)),
    )
    source = add_source(session, "letter.pdf", original)

    run(source.id)

    assert [(entry["page"], entry["width"]) for entry in index(source)["figures"]] == [
        (1, 80),
        (2, 60),
    ]


def test_a_decks_pictures_keep_the_pixels_the_file_embeds(
    session: Session, stub_model: None, docling: list[Any], tmp_path: Path
) -> None:
    """Never a picture that points at a file, and never one with no pixels."""
    elsewhere = tmp_path / "elsewhere.png"
    png((30, 30)).save(elsewhere)
    docling.append(
        reading(
            {"image": ImageRef.from_pil(png((120, 80)), dpi=72), "page": 1},
            {"image": None, "page": 1},
            {
                "image": ImageRef(
                    mimetype="image/png",
                    dpi=72,
                    size=Size(width=30, height=30),
                    uri=elsewhere,
                ),
                "page": 2,
            },
            {"image": ImageRef.from_pil(png((60, 40), "blue"), dpi=72), "page": 2},
        )
    )
    source = add_source(session, "deck.pptx", b"PK fake")

    run(source.id)

    assert index(source) == {
        "version": 1,
        "figures": [
            {"n": 1, "caption": None, "page": 1, "width": 120, "height": 80},
            {"n": 2, "caption": None, "page": 2, "width": 60, "height": 40},
        ],
    }
    with Image.open(figures_dir(source) / "2.png") as kept:
        assert kept.getpixel((0, 0)) == (0, 0, 255)


def test_an_image_source_is_its_own_single_figure(
    session: Session, stub_model: None, docling: list[Any]
) -> None:
    """Upright as it displays, whatever regions Docling found inside it."""
    sideways = io.BytesIO()
    exif = Image.Exif()
    exif[0x0112] = 6  # stored on its side; turn 90 degrees to display
    png((300, 200)).save(sideways, "JPEG", exif=exif)
    docling.append(
        reading({"image": ImageRef.from_pil(png((50, 50)), dpi=72), "page": 1})
    )
    source = add_source(session, "logo.jpg", sideways.getvalue())

    run(source.id)

    assert index(source) == {
        "version": 1,
        "figures": [
            {"n": 1, "caption": None, "page": None, "width": 200, "height": 300}
        ],
    }
    with Image.open(figures_dir(source) / "1.png") as kept:
        assert kept.size == (200, 300)


def test_a_text_upload_keeps_no_figures_even_when_docling_reads_it(
    session: Session, stub_model: None, docling: list[Any]
) -> None:
    """An HTML page's pictures are links Docling does not fetch; text has none."""
    docling.append(
        reading({"image": ImageRef.from_pil(png((50, 50)), dpi=72), "page": 1})
    )
    source = add_source(session, "page.html", b"<p>Quarterly results.</p>")

    run(source.id)

    session.expire_all()
    assert source.status is DocumentStatus.READY
    assert not figures_dir(source).exists()


def test_failing_to_keep_figures_does_not_fail_the_ingest(
    session: Session, stub_model: None, docling: list[Any]
) -> None:
    """The text is the source; its figures are a convenience recorded as failed."""

    class Unreadable:
        def export_to_markdown(self) -> str:
            return "Quarterly results."

        def iterate_items(self, **_options: object) -> Iterator[Any]:
            raise RuntimeError("the picture tree is corrupt")

    docling.append(Unreadable())
    source = add_source(session, "deck.pptx", b"PK fake")

    run(source.id)

    session.expire_all()
    assert source.status is DocumentStatus.READY
    assert index(source) == {
        "version": 1,
        "figures": [],
        "error": "RuntimeError: the picture tree is corrupt",
    }


def test_a_second_ingest_replaces_the_figures_of_the_first(
    session: Session, stub_model: None, docling: list[Any]
) -> None:
    """A retry must not leave a figure the new index does not list."""
    docling.append(
        reading(
            {"image": ImageRef.from_pil(png((10, 10)), dpi=72), "page": 1},
            {"image": ImageRef.from_pil(png((20, 20)), dpi=72), "page": 2},
        )
    )
    docling.append(
        reading({"image": ImageRef.from_pil(png((30, 30)), dpi=72), "page": 1})
    )
    source = add_source(session, "deck.pptx", b"PK fake")
    run(source.id)
    source.status = DocumentStatus.PENDING
    session.commit()

    run(source.id)

    assert [entry["width"] for entry in index(source)["figures"]] == [30]
    assert not (figures_dir(source) / "2.png").exists()


def test_the_figures_pass_keeps_a_ready_sources_figures_and_leaves_its_text(
    session: Session, docling: list[Any]
) -> None:
    """For sources ingested before figures were kept: their text stays as it was."""
    docling.append(
        reading({"caption": "Figure 1: Costs.", "page": 3, "box": (50, 50, 110, 90)})
    )
    source = add_source(
        session,
        "report.pdf",
        pdf_of(3, (3, "red", (50, 50, 110, 90))),
        status=DocumentStatus.READY,
    )

    extract_figures.call_local(source.id)

    session.expire_all()
    assert index(source)["figures"] == [
        {"n": 1, "caption": "Figure 1: Costs.", "page": 3, "width": 120, "height": 80}
    ]
    assert source.status is DocumentStatus.READY
    assert source.content == "The text ingest extracted."
    assert session.scalar(select(func.count()).select_from(Chunk)) == 0


def test_the_figures_pass_needs_no_parser_for_an_image_source(
    session: Session, docling: list[Any]
) -> None:
    """The fixture fails the test if Docling is asked to read anything."""
    photo = io.BytesIO()
    png((40, 30)).save(photo, "PNG")
    source = add_source(
        session, "logo.png", photo.getvalue(), status=DocumentStatus.READY
    )

    extract_figures.call_local(source.id)

    assert index(source)["figures"] == [
        {"n": 1, "caption": None, "page": None, "width": 40, "height": 30}
    ]


def test_the_figures_pass_records_a_file_docling_cannot_read(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Recorded, so asking for the figures again does not queue the pass forever."""

    def unreadable(_source: object) -> None:
        raise ValueError("not a PDF")

    monkeypatch.setattr(
        "worker.ingestion.parsing._converter",
        lambda: SimpleNamespace(convert=unreadable),
    )
    source = add_source(
        session, "report.pdf", b"%PDF-1.7 fake", status=DocumentStatus.READY
    )

    extract_figures.call_local(source.id)

    assert index(source) == {
        "version": 1,
        "figures": [],
        "error": "ValueError: not a PDF",
    }


def test_the_figures_pass_leaves_kept_and_unready_sources_alone(
    session: Session, docling: list[Any]
) -> None:
    """Ingest keeps an unready source's figures; kept ones are not read twice."""
    pending = add_source(session, "draft.pdf", b"%PDF-1.7 fake")
    kept = add_source(session, "report.pdf", b"%PDF-1.7 fake", DocumentStatus.READY)
    figures_dir(kept).mkdir()
    (figures_dir(kept) / "figures.json").write_text(
        json.dumps({"version": 1, "figures": []}), encoding="utf-8"
    )

    extract_figures.call_local(pending.id)
    extract_figures.call_local(kept.id)
    extract_figures.call_local(9999)

    assert not figures_dir(pending).exists()
    assert index(kept) == {"version": 1, "figures": []}
