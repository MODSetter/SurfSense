"""Tests for Dropbox file type filtering (should_skip_file)."""

import pytest

from app.connectors.dropbox.file_types import should_skip_file

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Structural skips (independent of ETL service)
# ---------------------------------------------------------------------------


def test_folder_item_is_skipped():
    item = {".tag": "folder", "name": "My Folder"}
    assert should_skip_file(item) is True


def test_paper_file_is_not_skipped():
    item = {".tag": "file", "name": "notes.paper", "is_downloadable": False}
    assert should_skip_file(item) is False


def test_non_downloadable_item_is_skipped():
    item = {".tag": "file", "name": "locked.gdoc", "is_downloadable": False}
    assert should_skip_file(item) is True


# ---------------------------------------------------------------------------
# Extension-based skips (require ETL service context)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "filename",
    [
        "archive.zip", "backup.tar", "data.gz", "stuff.rar", "pack.7z",
        "program.exe", "lib.dll", "module.so", "image.dmg", "disk.iso",
        "movie.mov", "clip.avi", "video.mkv", "film.wmv", "stream.flv",
        "favicon.ico",
        "raw.cr2", "photo.nef", "image.arw", "pic.dng",
        "design.psd", "vector.ai", "mockup.sketch", "proto.fig",
        "font.ttf", "font.otf", "font.woff", "font.woff2",
        "model.stl", "scene.fbx", "mesh.blend",
        "local.db", "data.sqlite", "access.mdb",
    ],
)
def test_non_parseable_extensions_are_skipped(filename, mocker):
    mocker.patch("app.config.config.ETL_SERVICE", "DOCLING")
    item = {".tag": "file", "name": filename}
    assert should_skip_file(item) is True, f"{filename} should be skipped"


@pytest.mark.parametrize(
    "filename",
    [
        "report.pdf", "document.docx", "sheet.xlsx", "slides.pptx",
        "readme.txt", "data.csv", "page.html", "notes.md",
        "config.json", "feed.xml",
    ],
)
def test_parseable_documents_are_not_skipped(filename, mocker):
    """Files in plaintext/direct_convert/universal document sets are never skipped."""
    for service in ("DOCLING", "LLAMACLOUD", "UNSTRUCTURED"):
        mocker.patch("app.config.config.ETL_SERVICE", service)
        item = {".tag": "file", "name": filename}
        assert should_skip_file(item) is False, (
            f"{filename} should NOT be skipped with {service}"
        )


@pytest.mark.parametrize(
    "filename",
    ["photo.jpg", "image.jpeg", "screenshot.png", "scan.bmp", "page.tiff", "doc.tif"],
)
def test_universal_images_are_not_skipped(filename, mocker):
    """Images supported by all parsers are never skipped."""
    for service in ("DOCLING", "LLAMACLOUD", "UNSTRUCTURED"):
        mocker.patch("app.config.config.ETL_SERVICE", service)
        item = {".tag": "file", "name": filename}
        assert should_skip_file(item) is False, (
            f"{filename} should NOT be skipped with {service}"
        )


@pytest.mark.parametrize("filename,service,expected_skip", [
    ("old.doc", "DOCLING", True),
    ("old.doc", "LLAMACLOUD", False),
    ("old.doc", "UNSTRUCTURED", False),
    ("legacy.xls", "DOCLING", True),
    ("legacy.xls", "LLAMACLOUD", False),
    ("legacy.xls", "UNSTRUCTURED", False),
    ("deck.ppt", "DOCLING", True),
    ("deck.ppt", "LLAMACLOUD", False),
    ("deck.ppt", "UNSTRUCTURED", False),
    ("icon.svg", "DOCLING", True),
    ("icon.svg", "LLAMACLOUD", False),
    ("anim.gif", "DOCLING", True),
    ("anim.gif", "LLAMACLOUD", False),
    ("photo.webp", "DOCLING", False),
    ("photo.webp", "LLAMACLOUD", False),
    ("photo.webp", "UNSTRUCTURED", True),
    ("live.heic", "DOCLING", True),
    ("live.heic", "UNSTRUCTURED", False),
    ("macro.docm", "DOCLING", True),
    ("macro.docm", "LLAMACLOUD", False),
    ("mail.eml", "DOCLING", True),
    ("mail.eml", "UNSTRUCTURED", False),
])
def test_parser_specific_extensions(filename, service, expected_skip, mocker):
    mocker.patch("app.config.config.ETL_SERVICE", service)
    item = {".tag": "file", "name": filename}
    assert should_skip_file(item) is expected_skip, (
        f"{filename} with {service}: expected skip={expected_skip}"
    )
