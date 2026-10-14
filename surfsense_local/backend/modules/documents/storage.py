import hashlib
import re
from codecs import getincrementaldecoder
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import NamedTuple
from zipfile import BadZipFile, ZipFile

from fastapi import HTTPException, UploadFile, status

MAX_UPLOAD_BYTES = 500 * 1024 * 1024
MAX_ARCHIVE_ENTRIES = 10_000
MAX_ARCHIVE_UNPACKED_BYTES = 2 * 1024 * 1024 * 1024
READ_SIZE = 1024 * 1024

# The only part of a client's filename allowed near a path.
SAFE_SUFFIX = re.compile(r"\A\.[A-Za-z0-9]{1,16}\Z")

# This is the upload authority. The frontend mirrors these suffixes only to
# filter its native picker; update that mirror when this changes. If formats
# become dynamic or change often, expose them through a capabilities endpoint.
UPLOAD_MIME_BY_SUFFIX = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".html": "text/html",
    ".htm": "text/html",
    ".csv": "text/csv",
    ".md": "text/markdown",
    ".markdown": "text/markdown",
    ".txt": "text/plain",
    ".text": "text/plain",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".tif": "image/tiff",
    ".tiff": "image/tiff",
    ".bmp": "image/bmp",
    ".webp": "image/webp",
    # Recordings the worker's decoder reads; transcribed, never parsed.
    ".wav": "audio/wav",
    ".mp3": "audio/mpeg",
    ".flac": "audio/flac",
    ".ogg": "audio/ogg",
    ".oga": "audio/ogg",
}
SUPPORTED_UPLOAD_SUFFIXES = frozenset(UPLOAD_MIME_BY_SUFFIX)

_AUDIO_SUFFIXES = frozenset({".wav", ".mp3", ".flac", ".ogg", ".oga"})
# An Ogg file's first packet names its codec.
_VORBIS_HEADER = b"\x01vorbis"
_OPUS_HEADER = b"OpusHead"
OPUS_LATER = "Opus support comes in a later update"

_OOXML_MEMBER_BY_SUFFIX = {
    ".docx": "word/document.xml",
    ".pptx": "ppt/presentation.xml",
    ".xlsx": "xl/workbook.xml",
}


