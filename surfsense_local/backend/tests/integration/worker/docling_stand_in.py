"""Docling as a fixed reading built with docling-core, so a test needs none of its
models; test_figures_docling.py and test_parsing.py run the real parser."""

from types import SimpleNamespace
from typing import Any

import pytest
from docling_core.types.doc import (
    BoundingBox,
    CoordOrigin,
    DocItemLabel,
    DoclingDocument,
    ProvenanceItem,
    Size,
)
from reportlab.lib.pagesizes import A4


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
