"""Whether an upload is a Kindle book the reader can open, from its first bytes."""

import struct
from pathlib import Path

from modules.documents.kindle_books.container import (
    PALM_HEADER_SIZE,
    KindleBookError,
    book_header,
    record_offsets,
    u16,
)

KINDLE_SUFFIXES = frozenset({".mobi", ".azw3"})
DRM_REFUSAL = "This book is DRM-protected, so it can't be read"
KFX_REFUSAL = "KFX books from the Kindle store can't be read yet"
# Amazon's KFX: a DRM envelope, or the bare container.
_KFX_MAGIC = (b"\xeaDRMION\xee", b"CONT")
# Record 0 holds the headers; anything past this is not needed to judge the book.
_RECORD0_READ = 64 * 1024


def is_kindle_book(path: Path) -> bool:
    """True for a readable book; raises with the user's reason for DRM and KFX."""
    try:
        with path.open("rb") as book:
            head = book.read(PALM_HEADER_SIZE)
            if head.startswith(_KFX_MAGIC):
                raise ValueError(KFX_REFUSAL)
            if len(head) < PALM_HEADER_SIZE:
                return False
            head += book.read(8 * u16(head, 76))
            offsets = record_offsets(head)
            book.seek(offsets[0])
            record0 = book.read(_RECORD0_READ)
    except (OSError, KindleBookError, struct.error):
        return False
    try:
        header = book_header(record0)
    except (KindleBookError, struct.error):
        return False
    if header.encryption:
        raise ValueError(DRM_REFUSAL)
    return True
