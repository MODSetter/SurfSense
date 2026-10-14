"""The names a revised copy is saved under: the source's, so the user knows which file it is."""

import pytest

from modules.artifacts.revised_copies.downloads import NAME_BYTES, download_name

pytestmark = pytest.mark.unit


def test_the_name_is_the_source_stem_the_suffix_and_the_version() -> None:
    """The user's own file name, marked as revised and numbered."""
    assert download_name("MSA_Acme.docx", 3, "revised") == "MSA_Acme (revised v3).docx"


def test_a_macro_workbook_keeps_its_suffix() -> None:
    """An .xlsm saved as .xlsx would lose its macros."""
    assert download_name("Budget.xlsm", 1, "clean") == "Budget (clean v1).xlsm"


def test_characters_no_file_system_takes_are_dropped_from_the_suffix() -> None:
    """A translated suffix cannot break the saved name."""
    assert download_name("Plan.docx", 2, 're<vi>sed:/"') == "Plan (revised v2).docx"


def test_a_windows_device_name_gets_a_leading_underscore() -> None:
    """Windows refuses to save a file named like a device."""
    assert download_name("con.docx", 1, "revised") == "_con (revised v1).docx"


def test_a_long_name_is_cut_to_fit_and_keeps_its_ending() -> None:
    """The stem gives way; the suffix, version and extension stay."""
    name = download_name("é" * 300 + ".docx", 12, "überarbeitet")

    assert len(name.encode()) <= NAME_BYTES
    assert name.endswith(" (überarbeitet v12).docx")
