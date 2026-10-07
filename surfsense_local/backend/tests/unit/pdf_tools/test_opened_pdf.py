"""Opening a PDF for the PDF tools: what is refused, and in which sentence."""

import pytest

from modules.pdf_tools import opened_pdf
from modules.pdf_tools.opened_pdf import open_pdf
from modules.pdf_tools.refusal import PdfRefusedError
from tests.unit.pdf_tools.pdfs import locked, numbered

pytestmark = pytest.mark.unit


def test_a_pdf_opens_with_its_pages() -> None:
    """The ordinary case."""
    assert len(open_pdf(numbered(3), "Source 7").pages) == 3


def test_bytes_that_are_not_a_pdf_are_refused_by_name() -> None:
    """A file named .pdf may be anything; the sentence names which."""
    with pytest.raises(PdfRefusedError) as refused:
        open_pdf(b"PK\x03\x04 a zip, not a PDF", 'Source 7 ("Plan.pdf")')

    assert str(refused.value).startswith('Source 7 ("Plan.pdf") could not be read')


def test_a_cut_off_pdf_is_refused() -> None:
    """A damaged file fails anywhere in the parser; the model gets one sentence."""
    with pytest.raises(PdfRefusedError, match="could not be read as a PDF"):
        open_pdf(numbered(3)[:200], "Source 7")


def test_a_pdf_that_needs_a_password_is_refused() -> None:
    """Only the user can unlock it, so the sentence says to ask them."""
    with pytest.raises(PdfRefusedError) as refused:
        open_pdf(locked(numbered(1), user_password="secret"), "Source 7")

    assert "password" in str(refused.value)
    assert "without the password" in str(refused.value)


def test_a_pdf_locked_only_against_changes_opens_with_the_empty_password() -> None:
    """Every viewer opens such a file without asking, so the tools do too."""
    reader = open_pdf(locked(numbered(2), user_password=""), "Source 7")

    assert len(reader.pages) == 2
    assert "Page 2" in reader.pages[1].extract_text()


def test_a_pdf_with_more_pages_than_the_cap_is_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A call must answer inside the tool's timeout."""
    monkeypatch.setattr(opened_pdf, "MAX_PAGES", 4)

    with pytest.raises(PdfRefusedError) as refused:
        open_pdf(numbered(5), "Source 7")

    assert str(refused.value) == (
        "Source 7 has 5 pages; the PDF tools work on files of at most 4 pages."
    )


def test_a_file_larger_than_the_cap_is_refused_before_it_is_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """pypdf holds the whole file in memory."""
    monkeypatch.setattr(opened_pdf, "MAX_BYTES", 100)

    with pytest.raises(PdfRefusedError, match="larger than the PDF tools take"):
        open_pdf(numbered(1), "Source 7")
