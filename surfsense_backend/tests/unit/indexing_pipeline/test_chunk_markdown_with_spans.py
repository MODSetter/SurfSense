"""Span-aware chunking contract: slices form a lossless, contiguous partition
of the markdown, and every slice's char span addresses its own text."""

import pytest

from app.indexing_pipeline.document_chunker import chunk_markdown_with_spans

pytestmark = pytest.mark.unit


def _assert_lossless_partition(md: str, slices) -> None:
    assert "".join(s.text for s in slices) == md

    cursor = 0
    for s in slices:
        assert s.start_char == cursor, "slices must be contiguous"
        assert s.end_char >= s.start_char
        assert md[s.start_char : s.end_char] == s.text, "span must address slice text"
        cursor = s.end_char
    assert cursor == len(md)


def test_prose_partition_and_spans():
    md = (
        "# Title\n\n"
        + "First paragraph with several words here. " * 20
        + "\n\nSecond section with more prose to force multiple chunks. " * 20
    )

    slices = chunk_markdown_with_spans(md)

    assert len(slices) > 1
    _assert_lossless_partition(md, slices)


def test_table_kept_whole_with_exact_span():
    table = "| a | b |\n| - | - |\n| 1 | 2 |\n"
    md = f"Intro prose before the table.\n{table}\nClosing prose after."

    slices = chunk_markdown_with_spans(md)

    _assert_lossless_partition(md, slices)
    table_slices = [s for s in slices if s.text.lstrip().startswith("|")]
    assert any("| 1 | 2 |" in s.text for s in table_slices)
    for s in table_slices:
        assert "| a | b |" in s.text and "| 1 | 2 |" in s.text


def test_table_at_eof_without_trailing_newline_stays_whole():
    md = "Intro.\n| a | b |\n| - | - |\n| 1 | 2 |"

    slices = chunk_markdown_with_spans(md)

    _assert_lossless_partition(md, slices)
    table_slices = [s for s in slices if "| 1 | 2 |" in s.text]
    assert len(table_slices) == 1
    assert "| a | b |" in table_slices[0].text


def test_code_chunker_partition_and_spans():
    code = "\n\n".join(
        f"def func_{i}(x):\n    total = x + {i}\n    return total" for i in range(40)
    )

    slices = chunk_markdown_with_spans(code, use_code_chunker=True)

    assert len(slices) >= 1
    _assert_lossless_partition(code, slices)


def test_empty_markdown_yields_no_slices():
    assert chunk_markdown_with_spans("") == []
