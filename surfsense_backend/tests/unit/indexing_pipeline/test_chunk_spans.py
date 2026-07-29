"""Line spans must name the exact slice a chunk was cut from.

Spans are what a search excerpt renders line numbers from, so an off-by-one here
points a reader at the wrong line. Every case asserts against the document's own
lines rather than against hardcoded numbers, so the assertions stay true if the
fixture text is edited.
"""

from __future__ import annotations

from app.indexing_pipeline.document_chunker import attach_line_spans


def slice_of(text: str, span) -> str:
    """The document lines a span claims, as the reader would see them."""
    lines = text.split("\n")
    return "\n".join(lines[span.start_line - 1 : span.end_line])


def test_a_single_line_chunk_claims_exactly_its_line():
    text = "alpha\nbravo\ncharlie"

    spans = attach_line_spans(text, ["bravo"])

    assert (spans[0].start_line, spans[0].end_line) == (2, 2)


def test_every_chunk_span_slices_back_to_its_own_text():
    text = "# Title\n\nFirst paragraph.\n\nSecond paragraph.\n"
    chunks = ["# Title", "First paragraph.", "Second paragraph."]

    spans = attach_line_spans(text, chunks)

    for span in spans:
        assert span.text in slice_of(text, span)


def test_a_multi_line_chunk_spans_from_its_first_line_to_its_last():
    text = "intro\n\nline one\nline two\nline three\n\noutro"
    chunk = "line one\nline two\nline three"

    span = attach_line_spans(text, [chunk])[0]

    assert (span.start_line, span.end_line) == (3, 5)
    assert slice_of(text, span) == chunk


def test_a_chunk_ending_in_a_newline_does_not_claim_the_next_line():
    """The trailing newline belongs to the chunk's last line, not the one after."""
    text = "first\nsecond\nthird"

    span = attach_line_spans(text, ["first\nsecond\n"])[0]

    assert (span.start_line, span.end_line) == (1, 2)


def test_repeated_text_resolves_to_each_occurrence_in_order():
    """A whole-document search would pin both chunks to line 1; the cursor cannot."""
    text = "duplicate\nmiddle\nduplicate\n"

    spans = attach_line_spans(text, ["duplicate", "duplicate"])

    assert [(s.start_line, s.end_line) for s in spans] == [(1, 1), (3, 3)]


def test_a_markdown_table_kept_whole_spans_all_of_its_rows():
    """The hybrid chunker emits a table as one chunk and strips it as it goes."""
    text = "Before the table.\n\n| a | b |\n| - | - |\n| 1 | 2 |\n\nAfter the table.\n"
    table = "| a | b |\n| - | - |\n| 1 | 2 |"

    spans = attach_line_spans(text, ["Before the table.", table, "After the table."])

    assert [(s.start_line, s.end_line) for s in spans] == [(1, 1), (3, 5), (7, 7)]
    assert slice_of(text, spans[1]) == table


def test_a_chunk_that_is_not_in_the_document_falls_back_to_the_cursor():
    """A chunker that rewrites text must degrade to a plausible line, not crash."""
    text = "alpha\nbravo\ncharlie\n"

    spans = attach_line_spans(text, ["alpha", "REWRITTEN"])

    assert spans[1].start_line >= spans[0].start_line
    assert spans[1].start_line <= text.count("\n") + 1


def test_no_chunks_yields_no_spans():
    assert attach_line_spans("anything", []) == []
