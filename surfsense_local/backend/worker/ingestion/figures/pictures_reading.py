"""Docling's reading of a PDF for its pictures: layout alone where it finds the same.

A picture's place comes from the layout model and its caption from the text
layer, so a born-digital page needs neither OCR nor TableFormer, most of a full
reading's time. A scanned page keeps the full reading, as only OCR reads its
captions. So does a page with a picture and a caption the text layer lacks, and
a page with a picture inside a table, which TableFormer files under the table's
cell and so can move in the order.
"""

from collections.abc import Callable, Iterator, Sequence
from itertools import groupby
from pathlib import Path
from typing import Any, NamedTuple

from worker.ingestion.docling_batches.checkpoint import ReadingCheckpoint
from worker.ingestion.docling_batches.lost_pages import with_every_page
from worker.ingestion.docling_batches.page_runs import BATCH_PAGES
from worker.ingestion.figures import run_reading


class _Run(NamedTuple):
    first: int
    last: int
    full: bool


def read_for_pictures(
    pdf: Path,
    scanned: Sequence[bool],
    kept: ReadingCheckpoint | None = None,
    between_runs: Callable[[], None] | None = None,
) -> Any:
    """The PDF's DoclingDocument, read a run of like pages at a time.

    `scanned` says, for each page, whether it is a scan. Docling finds, orders
    and captions pictures one page at a time, so the pages join into the
    reading of the whole file. With `kept`, each run read is kept there and
    one read already is not read again; `between_runs` may raise to stop the
    reading between two runs.
    """
    reader = _Reader(pdf, kept, between_runs)
    readings: list[tuple[_Run, Any]] = []
    again: set[int] = set()
    for run in _runs(scanned):
        if run.full:
            readings.append((run, reader.in_full(run, "full")))
            continue
        document, needs_full = reader.by_layout(run)
        readings.append((run, document))
        again |= needs_full
    # Only those pages again: a later reading of a page replaces the earlier.
    for run in _runs([n in again for n in range(1, len(scanned) + 1)]):
        if run.full:
            readings.append((run, reader.in_full(run, "again")))
    return _joined(readings, len(scanned))


class _Reader:
    """Docling's readings of runs, each kept as it comes when a checkpoint is given."""

    def __init__(
        self,
        pdf: Path,
        kept: ReadingCheckpoint | None,
        between_runs: Callable[[], None] | None,
    ) -> None:
        self._pdf = pdf
        self._kept = kept
        self._between_runs = between_runs
        self._read_here = False
        self._all_kept = True  # stopping now loses no run read

    def in_full(self, run: _Run, round_name: str) -> Any:
        name = f"{round_name}-{run.first}-{run.last}"
        found = self._kept.done(name) if self._kept else None
        if found is not None:
            return found[0]
        self._before_reading()
        document = _whole(run_reading.read_in_full(self._pdf, run.first, run.last), run)
        self._keep(name, document)
        return document

    def by_layout(self, run: _Run) -> tuple[Any, set[int]]:
        name = f"layout-{run.first}-{run.last}"
        found = self._kept.done(name) if self._kept else None
        if found is not None:
            return found[0], set(found[1])
        self._before_reading()
        layout = run_reading.read_by_layout(self._pdf, run.first, run.last)
        document = _whole(layout.document, run)
        needs_full = _pages_for_the_full_reading(layout)
        self._keep(name, document, sorted(needs_full))
        return document, needs_full

    def _before_reading(self) -> None:
        if self._read_here and self._all_kept and self._between_runs is not None:
            self._between_runs()
        self._read_here = True

    def _keep(self, name: str, document: Any, notes: Any = None) -> None:
        if self._kept is not None:
            self._all_kept = self._kept.keep(name, document, notes) and self._all_kept


def _whole(document: Any, run: _Run) -> Any:
    # Joining renumbers each reading's pages from where the last one ended.
    pages = range(run.first, run.last + 1)
    if set(with_every_page(document, pages).pages) != set(pages):
        raise ValueError(f"the reading of pages {run.first}-{run.last} has others")
    return document


def _runs(in_full: Sequence[bool]) -> Iterator[_Run]:
    """Runs of like pages, cut into batches: the pass can stop between any two."""
    first = 1
    for full, pages in groupby(in_full):
        last = first + len(list(pages)) - 1
        for start in range(first, last + 1, BATCH_PAGES):
            yield _Run(start, min(start + BATCH_PAGES - 1, last), full)
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
