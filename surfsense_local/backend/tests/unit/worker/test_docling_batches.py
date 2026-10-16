"""A long Docling reading's batches: how pages are cut, how the batches join into
the reading one conversion of all their pages makes, and when kept ones are
read again."""

from pathlib import Path

import pytest
from docling_core.types.doc import (
    BoundingBox,
    ContentLayer,
    CoordOrigin,
    DocItemLabel,
    DoclingDocument,
    ProvenanceItem,
    Size,
)
from reportlab.lib.pagesizes import A4

from worker.ingestion.docling_batches import checkpoint
from worker.ingestion.docling_batches.checkpoint import ReadingCheckpoint
from worker.ingestion.docling_batches.joined import joined
from worker.ingestion.docling_batches.page_runs import (
    PageRun,
    batches_of,
    described,
    runs_of,
)

pytestmark = pytest.mark.unit

# What a page holds, in reading order: (label, text) of each item.
Page = list[tuple[DocItemLabel, str]]


def place(page: int, start: int, text: str) -> ProvenanceItem:
    """Where Docling read a text: its page, a line across it, and its span."""
    return ProvenanceItem(
        page_no=page,
        bbox=BoundingBox(
            l=72, b=100, r=500, t=120, coord_origin=CoordOrigin.BOTTOMLEFT
        ),
        charspan=(start, start + len(text)),
    )


def reading(first: int, pages: list[Page]) -> DoclingDocument:
    """A conversion of the pages from `first` on, each item on its own page."""
    document = DoclingDocument(name="report")
    for n, items in enumerate(pages, start=first):
        document.add_page(page_no=n, size=Size(width=A4[0], height=A4[1]))
        for label, text in items:
            furniture = label in (DocItemLabel.PAGE_HEADER, DocItemLabel.PAGE_FOOTER)
            document.add_text(
                label=label,
                text=text,
                prov=place(n, 0, text),
                content_layer=ContentLayer.FURNITURE if furniture else None,
            )
    return document


def texts(document: DoclingDocument) -> list[tuple[str, list[tuple[int, tuple]]]]:
    """Each text item, with every page it lies on and the span it takes there."""
    return [
        (item.text, [(p.page_no, tuple(p.charspan)) for p in item.prov])
        for item, _level in document.iterate_items()
    ]


TEXT, FOOTER, HEADER = (
    DocItemLabel.TEXT,
    DocItemLabel.PAGE_FOOTER,
    DocItemLabel.PAGE_HEADER,
)


def test_flagged_pages_are_runs_and_runs_are_cut_into_batches() -> None:
    """Eight pages a batch, the last one shorter; a reader's page list in the log."""
    runs = runs_of([1, 4, 5, 6, 9])

    assert runs == [PageRun(1, 1), PageRun(4, 6), PageRun(9, 9)]
    assert described(runs) == "1, 4-6, 9"
    assert batches_of(PageRun(1, 20)) == [
        PageRun(1, 8),
        PageRun(9, 16),
        PageRun(17, 20),
    ]
    assert batches_of(PageRun(3, 3)) == [PageRun(3, 3)]


def test_a_paragraph_running_on_past_a_batch_is_one_text_again() -> None:
    """As Docling joins it, past the page's footer and the next page's header,
    with each part's place and span as Docling counts them."""
    before = reading(
        1, [[(TEXT, "Harbour dues rose."), (TEXT, "The crane budget"), (FOOTER, "1")]]
    )
    after = reading(
        2,
        [[(HEADER, "Budget"), (TEXT, "covers two berths."), (TEXT, "Dredging ends.")]],
    )

    whole = joined([(PageRun(1, 1), before), (PageRun(2, 2), after)])

    assert texts(whole) == [
        ("Harbour dues rose.", [(1, (0, 18))]),
        ("The crane budget covers two berths.", [(1, (0, 16)), (2, (17, 35))]),
        ("Dredging ends.", [(2, (0, 14))]),
    ]
    assert sorted(whole.pages) == [1, 2]


