"""An Ogg Vorbis recording's length read off its own pages: the last page's
granule position over the rate its first packet names. stb_vorbis opens a path
with fopen, which on Windows fails for any name outside the ANSI code page."""

import os
import struct
from pathlib import Path

__all__ = ["vorbis_seconds"]

# OggS, version, flags, granule position, serial, sequence, CRC, segment count.
_PAGE = struct.Struct("<4sBBqIIIB")
# A page holds at most 255 segments of 255 bytes: its whole size bounds both
# reads.
_MAX_PAGE = _PAGE.size + 255 + 255 * 255
_VORBIS_ID = b"\x01vorbis"
# The identification packet's rate, after its type, name, version and channels.
_RATE_AT = 12
# No packet ends on such a page, so it has no position.
_NO_GRANULE = -1


def vorbis_seconds(source: Path) -> float:
    """Raises ValueError when no Vorbis stream can be measured in it."""
    with source.open("rb") as recording:
        head = recording.read(_MAX_PAGE)
        size = recording.seek(0, os.SEEK_END)
        recording.seek(max(0, size - 2 * _MAX_PAGE))
        tail = recording.read()
    serial, rate = _vorbis_stream(head)
    return _last_granule(tail, serial) / rate


def _vorbis_stream(head: bytes) -> tuple[int, int]:
    if len(head) < _PAGE.size or not head.startswith(b"OggS"):
        raise ValueError("not an Ogg file")
    *_, serial, _, _, segments = _PAGE.unpack_from(head)
    packet = head[_PAGE.size + segments :]
    if not packet.startswith(_VORBIS_ID) or len(packet) < _RATE_AT + 4:
        raise ValueError("not an Ogg Vorbis file")
    (rate,) = struct.unpack_from("<I", packet, _RATE_AT)
    if rate == 0:
        raise ValueError("an Ogg Vorbis file with no sample rate")
    return serial, rate


def _last_granule(tail: bytes, serial: int) -> int:
    """The last whole page of the stream that ends a packet."""
    at = tail.rfind(b"OggS")
    while at >= 0:
        if len(tail) - at >= _PAGE.size:
            _, version, _, granule, page_serial, _, _, segments = _PAGE.unpack_from(
                tail, at
            )
            table = tail[at + _PAGE.size : at + _PAGE.size + segments]
            whole = at + _PAGE.size + segments + sum(table) <= len(tail)
            if (
                version == 0
                and page_serial == serial
                and granule != _NO_GRANULE
                and len(table) == segments
                and whole
            ):
                return granule
        at = tail.rfind(b"OggS", 0, at)
    raise ValueError("an Ogg Vorbis file with no audio page")
