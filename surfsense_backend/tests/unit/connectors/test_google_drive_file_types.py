"""Tests for Google Drive file type filtering."""

import pytest

from app.connectors.google_drive.file_types import should_skip_by_extension

pytestmark = pytest.mark.unit


@pytest.mark.parametrize("filename", [
    "malware.exe", "archive.zip", "video.mov", "font.woff2", "model.blend",
])
def test_unsupported_extensions_are_skipped(filename):
    assert should_skip_by_extension(filename) is True


@pytest.mark.parametrize("filename", [
    "report.pdf", "doc.docx", "sheet.xlsx", "slides.pptx",
    "readme.txt", "data.csv", "photo.png", "notes.md",
])
def test_parseable_extensions_are_not_skipped(filename):
    assert should_skip_by_extension(filename) is False
