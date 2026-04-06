"""Tests for the DOCUMENT_EXTENSIONS allowlist module."""

import pytest

pytestmark = pytest.mark.unit


def test_pdf_is_supported_document():
    from app.utils.file_extensions import is_supported_document_extension

    assert is_supported_document_extension("report.pdf") is True


def test_exe_is_not_supported_document():
    from app.utils.file_extensions import is_supported_document_extension

    assert is_supported_document_extension("malware.exe") is False


@pytest.mark.parametrize("filename", [
    "report.pdf", "doc.docx", "old.doc",
    "sheet.xlsx", "legacy.xls",
    "slides.pptx", "deck.ppt",
    "photo.png", "photo.jpg", "photo.jpeg", "scan.bmp", "scan.tiff", "scan.tif",
    "manual.rtf", "book.epub",
    "letter.odt", "data.ods", "presentation.odp",
    "korean.hwpx",
])
def test_document_extensions_are_supported(filename):
    from app.utils.file_extensions import is_supported_document_extension

    assert is_supported_document_extension(filename) is True, f"{filename} should be supported"


@pytest.mark.parametrize("filename", [
    "malware.exe", "archive.zip", "video.mov", "font.woff2",
    "model.blend", "random.xyz", "data.parquet", "package.deb",
])
def test_non_document_extensions_are_not_supported(filename):
    from app.utils.file_extensions import is_supported_document_extension

    assert is_supported_document_extension(filename) is False, f"{filename} should NOT be supported"
