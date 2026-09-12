import pytest

from worker.ingestion.chunking import chunk

pytestmark = pytest.mark.unit

# A character tokenizer keeps the unit tests off the bundled model: one token
# per character, so the budget below reads as a character count.
BUDGET = 80


def chunked(markdown: str, chunk_size: int = BUDGET):
    """Chunk with the character tokenizer, so the tests carry no model."""
    return chunk(markdown, tokenizer="character", chunk_size=chunk_size)


def test_a_short_document_is_one_chunk() -> None:
    """Splitting a page into pieces would only scatter its meaning."""
    chunks = chunked("# Title\n\nOne short paragraph.\n")

    assert len(chunks) == 1
    assert chunks[0].text == "# Title\n\nOne short paragraph."


def test_no_chunk_exceeds_the_budget() -> None:
    """Past the model's window the tail of a chunk is embedded as nothing."""
    chunks = chunked("\n\n".join(f"Paragraph {n}." for n in range(200)))

    assert len(chunks) > 1
    assert all(len(piece.text) <= BUDGET for piece in chunks)


def test_a_long_single_line_is_still_split() -> None:
    """A minified file is one line, and it cannot stay one oversized chunk."""
    chunks = chunked("word " * 300)

    assert len(chunks) > 1
    assert all(len(piece.text) <= BUDGET for piece in chunks)


def test_a_heading_leads_the_section_it_names() -> None:
    """A heading stranded at the end of a chunk names a section it does not hold."""
    sections = "\n\n".join(f"## Section {n}\n\n" + "body " * 40 for n in range(10))

    for piece in chunked(sections, chunk_size=300):
        assert not piece.text.splitlines()[-1].lstrip().startswith("#")


def test_line_numbers_point_at_the_source() -> None:
    """The span marks the lines holding the chunk's first and last characters."""
    markdown = "\n\n".join(f"Paragraph {n} of the document." for n in range(200))

    for piece in chunked(markdown):
        offset = markdown.index(piece.text)
        assert piece.start_line == markdown.count("\n", 0, offset) + 1
        assert (
            piece.end_line == markdown.count("\n", 0, offset + len(piece.text) - 1) + 1
        )


def test_an_empty_document_has_no_chunks() -> None:
    """A note someone created and has not written yet is not a failure."""
    assert chunked("   \n\n  \n") == []
