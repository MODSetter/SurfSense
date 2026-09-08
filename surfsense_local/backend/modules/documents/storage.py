import hashlib
import re
from codecs import getincrementaldecoder
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import NamedTuple
from zipfile import BadZipFile, ZipFile

from fastapi import HTTPException, UploadFile, status

from modules.documents.models import Document
from shared.config import get_storage_settings

MAX_UPLOAD_BYTES = 500 * 1024 * 1024
MAX_ARCHIVE_ENTRIES = 10_000
MAX_ARCHIVE_UNPACKED_BYTES = 2 * 1024 * 1024 * 1024
READ_SIZE = 1024 * 1024

# The only part of a client's filename allowed near a path.
SAFE_SUFFIX = re.compile(r"\A\.[A-Za-z0-9]{1,16}\Z")

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
}
SUPPORTED_UPLOAD_SUFFIXES = frozenset(UPLOAD_MIME_BY_SUFFIX)

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


def original_path(document: Document) -> Path:
    """Where the upload was stored."""
    suffix = (document.document_metadata or {}).get("suffix", "")
    directory = get_storage_settings().document_dir(document.workspace_id, document.id)
    return directory / f"original{suffix}"


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

    with NamedTemporaryFile(dir=directory, delete=False) as temporary:
        path = Path(temporary.name)
        try:
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
            path.unlink(missing_ok=True)
            raise

    return StreamedUpload(path, digest.hexdigest(), written)