def test_a_word_split_at_a_batch_edge_is_one_word_again() -> None:
    """A hyphen before a lower-case letter splits a word, as Docling reads it."""
    before = reading(1, [[(TEXT, "The terminal's through-")]])
    after = reading(2, [[(TEXT, "put doubled.")]])

    whole = joined([(PageRun(1, 1), before), (PageRun(2, 2), after)])

    assert [text for text, _places in texts(whole)] == [
        "The terminal's throughput doubled."
    ]


def test_a_closed_sentence_or_a_heading_is_not_joined() -> None:
    """Only an open end going on into a word joins."""
    closed = reading(1, [[(TEXT, "Harbour dues rose.")]])
    going_on = reading(2, [[(TEXT, "berths reopened.")]])
    open_end = reading(3, [[(TEXT, "The crane budget")]])
    heading = reading(4, [[(DocItemLabel.SECTION_HEADER, "Dredging")]])

    whole = joined(
        [
            (PageRun(1, 1), closed),
            (PageRun(2, 2), going_on),
            (PageRun(3, 3), open_end),
            (PageRun(4, 4), heading),
        ]
    )

    assert [text for text, _places in texts(whole)] == [
        "Harbour dues rose.",
        "berths reopened.",
        "The crane budget",
        "Dredging",
    ]


def test_a_text_runs_on_past_a_batch_with_nothing_to_read() -> None:
    """A blank batch between leaves the paragraph open, as one reading sees it."""
    before = reading(1, [[(TEXT, "The crane budget")]])
    blank = reading(2, [[]])
    after = reading(3, [[(TEXT, "covers two berths.")]])

    whole = joined(
        [(PageRun(1, 1), before), (PageRun(2, 2), blank), (PageRun(3, 3), after)]
    )

    assert [text for text, _places in texts(whole)] == [
        "The crane budget covers two berths."
    ]


@pytest.mark.parametrize("lost", [2, 3], ids=["last-of-a-batch", "first-of-a-batch"])
def test_a_page_a_batch_lost_leaves_every_later_page_in_place(lost: int) -> None:
    """Joining numbers each batch's pages on from the last one's; the lost page is
    kept empty, so what Docling read on page 4 stays on page 4."""
    pages = {
        1: "Harbour dues rose.",
        2: "Cranes were idle.",
        3: "Dredging ends.",
        4: "Berth four reopens.",
    }
    batches = []
    for run in (PageRun(1, 2), PageRun(3, 4)):
        read = DoclingDocument(name="report")
        for n in run.pages:
            if n != lost:
                read.add_page(page_no=n, size=Size(width=A4[0], height=A4[1]))
                read.add_text(label=TEXT, text=pages[n], prov=place(n, 0, pages[n]))
        batches.append((run, read))

    whole = joined(batches)

    assert [(text, places[0][0]) for text, places in texts(whole)] == [
        (pages[n], n) for n in pages if n != lost
    ]
    assert sorted(whole.pages) == [1, 2, 3, 4]


@pytest.mark.parametrize("change", ["docling", "format", "parser pack"])
def test_batches_kept_by_another_docling_format_or_parser_pack_are_read_again(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, change: str
) -> None:
    """Each can read the same bytes otherwise, so the batches would not join as
    one reading."""
    original = tmp_path / "scan.pdf"
    original.write_bytes(b"%PDF-1.7 a scan")
    work = tmp_path / "docling" / "work"
    kept = ReadingCheckpoint(work, original, root=tmp_path / "docling")
    assert kept.keep("pages-1-8", reading(1, [[(TEXT, "Harbour dues rose.")]]))
    assert ReadingCheckpoint(work, original).done("pages-1-8") is not None

    if change == "docling":
        monkeypatch.setattr(checkpoint, "version", lambda _name: "0.0.1")
    elif change == "format":
        monkeypatch.setattr(checkpoint, "_FORMAT", checkpoint._FORMAT + 1)
    else:
        pack_missing = bool(checkpoint.missing_parser_folders())
        monkeypatch.setattr(
            checkpoint,
            "missing_parser_folders",
            lambda: [] if pack_missing else ["RapidOcr"],
        )

    assert ReadingCheckpoint(work, original).done("pages-1-8") is None
    assert not work.exists()
