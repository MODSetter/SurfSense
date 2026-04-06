"""Tests for OneDrive file type filtering."""

import pytest

from app.connectors.onedrive.file_types import should_skip_file

pytestmark = pytest.mark.unit


def test_folder_is_skipped():
    item = {"folder": {}, "name": "My Folder"}
    assert should_skip_file(item) is True


def test_remote_item_is_skipped():
    item = {"remoteItem": {}, "name": "shared.docx"}
    assert should_skip_file(item) is True


def test_package_is_skipped():
    item = {"package": {}, "name": "notebook"}
    assert should_skip_file(item) is True


def test_onenote_is_skipped():
    item = {"name": "notes", "file": {"mimeType": "application/msonenote"}}
    assert should_skip_file(item) is True


@pytest.mark.parametrize("filename", [
    "malware.exe", "archive.zip", "video.mov", "font.woff2", "model.blend",
])
def test_unsupported_extensions_are_skipped(filename):
    item = {"name": filename, "file": {"mimeType": "application/octet-stream"}}
    assert should_skip_file(item) is True, f"{filename} should be skipped"


@pytest.mark.parametrize("filename", [
    "report.pdf", "doc.docx", "sheet.xlsx", "slides.pptx",
    "readme.txt", "data.csv", "photo.png", "notes.md",
])
def test_parseable_files_are_not_skipped(filename):
    item = {"name": filename, "file": {"mimeType": "application/octet-stream"}}
    assert should_skip_file(item) is False, f"{filename} should NOT be skipped"
