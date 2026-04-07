"""Tests for OneDrive file type filtering."""

import pytest

from app.connectors.onedrive.file_types import should_skip_file

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Structural skips (independent of ETL service)
# ---------------------------------------------------------------------------


def test_folder_is_skipped():
    item = {"folder": {}, "name": "My Folder"}
    skip, ext = should_skip_file(item)
    assert skip is True
    assert ext is None


def test_remote_item_is_skipped():
    item = {"remoteItem": {}, "name": "shared.docx"}
    skip, ext = should_skip_file(item)
    assert skip is True
    assert ext is None


def test_package_is_skipped():
    item = {"package": {}, "name": "notebook"}
    skip, ext = should_skip_file(item)
    assert skip is True
    assert ext is None


def test_onenote_is_skipped():
    item = {"name": "notes", "file": {"mimeType": "application/msonenote"}}
    skip, ext = should_skip_file(item)
    assert skip is True
    assert ext is None


# ---------------------------------------------------------------------------
# Extension-based skips (require ETL service context)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "filename",
    [
        "malware.exe",
        "archive.zip",
        "video.mov",
        "font.woff2",
        "model.blend",
    ],
)
def test_unsupported_extensions_are_skipped(filename, mocker):
    mocker.patch("app.config.config.ETL_SERVICE", "DOCLING")
    item = {"name": filename, "file": {"mimeType": "application/octet-stream"}}
    skip, ext = should_skip_file(item)
    assert skip is True, f"{filename} should be skipped"
    assert ext is not None


@pytest.mark.parametrize(
    "filename",
    [
        "report.pdf",
        "doc.docx",
        "sheet.xlsx",
        "slides.pptx",
        "readme.txt",
        "data.csv",
        "photo.png",
        "notes.md",
    ],
)
def test_universal_files_are_not_skipped(filename, mocker):
    for service in ("DOCLING", "LLAMACLOUD", "UNSTRUCTURED"):
        mocker.patch("app.config.config.ETL_SERVICE", service)
        item = {"name": filename, "file": {"mimeType": "application/octet-stream"}}
        skip, ext = should_skip_file(item)
        assert skip is False, f"{filename} should NOT be skipped with {service}"
        assert ext is None


@pytest.mark.parametrize(
    "filename,service,expected_skip",
    [
        ("macro.docm", "DOCLING", True),
        ("macro.docm", "LLAMACLOUD", False),
        ("mail.eml", "DOCLING", True),
        ("mail.eml", "UNSTRUCTURED", False),
        ("photo.heic", "UNSTRUCTURED", False),
        ("photo.heic", "DOCLING", True),
    ],
)
def test_parser_specific_extensions(filename, service, expected_skip, mocker):
    mocker.patch("app.config.config.ETL_SERVICE", service)
    item = {"name": filename, "file": {"mimeType": "application/octet-stream"}}
    skip, ext = should_skip_file(item)
    assert skip is expected_skip, (
        f"{filename} with {service}: expected skip={expected_skip}"
    )
    if expected_skip:
        assert ext is not None
    else:
        assert ext is None


def test_returns_unsupported_extension(mocker):
    """When a file is skipped due to unsupported extension, the ext string is returned."""
    mocker.patch("app.config.config.ETL_SERVICE", "DOCLING")
    item = {"name": "mail.eml", "file": {"mimeType": "application/octet-stream"}}
    skip, ext = should_skip_file(item)
    assert skip is True
    assert ext == ".eml"
