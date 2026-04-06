"""Tests for OneDrive file type filtering."""

import pytest

from app.connectors.onedrive.file_types import should_skip_file

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Structural skips (independent of ETL service)
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Extension-based skips (require ETL service context)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("filename", [
    "malware.exe", "archive.zip", "video.mov", "font.woff2", "model.blend",
])
def test_unsupported_extensions_are_skipped(filename, mocker):
    mocker.patch("app.config.config.ETL_SERVICE", "DOCLING")
    item = {"name": filename, "file": {"mimeType": "application/octet-stream"}}
    assert should_skip_file(item) is True, f"{filename} should be skipped"


@pytest.mark.parametrize("filename", [
    "report.pdf", "doc.docx", "sheet.xlsx", "slides.pptx",
    "readme.txt", "data.csv", "photo.png", "notes.md",
])
def test_universal_files_are_not_skipped(filename, mocker):
    for service in ("DOCLING", "LLAMACLOUD", "UNSTRUCTURED"):
        mocker.patch("app.config.config.ETL_SERVICE", service)
        item = {"name": filename, "file": {"mimeType": "application/octet-stream"}}
        assert should_skip_file(item) is False, (
            f"{filename} should NOT be skipped with {service}"
        )


@pytest.mark.parametrize("filename,service,expected_skip", [
    ("macro.docm", "DOCLING", True),
    ("macro.docm", "LLAMACLOUD", False),
    ("mail.eml", "DOCLING", True),
    ("mail.eml", "UNSTRUCTURED", False),
    ("photo.heic", "UNSTRUCTURED", False),
    ("photo.heic", "DOCLING", True),
])
def test_parser_specific_extensions(filename, service, expected_skip, mocker):
    mocker.patch("app.config.config.ETL_SERVICE", service)
    item = {"name": filename, "file": {"mimeType": "application/octet-stream"}}
    assert should_skip_file(item) is expected_skip, (
        f"{filename} with {service}: expected skip={expected_skip}"
    )
