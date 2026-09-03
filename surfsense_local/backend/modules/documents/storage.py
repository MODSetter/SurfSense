import hashlib
import re
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import NamedTuple

from fastapi import HTTPException, UploadFile, status

MAX_UPLOAD_BYTES = 500 * 1024 * 1024
READ_SIZE = 1024 * 1024

# The only part of a client's filename allowed near a path.
SAFE_SUFFIX = re.compile(r"\A\.[A-Za-z0-9]{1,16}\Z")


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
