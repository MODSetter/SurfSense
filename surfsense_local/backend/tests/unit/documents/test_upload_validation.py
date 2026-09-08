"""Content checks for the formats exposed by the source picker."""

from pathlib import Path
from zipfile import ZipFile

import pytest

from modules.documents.storage import (
    SUPPORTED_UPLOAD_SUFFIXES,
    UPLOAD_MIME_BY_SUFFIX,
    validate_upload,
)


def test_the_public_allowlist_is_deliberately_small() -> None:
    """A dependency upgrade must not silently expose another Docling format."""
    assert {
        ".pdf",
        ".docx",
        ".pptx",
        ".xlsx",
        ".html",
        ".htm",
        ".csv",
        ".md",
        ".markdown",
        ".txt",
        ".text",
        ".png",
        ".jpg",
        ".jpeg",
        ".tif",
        ".tiff",
        ".bmp",
        ".webp",
    } == SUPPORTED_UPLOAD_SUFFIXES


@pytest.mark.parametrize(
    ("suffix", "header"),
    [
        (".png", b"\x89PNG\r\n\x1a\n"),
        (".jpg", b"\xff\xd8\xff"),
        (".jpeg", b"\xff\xd8\xff"),
        (".tif", b"II*\x00"),
        (".tiff", b"MM\x00*"),
        (".bmp", b"BM"),
        (".webp", b"RIFF\x04\x00\x00\x00WEBP"),
    ],
)
def test_selected_image_signatures_are_accepted(
    tmp_path: Path, suffix: str, header: bytes
) -> None:
    """Each image extension must agree with its bytes."""
    upload = tmp_path / f"image{suffix}"
    upload.write_bytes(header + b"content")

    assert validate_upload(upload, suffix) == UPLOAD_MIME_BY_SUFFIX[suffix]


@pytest.mark.parametrize("content", [b"text\0binary", b"\xff\xfe"])
def test_binary_content_cannot_enter_through_a_text_extension(
    tmp_path: Path, content: bytes
) -> None:
    """Text formats must be nonempty UTF-8 without binary NUL bytes."""
    upload = tmp_path / "notes.txt"
    upload.write_bytes(content)

    with pytest.raises(ValueError, match="file contents do not match"):
        validate_upload(upload, ".txt")


@pytest.mark.parametrize(
    ("suffix", "member"),
    [
        (".docx", "word/document.xml"),
        (".pptx", "ppt/presentation.xml"),
        (".xlsx", "xl/workbook.xml"),
    ],
)
def test_ooxml_container_must_match_its_extension(
    tmp_path: Path, suffix: str, member: str
) -> None:
    """A generic ZIP or renamed Office file is not enough."""
    upload = tmp_path / f"office{suffix}"
    with ZipFile(upload, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types />")
        archive.writestr(member, "<document />")

    assert validate_upload(upload, suffix) == UPLOAD_MIME_BY_SUFFIX[suffix]

    wrong_suffix = ".pptx" if suffix == ".docx" else ".docx"
    with pytest.raises(ValueError, match="file contents do not match"):
        validate_upload(upload, wrong_suffix)
