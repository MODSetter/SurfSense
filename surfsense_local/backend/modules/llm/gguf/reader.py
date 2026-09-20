"""Parse a GGUF metadata block. Standard library only.

The header is the only thing a fit estimate needs, and it sits at the front of
the file, so it can be read over an HTTP range without downloading weights.
"""

import struct
from dataclasses import dataclass
from typing import Any

MAGIC = b"GGUF"

_UINT8, _INT8, _UINT16, _INT16, _UINT32, _INT32 = 0, 1, 2, 3, 4, 5
_FLOAT32, _BOOL, _STRING, _ARRAY, _UINT64, _INT64, _FLOAT64 = 6, 7, 8, 9, 10, 11, 12

_SCALARS: dict[int, tuple[str, int]] = {
    _UINT8: ("<B", 1),
    _INT8: ("<b", 1),
    _UINT16: ("<H", 2),
    _INT16: ("<h", 2),
    _UINT32: ("<I", 4),
    _INT32: ("<i", 4),
    _FLOAT32: ("<f", 4),
    _BOOL: ("<?", 1),
    _UINT64: ("<Q", 8),
    _INT64: ("<q", 8),
    _FLOAT64: ("<d", 8),
}


class TruncatedHeaderError(ValueError):
    """The metadata block runs past the bytes we were given.

    A `ValueError`, because that is what it is: bytes that do not parse. Callers
    that can widen the read catch it by name and retry; callers that merely need
    to skip an unusable file catch `ValueError` and get both this and a file
    that was never a GGUF, which is the behaviour they want.

    Distinct from a malformed file: the caller's remedy is a wider read, not a
    rejection. Vocabulary lists make header size scale with vocab rather than
    with model size, so a budget that suits a 135M model fails on a 30B one.
    """


@dataclass(frozen=True)
class GgufHeader:
    metadata: dict[str, Any]
    tensors: tuple[tuple[str, tuple[int, ...]], ...]


class _Cursor:
    def __init__(self, data: bytes) -> None:
        self._data = data
        self._at = 0

    def take(self, n: int) -> bytes:
        end = self._at + n
        if end > len(self._data):
            raise TruncatedHeaderError(
                f"header needs {end} bytes, got {len(self._data)}"
            )
        chunk = self._data[self._at : end]
        self._at = end
        return chunk

    def scalar(self, kind: int) -> Any:
        fmt, size = _SCALARS[kind]
        return struct.unpack(fmt, self.take(size))[0]

    def string(self) -> str:
        return self.take(self.scalar(_UINT64)).decode("utf-8", errors="replace")

    def value(self, kind: int) -> Any:
        if kind == _STRING:
            return self.string()
        if kind == _ARRAY:
            elem = self.scalar(_UINT32)
            count = self.scalar(_UINT64)
            return [self.value(elem) for _ in range(count)]
        if kind in _SCALARS:
            return self.scalar(kind)
        raise ValueError(f"unknown GGUF value type {kind}")


def read_gguf_header(data: bytes) -> GgufHeader:
    """Metadata and tensor table, or TruncatedHeaderError if `data` is short."""
    cursor = _Cursor(data)
    if cursor.take(4) != MAGIC:
        raise ValueError("not a GGUF file")
    cursor.scalar(_UINT32)  # format version
    tensor_count = cursor.scalar(_UINT64)
    kv_count = cursor.scalar(_UINT64)

    metadata: dict[str, Any] = {}
    for _ in range(kv_count):
        key = cursor.string()
        metadata[key] = cursor.value(cursor.scalar(_UINT32))

    tensors: list[tuple[str, tuple[int, ...]]] = []
    for _ in range(tensor_count):
        name = cursor.string()
        dims = tuple(cursor.scalar(_UINT64) for _ in range(cursor.scalar(_UINT32)))
        cursor.scalar(_UINT32)  # element type
        cursor.scalar(_UINT64)  # offset
        tensors.append((name, dims))

    return GgufHeader(metadata=metadata, tensors=tuple(tensors))
