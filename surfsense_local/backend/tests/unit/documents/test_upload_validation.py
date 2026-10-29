"""Content checks for the formats exposed by the source picker."""

from pathlib import Path
from zipfile import ZipFile

import pytest

from modules.documents.storage import (
    MAX_ARCHIVE_ENTRIES,
    SUPPORTED_UPLOAD_SUFFIXES,
    UPLOAD_MIME_BY_SUFFIX,
    validate_upload,
)
from tests import kindle_samples

pytestmark = pytest.mark.unit


def test_the_public_allowlist_is_deliberately_small() -> None:
    """A dependency upgrade must not silently expose another Docling format."""
    assert {
        ".pdf",
        ".docx",
        ".pptx",
        ".xlsx",
        ".epub",
        ".mobi",
        ".azw3",
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
        ".wav",
        ".mp3",
        ".flac",
        ".ogg",
        ".oga",
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


def _epub(
    path: Path, *, mimetype: str = "application/epub+zip", extra: int = 0
) -> Path:
    with ZipFile(path, "w") as archive:
        archive.writestr("mimetype", mimetype)
        archive.writestr("META-INF/container.xml", "<container />")
        for index in range(extra):
            archive.writestr(f"OEBPS/{index}.xhtml", "")
    return path


def test_an_epub_names_its_media_type_first(tmp_path: Path) -> None:
    """The EPUB spec's mimetype entry tells a book from any other ZIP."""
    book = _epub(tmp_path / "book.epub")
    assert validate_upload(book, ".epub") == "application/epub+zip"

    renamed = _epub(tmp_path / "renamed.epub", mimetype="application/zip")
    with pytest.raises(ValueError, match="file contents do not match"):
        validate_upload(renamed, ".epub")

    word = tmp_path / "word.epub"
    with ZipFile(word, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types />")
        archive.writestr("word/document.xml", "<document />")
    with pytest.raises(ValueError, match="file contents do not match"):
        validate_upload(word, ".epub")


def test_an_epub_keeps_the_archive_limits(tmp_path: Path) -> None:
    """A book is a ZIP, so it gets the same guard against a ZIP bomb as Office files."""
    book = _epub(tmp_path / "bomb.epub", extra=MAX_ARCHIVE_ENTRIES)

    with pytest.raises(ValueError, match="file contents do not match"):
        validate_upload(book, ".epub")


@pytest.mark.parametrize(
    ("suffix", "mime"),
    [
        (".mobi", "application/x-mobipocket-ebook"),
        (".azw3", "application/vnd.amazon.mobi8-ebook"),
    ],
)
def test_a_kindle_book_is_accepted_by_its_header(
    tmp_path: Path, suffix: str, mime: str
) -> None:
    """Either name holds the same container; the reader picks the part inside."""
    book = tmp_path / f"book{suffix}"
    book.write_bytes(kindle_samples.mobi("<p>Call me Ishmael.</p>"))

    assert validate_upload(book, suffix) == mime


def test_a_kindle_book_with_drm_is_refused_on_upload(tmp_path: Path) -> None:
    """Most Kindle Store books are locked; say so at once, not after a failed ingest."""
    book = tmp_path / "bought.azw3"
    book.write_bytes(kindle_samples.mobi("<p>Locked.</p>", encryption=2))

    with pytest.raises(ValueError, match="DRM"):
        validate_upload(book, ".azw3")


@pytest.mark.parametrize(
    ("content", "reason"),
    [
        # Amazon's newer KFX books, often saved under an .azw3 name.
        (b"\xeaDRMION\xee" + bytes(200), "KFX"),
        (b"CONT\x02\x00" + bytes(200), "KFX"),
        (b"PK\x03\x04" + bytes(200), "file contents do not match"),
    ],
    ids=["kfx-with-drm", "kfx", "zip"],
)
def test_what_is_not_a_kindle_book_is_refused(
    tmp_path: Path, content: bytes, reason: str
) -> None:
    """KFX gets its own reason; anything else is not the book it is named."""
    book = tmp_path / "book.azw3"
    book.write_bytes(content)

    with pytest.raises(ValueError, match=reason):
        validate_upload(book, ".azw3")


# Made with ffmpeg from a 440 Hz tone, stereo at 44.1 kHz, under a second long.
AUDIO = Path(__file__).resolve().parents[2] / "fixtures" / "audio"


def _wav_header() -> bytes:
    return b"RIFF\x24\x00\x00\x00WAVEfmt "


@pytest.mark.parametrize(
    ("suffix", "fixture", "mime"),
    [
        (".mp3", "tone.mp3", "audio/mpeg"),
        (".flac", "tone.flac", "audio/flac"),
        (".ogg", "tone.ogg", "audio/ogg"),
        (".oga", "tone.ogg", "audio/ogg"),
    ],
)
def test_recordings_are_accepted_by_their_bytes(
    tmp_path: Path, suffix: str, fixture: str, mime: str
) -> None:
    """MP3, FLAC and Ogg Vorbis, as the decoder reads them."""
    upload = tmp_path / f"meeting{suffix}"
    upload.write_bytes((AUDIO / fixture).read_bytes())

    assert validate_upload(upload, suffix) == mime


def test_a_wave_file_is_a_recording(tmp_path: Path) -> None:
    """RIFF with a WAVE form, not a WebP's."""
    upload = tmp_path / "memo.wav"
    upload.write_bytes(_wav_header() + b"\x00" * 64)

    assert validate_upload(upload, ".wav") == "audio/wav"


def test_an_mp3_without_a_tag_starts_with_a_frame(tmp_path: Path) -> None:
    """Not every encoder writes ID3; an MPEG audio frame header is enough."""
    upload = tmp_path / "bare.mp3"
    upload.write_bytes(b"\xff\xfb\x90\x64" + b"\x00" * 64)

    assert validate_upload(upload, ".mp3") == "audio/mpeg"


@pytest.mark.parametrize(
    ("suffix", "content"),
    [
        (".wav", b"RIFF\x04\x00\x00\x00WEBPVP8 "),
        (".mp3", b"%PDF-1.7"),
        # AAC in ADTS shares the sync word, and the decoder cannot read it.
        (".mp3", b"\xff\xf1\x50\x80" + b"\x00" * 16),
        (".flac", b"ID3\x04" + b"\x00" * 16),
        (".ogg", b"OggS" + b"\x00" * 64),
    ],
)
def test_bytes_that_are_not_the_recording_named_are_refused(
    tmp_path: Path, suffix: str, content: bytes
) -> None:
    """A renamed file never reaches the decoder."""
    upload = tmp_path / f"renamed{suffix}"
    upload.write_bytes(content)

    with pytest.raises(ValueError, match="file contents do not match"):
        validate_upload(upload, suffix)


@pytest.mark.parametrize("suffix", [".ogg", ".oga"])
def test_ogg_opus_is_refused_until_its_decoder_ships(
    tmp_path: Path, suffix: str
) -> None:
    """The decoder reads Vorbis only; the person learns why, file by file."""
    upload = tmp_path / f"voice-note{suffix}"
    upload.write_bytes((AUDIO / "tone-opus.ogg").read_bytes())

    with pytest.raises(ValueError, match=r"^Opus support comes in a later update$"):
        validate_upload(upload, suffix)
