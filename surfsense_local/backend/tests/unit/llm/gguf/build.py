"""A minimal GGUF writer, so header tests need no checked-in binary.

Built from the format spec rather than from the reader under test, so the two
can disagree.
"""

import struct

UINT32, FLOAT32, BOOL, STRING, ARRAY, UINT64 = 4, 6, 7, 8, 9, 10


def _string(value: str) -> bytes:
    raw = value.encode()
    return struct.pack("<Q", len(raw)) + raw


def _value(kind: int, value: object) -> bytes:
    if kind == STRING:
        return _string(str(value))
    if kind == UINT32:
        return struct.pack("<I", int(value))  # type: ignore[arg-type]
    if kind == UINT64:
        return struct.pack("<Q", int(value))  # type: ignore[arg-type]
    if kind == FLOAT32:
        return struct.pack("<f", float(value))  # type: ignore[arg-type]
    if kind == BOOL:
        return struct.pack("<?", bool(value))
    raise ValueError(f"unsupported kind {kind}")


def kv(key: str, kind: int, value: object) -> bytes:
    """One scalar metadata entry."""
    return _string(key) + struct.pack("<I", kind) + _value(kind, value)


def array(key: str, elem_kind: int, values: list[object]) -> bytes:
    """One metadata entry holding a list, as vocabularies and per-layer fields are."""
    body = b"".join(_value(elem_kind, v) for v in values)
    return (
        _string(key)
        + struct.pack("<I", ARRAY)
        + struct.pack("<I", elem_kind)
        + struct.pack("<Q", len(values))
        + body
    )


def tensor(name: str, dims: list[int], dtype: int = 0, offset: int = 0) -> bytes:
    """One tensor-table row."""
    return (
        _string(name)
        + struct.pack("<I", len(dims))
        + b"".join(struct.pack("<Q", d) for d in dims)
        + struct.pack("<I", dtype)
        + struct.pack("<Q", offset)
    )


def gguf(entries: list[bytes], tensors: list[bytes] | None = None) -> bytes:
    """A whole file: magic, counts, metadata, then the tensor table."""
    tensors = tensors or []
    return (
        b"GGUF"
        + struct.pack("<I", 3)
        + struct.pack("<Q", len(tensors))
        + struct.pack("<Q", len(entries))
        + b"".join(entries)
        + b"".join(tensors)
    )
