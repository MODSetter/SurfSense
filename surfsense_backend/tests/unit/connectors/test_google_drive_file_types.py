"""Tests for Google Drive file type filtering."""

import pytest

from app.connectors.google_drive.file_types import should_skip_by_extension

pytestmark = pytest.mark.unit


@pytest.mark.parametrize("filename", [
    "malware.exe", "archive.zip", "video.mov", "font.woff2", "model.blend",
])
def test_unsupported_extensions_are_skipped_regardless_of_service(filename, mocker):
    """Truly unsupported files are skipped no matter which ETL service is configured."""
    for service in ("DOCLING", "LLAMACLOUD", "UNSTRUCTURED"):
        mocker.patch("app.config.config.ETL_SERVICE", service)
        skip, ext = should_skip_by_extension(filename)
        assert skip is True


@pytest.mark.parametrize("filename", [
    "report.pdf", "doc.docx", "sheet.xlsx", "slides.pptx",
    "readme.txt", "data.csv", "photo.png", "notes.md",
])
def test_universal_extensions_are_not_skipped(filename, mocker):
    """Files supported by all parsers (or handled by plaintext/direct_convert) are never skipped."""
    for service in ("DOCLING", "LLAMACLOUD", "UNSTRUCTURED"):
        mocker.patch("app.config.config.ETL_SERVICE", service)
        skip, ext = should_skip_by_extension(filename)
        assert skip is False, f"{filename} should NOT be skipped with {service}"
        assert ext is None


@pytest.mark.parametrize("filename,service,expected_skip", [
    ("macro.docm", "DOCLING", True),
    ("macro.docm", "LLAMACLOUD", False),
    ("mail.eml", "DOCLING", True),
    ("mail.eml", "UNSTRUCTURED", False),
    ("photo.gif", "DOCLING", True),
    ("photo.gif", "LLAMACLOUD", False),
    ("photo.heic", "UNSTRUCTURED", False),
    ("photo.heic", "DOCLING", True),
])
def test_parser_specific_extensions(filename, service, expected_skip, mocker):
    mocker.patch("app.config.config.ETL_SERVICE", service)
    skip, ext = should_skip_by_extension(filename)
    assert skip is expected_skip, (
        f"{filename} with {service}: expected skip={expected_skip}"
    )
    if expected_skip:
        assert ext is not None, "unsupported extension should be returned"
    else:
        assert ext is None


def test_returns_unsupported_extension(mocker):
    """When a file is skipped, the unsupported extension string is returned."""
    mocker.patch("app.config.config.ETL_SERVICE", "DOCLING")
    skip, ext = should_skip_by_extension("macro.docm")
    assert skip is True
    assert ext == ".docm"
