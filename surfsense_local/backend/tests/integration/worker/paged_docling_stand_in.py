"""Docling as a reading of exactly the pages it is asked for, built with
docling-core: each page a paragraph that names it, and a picture on the pages
a test gives one. It records what it was asked for and can act mid-reading."""

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pypdfium2
import pytest
from docling_core.types.doc import DocItemLabel, DoclingDocument, Size
from reportlab.lib.pagesizes import A4

from tests.integration.worker.docling_stand_in import provenance

Pages = tuple[int, int]


@dataclass
class PagedDocling:
    """`asked`: each conversion's pages, None for the whole file. `pictured`: pages
    with a picture. `lost`: pages a reading drops. `during`: called inside a
    conversion with its pages, as Docling runs."""

    asked: list[Pages | None] = field(default_factory=list)
    pictured: set[int] = field(default_factory=set)
    lost: set[int] = field(default_factory=set)
    during: Callable[[Pages | None], None] | None = None

    def reading(self, first: int, last: int) -> DoclingDocument:
        """What one conversion of pages first to last reads."""
        document = DoclingDocument(name="report")
        for page in range(first, last + 1):
            if page in self.lost:
                continue
            document.add_page(page_no=page, size=Size(width=A4[0], height=A4[1]))
            document.add_text(
                label=DocItemLabel.TEXT,
                text=f"Docling read page {page}.",
                prov=provenance(page, (72, 700, 400, 720)),
            )
            if page in self.pictured:
                document.add_picture(prov=provenance(page, (72, 300, 372, 525)))
        return document

    def markdown(self, first: int, last: int) -> str:
        """Its markdown, as one conversion of those pages writes it."""
        return self.reading(first, last).export_to_markdown()

    def convert(self, source: Path, page_range: Pages | None = None) -> SimpleNamespace:
        self.asked.append(page_range)
        if self.during is not None:
            self.during(page_range)
        if page_range is None:
            pdf = pypdfium2.PdfDocument(source)
            try:
                page_range = (1, len(pdf))
            finally:
                pdf.close()
        return SimpleNamespace(document=self.reading(*page_range))


@pytest.fixture
def paged_docling(monkeypatch: pytest.MonkeyPatch) -> PagedDocling:
    """Make Docling read every PDF page by page, as PagedDocling builds it."""
    docling = PagedDocling()

    def converter() -> Any:
        return SimpleNamespace(convert=docling.convert)

    monkeypatch.setattr("worker.ingestion.parsing._converter", converter)
    return docling
