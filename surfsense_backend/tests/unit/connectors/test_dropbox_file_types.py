"""Tests for Dropbox file type filtering (should_skip_file)."""

import pytest

from app.connectors.dropbox.file_types import should_skip_file

pytestmark = pytest.mark.unit


def test_folder_item_is_skipped():
    item = {".tag": "folder", "name": "My Folder"}
    assert should_skip_file(item) is True


def test_paper_file_is_not_skipped():
    item = {".tag": "file", "name": "notes.paper", "is_downloadable": False}
    assert should_skip_file(item) is False


def test_non_downloadable_item_is_skipped():
    item = {".tag": "file", "name": "locked.gdoc", "is_downloadable": False}
    assert should_skip_file(item) is True


@pytest.mark.parametrize(
    "filename",
    [
        "archive.zip", "backup.tar", "data.gz", "stuff.rar", "pack.7z",
        "program.exe", "lib.dll", "module.so", "image.dmg", "disk.iso",
        "movie.mov", "clip.avi", "video.mkv", "film.wmv", "stream.flv",
        "icon.svg", "anim.gif", "photo.webp", "shot.heic", "favicon.ico",
        "raw.cr2", "photo.nef", "image.arw", "pic.dng",
        "design.psd", "vector.ai", "mockup.sketch", "proto.fig",
        "font.ttf", "font.otf", "font.woff", "font.woff2",
        "model.stl", "scene.fbx", "mesh.blend",
        "local.db", "data.sqlite", "access.mdb",
    ],
)
def test_non_parseable_extensions_are_skipped(filename):
    item = {".tag": "file", "name": filename}
    assert should_skip_file(item) is True, f"{filename} should be skipped"


@pytest.mark.parametrize(
    "filename",
    [
        "report.pdf", "document.docx", "sheet.xlsx", "slides.pptx",
        "old.doc", "legacy.xls", "deck.ppt",
        "readme.txt", "data.csv", "page.html", "notes.md",
        "config.json", "feed.xml",
    ],
)
def test_parseable_documents_are_not_skipped(filename):
    item = {".tag": "file", "name": filename}
    assert should_skip_file(item) is False, f"{filename} should NOT be skipped"


@pytest.mark.parametrize(
    "filename",
    ["photo.jpg", "image.jpeg", "screenshot.png", "scan.bmp", "page.tiff", "doc.tif"],
)
def test_universal_images_are_not_skipped(filename):
    item = {".tag": "file", "name": filename}
    assert should_skip_file(item) is False, f"{filename} should NOT be skipped"


@pytest.mark.parametrize(
    "filename",
    ["icon.svg", "anim.gif", "photo.webp", "live.heic"],
)
def test_non_universal_images_are_skipped(filename):
    item = {".tag": "file", "name": filename}
    assert should_skip_file(item) is True, f"{filename} should be skipped"
