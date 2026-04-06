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
        assert should_skip_by_extension(filename) is True


@pytest.mark.parametrize("filename", [
    "report.pdf", "doc.docx", "sheet.xlsx", "slides.pptx",
    "readme.txt", "data.csv", "photo.png", "notes.md",
])
def test_universal_extensions_are_not_skipped(filename, mocker):
    """Files supported by all parsers (or handled by plaintext/direct_convert) are never skipped."""
    for service in ("DOCLING", "LLAMACLOUD", "UNSTRUCTURED"):
        mocker.patch("app.config.config.ETL_SERVICE", service)
        assert should_skip_by_extension(filename) is False, (
            f"{filename} should NOT be skipped with {service}"
        )


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
    assert should_skip_by_extension(filename) is expected_skip, (
        f"{filename} with {service}: expected skip={expected_skip}"
    )
