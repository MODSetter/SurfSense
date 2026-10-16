"""Docling's reading of a PDF for its pictures: layout alone where it finds the same.

A picture's place comes from the layout model and its caption from the text
layer, so a born-digital page needs neither OCR nor TableFormer, most of a full
reading's time. A scanned page keeps the full reading, as only OCR reads its
captions. So does a page with a picture and a caption the text layer lacks, and
a page with a picture inside a table, which TableFormer files under the table's
cell and so can move in the order.
"""

from collections.abc import Iterator, Sequence
from itertools import groupby
from pathlib import Path
from typing import Any, NamedTuple

from worker.ingestion.figures import run_reading


class _Run(NamedTuple):
    first: int
    last: int
    full: bool


def read_for_pictures(pdf: Path, scanned: Sequence[bool]) -> Any:
    """The PDF's DoclingDocument, read a run of like pages at a time.

    `scanned` says, for each page, whether it is a scan. Docling finds, orders
    and captions pictures one page at a time, so the pages join into the
    reading of the whole file.
    """
    readings: list[tuple[_Run, Any]] = []
    again: set[int] = set()
    for run in _runs(scanned):
        if run.full:
            readings.append((run, _read(pdf, run)))
            continue
        layout = run_reading.read_by_layout(pdf, run.first, run.last)
        readings.append((run, _whole(layout.document, run)))
        again |= _pages_for_the_full_reading(layout)
    # Only those pages again: a later reading of a page replaces the earlier.
    for run in _runs([n in again for n in range(1, len(scanned) + 1)]):
        if run.full:
            readings.append((run, _read(pdf, run)))
    return _joined(readings, len(scanned))


def _read(pdf: Path, run: _Run) -> Any:
    return _whole(run_reading.read_in_full(pdf, run.first, run.last), run)


def _whole(document: Any, run: _Run) -> Any:
    # Joining renumbers each reading's pages from where the last one ended.
    if set(document.pages) != set(range(run.first, run.last + 1)):
        raise ValueError(f"the reading of pages {run.first}-{run.last} lacks some")
    return document


def _runs(in_full: Sequence[bool]) -> Iterator[_Run]:
    first = 1
    for full, pages in groupby(in_full):
        last = first + len(list(pages)) - 1
        yield _Run(first, last, full)
        first = last + 1


def _pages_for_the_full_reading(layout: run_reading.LayoutReading) -> set[int]:
    pictured = {
        picture.prov[0].page_no for picture in layout.document.pictures if picture.prov
    }
    return (pictured & layout.captions_for_ocr) | _pages_with_pictures_in_tables(
        layout.document
    )


def _pages_with_pictures_in_tables(reading: Any) -> set[int]:
    tables = [table.prov[0] for table in reading.tables if table.prov]
    return {
        picture.prov[0].page_no
        for picture in reading.pictures
        if picture.prov
        for table in tables
        if table.page_no == picture.prov[0].page_no
        # Looser than Docling's 0.8 of the picture inside one cell.
        and picture.prov[0].bbox.intersection_over_self(table.bbox) >= 0.5
    }


def _joined(readings: list[tuple[_Run, Any]], pages: int) -> Any:
    """Each page from the last reading of it, in page order."""
    source: dict[int, int] = {}
    for at, (run, _document) in enumerate(readings):
        source.update(dict.fromkeys(range(run.first, run.last + 1), at))
    parts = []
    for at, taken in groupby(range(1, pages + 1), key=source.__getitem__):
        run, document = readings[at]
        kept = list(taken)
        whole = (kept[0], kept[-1]) == (run.first, run.last)
        parts.append(document if whole else document.filter(page_nrs=set(kept)))
    if len(parts) == 1:
        return parts[0]
    from docling_core.types.doc import DoclingDocument

    return DoclingDocument.concatenate(parts)
