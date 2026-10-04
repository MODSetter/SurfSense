"""The name an upload is stored under inside its document folder."""

import pytest

from modules.documents.original_file import stored_name

pytestmark = pytest.mark.unit


def test_an_upload_keeps_its_own_name() -> None:
    """Finder and the PDF viewer show this name, not original.pdf."""
    assert stored_name("Q3 report.pdf", ".pdf") == "Q3 report.pdf"


@pytest.mark.parametrize(
    ("filename", "suffix", "expected"),
    [
        ("Report.PDF", ".pdf", "Report.pdf"),
        # An imported title carries no extension of its own.
        ("Notes", ".md", "Notes.md"),
        ("v1.2 plan", ".md", "v1.2 plan.md"),
    ],
)
def test_the_extension_is_the_one_that_was_validated(
    filename: str, suffix: str, expected: str
) -> None:
    """Lowercased, so the OS opens the file with the app for its type."""
    assert stored_name(filename, suffix) == expected


@pytest.mark.parametrize(
    ("filename", "expected"),
    [
        ("Q3: plan?.pdf", "Q3 plan.pdf"),
        ("tab\there\x7f.pdf", "tabhere.pdf"),
        ("CON.pdf", "CON_.pdf"),
        ("nul.pdf", "nul_.pdf"),
    ],
)
def test_a_name_no_filesystem_accepts_is_made_safe_everywhere(
    filename: str, expected: str
) -> None:
    """Stored on one machine, a workspace must still open on Windows."""
    assert stored_name(filename, ".pdf") == expected


def test_a_stored_file_is_never_hidden() -> None:
    """A dot-file is skipped when the folder is searched for its original."""
    assert stored_name(".env notes.md", ".md") == "env notes.md"


@pytest.mark.parametrize("filename", ["", "???.pdf", "..."])
def test_a_name_with_nothing_left_is_untitled(filename: str) -> None:
    """A file needs a name even when every character of its own was unsafe."""
    assert stored_name(filename, ".pdf") == "untitled.pdf"


@pytest.mark.parametrize("filename", ["extracted.md", "Extracted.MD"])
def test_an_upload_never_takes_the_legacy_extracted_name(filename: str) -> None:
    """The search for the original skips extracted.md, so an upload cannot use it."""
    assert stored_name(filename, ".md").casefold() == "extracted (1).md"


def test_a_long_name_is_cut_before_its_extension() -> None:
    """Filesystems cap a name at 255 bytes, and a multibyte name reaches that first."""
    name = stored_name("é" * 300 + ".pdf", ".pdf")

    assert name.endswith("é.pdf")
    assert len(name.encode()) <= 120


def test_a_long_name_leaves_room_for_the_folder_under_windows_path_limit() -> None:
    """MAX_PATH is 260 for the whole path, and the data folder takes about 70."""
    name = stored_name("a" * 250 + ".pdf", ".pdf")

    assert name == "a" * 116 + ".pdf"