def validate_upload(path: Path, suffix: str) -> str:
    """Validate the stored bytes and return the server-owned MIME type."""
    if suffix == ".pdf":
        valid = _starts_with(path, b"%PDF-")
    elif suffix in _OOXML_MEMBER_BY_SUFFIX:
        valid = _is_ooxml(path, suffix)
    elif suffix in {".html", ".htm", ".csv", ".md", ".markdown", ".txt", ".text"}:
        valid = _is_utf8_text(path)
    elif suffix in {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp"}:
        valid = _is_image(path, suffix)
    elif suffix in _AUDIO_SUFFIXES:
        valid = _is_audio(path, suffix)
    else:
        raise ValueError(f"{suffix or 'extensionless files'} are not supported")

    if not valid:
        raise ValueError(f"file contents do not match {suffix}")
    return UPLOAD_MIME_BY_SUFFIX[suffix]


def _starts_with(path: Path, signature: bytes) -> bool:
    with path.open("rb") as source:
        return source.read(len(signature)) == signature


def _is_ooxml(path: Path, suffix: str) -> bool:
    try:
        with ZipFile(path) as archive:
            entries = archive.infolist()
            names = {entry.filename for entry in entries}
            return (
                len(entries) <= MAX_ARCHIVE_ENTRIES
                and sum(entry.file_size for entry in entries)
                <= MAX_ARCHIVE_UNPACKED_BYTES
                and "[Content_Types].xml" in names
                and _OOXML_MEMBER_BY_SUFFIX[suffix] in names
            )
    except (BadZipFile, OSError):
        return False


def _is_utf8_text(path: Path) -> bool:
    size = 0
    controls = 0
    decoder = getincrementaldecoder("utf-8")()
    try:
        with path.open("rb") as source:
            while chunk := source.read(READ_SIZE):
                decoder.decode(chunk)
                if b"\0" in chunk:
                    return False
                size += len(chunk)
                controls += sum(byte < 32 and byte not in b"\t\n\f\r" for byte in chunk)
        decoder.decode(b"", final=True)
    except (OSError, UnicodeDecodeError):
        return False
    return size > 0 and controls <= max(1, size // 100)


def _is_image(path: Path, suffix: str) -> bool:
    with path.open("rb") as source:
        header = source.read(12)
    if suffix == ".png":
        return header.startswith(b"\x89PNG\r\n\x1a\n")
    if suffix in {".jpg", ".jpeg"}:
        return header.startswith(b"\xff\xd8\xff")
    if suffix in {".tif", ".tiff"}:
        return header.startswith((b"II*\x00", b"MM\x00*"))
    if suffix == ".bmp":
        return header.startswith(b"BM")
    return header.startswith(b"RIFF") and header[8:12] == b"WEBP"


def _is_audio(path: Path, suffix: str) -> bool:
    """Raises for Ogg Opus, which the decoder cannot read yet, with the reason."""
    with path.open("rb") as source:
        header = source.read(512)
    if suffix == ".wav":
        return header.startswith(b"RIFF") and header[8:12] == b"WAVE"
    if suffix == ".mp3":
        return header.startswith(b"ID3") or _is_mpeg_audio_frame(header)
    if suffix == ".flac":
        return header.startswith(b"fLaC")
    packet = _first_ogg_packet(header)
    if packet.startswith(_OPUS_HEADER):
        raise ValueError(OPUS_LATER)
    return packet.startswith(_VORBIS_HEADER)


def _is_mpeg_audio_frame(header: bytes) -> bool:
    # Eleven sync bits, a known MPEG version and a layer: ADTS AAC's layer is 0.
    return (
        len(header) >= 2
        and header[0] == 0xFF
        and header[1] & 0xE0 == 0xE0
        and (header[1] >> 3) & 0b11 != 0b01
        and (header[1] >> 1) & 0b11 != 0b00
    )


def _first_ogg_packet(header: bytes) -> bytes:
    # A page is 27 bytes, then one length byte per segment, then the packet.
    if not header.startswith(b"OggS") or len(header) < 27:
        return b""
    return header[27 + header[26] :]


def title_of(upload: UploadFile) -> str:
    name = Path(upload.filename or "").name.strip()
    return name[:500] or "untitled"


def suffix_of(upload: UploadFile) -> str:
    suffix = Path(upload.filename or "").suffix.lower()
    return suffix if SAFE_SUFFIX.match(suffix) else ""


class StreamedUpload(NamedTuple):
    path: Path
    digest: str
    size: int


def stream_upload(upload: UploadFile, directory: Path) -> StreamedUpload:
    """Write the upload to a temporary file, hashing it on the way past.

    Lands in the directory it will be moved into, since a rename is only atomic
    within one filesystem.
    """
    directory.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256()
    written = 0

    path: Path | None = None
    try:
        with NamedTemporaryFile(dir=directory, delete=False) as temporary:
            path = Path(temporary.name)
            while chunk := upload.file.read(READ_SIZE):
                written += len(chunk)
                if written > MAX_UPLOAD_BYTES:
                    raise HTTPException(
                        status.HTTP_413_CONTENT_TOO_LARGE,
                        f"{title_of(upload)} is larger than "
                        f"{MAX_UPLOAD_BYTES // 1024 // 1024} MB",
                    )
                digest.update(chunk)
                temporary.write(chunk)
    except BaseException:
        # Removed once closed: Windows cannot delete a file that is still open.
        if path is not None:
            path.unlink(missing_ok=True)
        raise

    return StreamedUpload(path, digest.hexdigest(), written)
