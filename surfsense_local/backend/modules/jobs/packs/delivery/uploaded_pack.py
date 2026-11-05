"""A pack file the user imports by hand, kept in the packs folder only within the size a pack may
have.

Starlette spools the upload to the OS's temporary folder before the route runs, and the screen
refuses a larger file before sending it; a route reading the raw body would bound it sooner.
"""

from __future__ import annotations

from contextlib import suppress
from pathlib import Path
from tempfile import NamedTemporaryFile

from fastapi import UploadFile

from modules.jobs.packs.integrity import MAX_PACK_BYTES
from modules.jobs.packs.manifest import PackRefusedError

CHUNK_BYTES = 1024 * 1024


def received_pack(upload: UploadFile, folder: Path) -> Path:
    """The upload as a scratch file in `folder`, which the caller removes; past the cap,
    PACK_TOO_LARGE and no file."""
    folder.mkdir(parents=True, exist_ok=True)
    path: Path | None = None
    try:
        with NamedTemporaryFile(
            dir=folder, prefix=".upload-", suffix=".zip", delete=False
        ) as file:
            path = Path(file.name)
            written = 0
            while chunk := upload.file.read(CHUNK_BYTES):
                written += len(chunk)
                if written > MAX_PACK_BYTES:
                    raise PackRefusedError(
                        "PACK_TOO_LARGE", "The pack is larger than 50 MB."
                    )
                file.write(chunk)
    except BaseException:
        # Closed first: Windows cannot remove a file still open.
        if path is not None:
            with suppress(OSError):
                path.unlink(missing_ok=True)
        raise
    return path
