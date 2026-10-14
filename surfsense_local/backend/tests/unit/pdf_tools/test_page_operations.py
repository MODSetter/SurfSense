"""Merging, extracting, splitting, rotating and reordering pages: always new bytes."""

from io import BytesIO

import pypdf
import pytest

from modules.pdf_tools import opened_pdf
from modules.pdf_tools.opened_pdf import open_pdf
from modules.pdf_tools.page_operations import extract, merge, reorder, rotate, split
from modules.pdf_tools.refusal import PdfRefusedError
from tests.unit.pdf_tools.pdfs import numbered, texts

pytestmark = pytest.mark.unit


def test_merge_keeps_each_pdfs_pages_in_the_order_given() -> None:
    """The order of the call is the order of the result."""
    first = open_pdf(numbered(2, "First"), "a")
    second = open_pdf(numbered(1, "Second"), "b")

    merged = merge([second, first])

    assert texts(merged) == ["Second 1", "First 1", "First 2"]


def test_a_merge_past_the_page_cap_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    """The result is held to the same cap as an input."""
    monkeypatch.setattr(opened_pdf, "MAX_PAGES", 3)
    readers = [open_pdf(numbered(2), "a"), open_pdf(numbered(2), "b")]

    with pytest.raises(PdfRefusedError, match="would have 4 pages"):
        merge(readers)


def test_extract_keeps_the_pages_named_in_their_order() -> None:
    """Extract can reorder as it takes pages out."""
    reader = open_pdf(numbered(5), "a")

    assert texts(extract(reader, [4, 1, 2])) == ["Page 4", "Page 1", "Page 2"]


def test_an_extract_naming_more_pages_than_the_cap_is_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Repeating a range can name more pages than any input has."""
    monkeypatch.setattr(opened_pdf, "MAX_PAGES", 3)

    with pytest.raises(PdfRefusedError, match="names 4 pages"):
        extract(open_pdf(numbered(1), "a"), [1, 1, 1, 1])


def test_split_makes_one_pdf_per_group() -> None:
    """One part per range the model wrote."""
    reader = open_pdf(numbered(5), "a")

    parts = split(reader, [[1, 2], [3], [4, 5]])

    assert [texts(part) for part in parts] == [
        ["Page 1", "Page 2"],
        ["Page 3"],
        ["Page 4", "Page 5"],
    ]


def test_rotate_turns_only_the_pages_named_clockwise() -> None:
    """Pages not named keep their turn."""
    reader = open_pdf(numbered(3), "a")

    rotated = pypdf.PdfReader(BytesIO(rotate(reader, [2, 3], 90)))

    assert [page.rotation for page in rotated.pages] == [0, 90, 90]


def test_rotating_adds_to_a_pages_own_rotation() -> None:
    """A page already shown turned is turned further, and the angle wraps."""
    once = open_pdf(rotate(open_pdf(numbered(1), "a"), [1], 270), "a")

    twice = pypdf.PdfReader(BytesIO(rotate(once, [1], 180)))

    assert twice.pages[0].rotation == 90


@pytest.mark.parametrize("angle", [45, 0, 360])
def test_an_angle_that_is_not_a_quarter_turn_is_refused(angle: int) -> None:
    """PDF pages turn only in quarter turns."""
    with pytest.raises(PdfRefusedError, match="90, 180 or 270"):
        rotate(open_pdf(numbered(1), "a"), [1], angle)


def test_reorder_puts_every_page_in_the_new_order() -> None:
    """The whole PDF, in the order named."""
    reader = open_pdf(numbered(3), "a")

    assert texts(reorder(reader, [3, 1, 2])) == ["Page 3", "Page 1", "Page 2"]


def test_a_reorder_that_drops_or_repeats_a_page_says_which() -> None:
    """A reorder that loses a page is a mistake; extract is for keeping some."""
    reader = open_pdf(numbered(4), "a")

    with pytest.raises(PdfRefusedError) as refused:
        reorder(reader, [3, 1, 1])

    assert "page 1 is named twice" in str(refused.value)
    assert "pages 2 and 4 are missing" in str(refused.value)
    assert "extract" in str(refused.value)


def test_the_pdf_read_is_left_as_it_was() -> None:
    """Every operation writes a copy; a second call on the same PDF sees it unchanged."""
    original = numbered(3)
    reader = open_pdf(original, "a")

    rotate(reader, [1], 90)
    extract(reader, [2])

    assert [page.rotation for page in reader.pages] == [0, 0, 0]
