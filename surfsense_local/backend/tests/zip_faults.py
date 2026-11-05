"""Zips damaged the ways a tampered or hand-made pack can be, byte for byte: a member marked
encrypted, or one whose compressed bytes are corrupt."""

_LOCAL = b"PK\x03\x04"
_CENTRAL = b"PK\x01\x02"
# Offsets from each header's signature: its flags, its name's length, its name.
_FLAGS_AT = {_LOCAL: 6, _CENTRAL: 8}
_NAME_LENGTH_AT = {_LOCAL: 26, _CENTRAL: 28}
_NAME_AT = {_LOCAL: 30, _CENTRAL: 46}
_ENCRYPTED = 0x1


def encrypted(data: bytes, name: str) -> bytes:
    """`data` with member `name` marked encrypted in its local and central headers."""
    out = bytearray(data)
    for header in (_LOCAL, _CENTRAL):
        for start in _headers_of(out, header, name):
            at = start + _FLAGS_AT[header]
            flags = int.from_bytes(out[at : at + 2], "little") | _ENCRYPTED
            out[at : at + 2] = flags.to_bytes(2, "little")
    return bytes(out)


def corrupted(data: bytes, name: str) -> bytes:
    """`data` with the compressed bytes of member `name` overwritten."""
    out = bytearray(data)
    (start,) = _headers_of(out, _LOCAL, name)
    size = int.from_bytes(out[start + 18 : start + 22], "little")
    name_length = int.from_bytes(out[start + 26 : start + 28], "little")
    extra_length = int.from_bytes(out[start + 28 : start + 30], "little")
    begin = start + 30 + name_length + extra_length
    out[begin : begin + size] = b"\xff" * size
    return bytes(out)


def _headers_of(data: bytearray, header: bytes, name: str) -> list[int]:
    """Where each header of that kind naming `name` starts."""
    encoded = name.encode()
    found = []
    start = data.find(header)
    while start != -1:
        length_at = start + _NAME_LENGTH_AT[header]
        length = int.from_bytes(data[length_at : length_at + 2], "little")
        at = start + _NAME_AT[header]
        if length == len(encoded) and data[at : at + length] == encoded:
            found.append(start)
        start = data.find(header, start + 4)
    return found
