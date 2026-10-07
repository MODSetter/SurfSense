"""Page ranges as the model writes them: "1-3,7", "5-", "9-7"."""

import pytest

from modules.pdf_tools.page_ranges import page_groups, page_numbers
from modules.pdf_tools.refusal import PdfRefusedError

pytestmark = pytest.mark.unit


def test_numbers_and_ranges_come_back_in_the_order_written() -> None:
    """The order written is the order extract keeps."""
    assert page_numbers("1-3, 7", 9) == [1, 2, 3, 7]
    assert page_numbers("7,1-2", 9) == [7, 1, 2]


def test_an_open_range_runs_to_the_last_page() -> None:
    """The model need not know the page count."""
    assert page_numbers("8-", 10) == [8, 9, 10]


def test_a_falling_range_runs_backwards() -> None:
    """A reversed range reverses the pages."""
    assert page_numbers("3-1", 5) == [3, 2, 1]


def test_no_range_means_every_page() -> None:
    """Rotate and stamp work on every page by default."""
    assert page_numbers(None, 3) == [1, 2, 3]
    assert page_numbers("  ", 3) == [1, 2, 3]


def test_groups_keep_each_range_apart() -> None:
    """Split makes one part per comma-separated item."""
    assert page_groups("1-2,3,4-", 6) == [[1, 2], [3], [4, 5, 6]]


def test_a_page_past_the_end_is_refused_with_the_count() -> None:
    """The model corrects its range from the count."""
    with pytest.raises(PdfRefusedError) as refused:
        page_numbers("2-12", 9)

    assert str(refused.value) == "Page 12 is past the end: the PDF has 9 pages."


@pytest.mark.parametrize("written", ["1-3;7", "first", "0", "1--3", "-3", "2,,4"])
def test_text_that_is_not_a_range_is_refused_with_the_syntax(written: str) -> None:
    """The refusal shows the syntax, so the next call parses."""
    with pytest.raises(PdfRefusedError) as refused:
        page_numbers(written, 9)

    assert f'"{written}" is not a page range' in str(refused.value)
    assert '"1-3,7"' in str(refused.value)


def test_ranges_naming_more_pages_than_any_call_makes_are_refused() -> None:
    """Refused before the pages are counted out: a short string can name billions."""
    with pytest.raises(PdfRefusedError, match="20,000"):
        page_groups(",".join(["1-1000"] * 100_000), 1000)


def test_a_number_too_long_to_read_is_refused_in_a_sentence() -> None:
    """Python will not read a number of 4,300 digits; the model reads why."""
    with pytest.raises(PdfRefusedError, match="not a page range"):
        page_groups("9" * 5000, 10)


def test_a_refusal_repeats_only_the_start_of_a_long_range() -> None:
    """What the model wrote is not echoed back whole."""
    with pytest.raises(PdfRefusedError) as refused:
        page_groups("1," * 5000 + "x", 10)

    assert len(str(refused.value)) < 300
