"""The Palm database a MOBI or AZW3 book is stored in, and its record 0 headers."""

import struct
from dataclasses import dataclass, field
from itertools import pairwise

NO_RECORD = 0xFFFFFFFF
BOOK_TYPES = (b"BOOKMOBI", b"TEXtREAd")
PALM_HEADER_SIZE = 78
COMPRESSION_NONE, COMPRESSION_PALMDOC, COMPRESSION_HUFFCDIC = 1, 2, 17480
EXTH_KF8_BOUNDARY = 121
# A text record unpacks to 4 KB. Codes that keep copying, or dictionary entries
# that double at each level, could reach gigabytes; past this the file is damaged.
MAX_UNPACKED_RECORD = 64 * 1024


class KindleBookError(ValueError):
    """The bytes are not a book this reader can open."""


class DrmProtectedError(KindleBookError):
    pass


def u16(data: bytes, at: int) -> int:
    return struct.unpack_from(">H", data, at)[0]


def u32(data: bytes, at: int) -> int:
    return struct.unpack_from(">I", data, at)[0]


def record_offsets(head: bytes) -> list[int]:
    """Each record's start, from the database header and record table."""
    if len(head) < PALM_HEADER_SIZE or head[60:68] not in BOOK_TYPES:
        raise KindleBookError("not a Kindle book")
    count = u16(head, 76)
    if len(head) < PALM_HEADER_SIZE + 8 * count:
        raise KindleBookError("the book is cut short")
    offsets = [u32(head, PALM_HEADER_SIZE + 8 * i) for i in range(count)]
    if not offsets or any(a > b for a, b in pairwise(offsets)):
        raise KindleBookError("the book's record table is out of order")
    return offsets


def records(data: bytes) -> list[bytes]:
    offsets = record_offsets(data)
    if offsets[-1] > len(data):
        raise KindleBookError("the book is cut short")
    ends = [*offsets[1:], len(data)]
    return [data[start:end] for start, end in zip(offsets, ends, strict=True)]


@dataclass(frozen=True)
class BookHeader:
    compression: int
    text_records: int
    encryption: int
    encoding: str = "cp1252"
    version: int = 0
    trailing_flags: int = 0
    huff_record: int = NO_RECORD
    huff_count: int = 0
    frag_index: int = NO_RECORD
    skel_index: int = NO_RECORD
    exth: dict[int, bytes] = field(default_factory=dict)

    @property
    def kf8_boundary(self) -> int | None:
        """Where a combined file's KF8 part starts, if it has one."""
        value = self.exth.get(EXTH_KF8_BOUNDARY)
        if value is None or len(value) < 4 or u32(value, 0) == NO_RECORD:
            return None
        return u32(value, 0)


def has_mobi_header(record0: bytes) -> bool:
    return record0[16:20] == b"MOBI"


def book_header(record0: bytes) -> BookHeader:
    """Record 0: a PalmDOC header, then for a MOBI book its MOBI and EXTH headers."""
    if len(record0) < 16:
        raise KindleBookError("the book is cut short")
    compression, text_records = u16(record0, 0), u16(record0, 8)
    if not has_mobi_header(record0):
        # A plain PalmDOC text: bytes 12-13 are its encryption, as for MOBI.
        return BookHeader(compression, text_records, u16(record0, 12))
    length = u32(record0, 20)
    encoding = {1252: "cp1252", 65001: "utf-8"}.get(u32(record0, 28))
    if encoding is None:
        raise KindleBookError("the book's text encoding is unknown")
    version = u32(record0, 36)
    kf8 = version >= 8
    return BookHeader(
        compression=compression,
        text_records=text_records,
        encryption=u16(record0, 12),
        encoding=encoding,
        version=version,
        # The field exists only in a header at least this long.
        trailing_flags=u32(record0, 240) if length >= 0xE4 else 0,
        huff_record=u32(record0, 112),
        huff_count=u32(record0, 116),
        frag_index=u32(record0, 248) if kf8 else NO_RECORD,
        skel_index=u32(record0, 252) if kf8 else NO_RECORD,
        exth=_exth(record0, 16 + length) if u32(record0, 128) & 0x40 else {},
    )


def _exth(record0: bytes, at: int) -> dict[int, bytes]:
    if record0[at : at + 4] != b"EXTH":
        return {}
    entries: dict[int, bytes] = {}
    pos = at + 12
    for _ in range(u32(record0, at + 8)):
        kind, size = u32(record0, pos), u32(record0, pos + 4)
        if size < 8:
            break
        # The first wins: authors repeat, the boundary does not.
        entries.setdefault(kind, record0[pos + 8 : pos + size])
        pos += size
    return entries
