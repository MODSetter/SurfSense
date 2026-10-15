"""Content checks for the formats exposed by the source picker."""

from pathlib import Path
from zipfile import ZipFile

import pytest

from modules.documents.storage import (
    SUPPORTED_UPLOAD_SUFFIXES,
    UPLOAD_MIME_BY_SUFFIX,
    validate_upload,
)

pytestmark = pytest.mark.unit


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
