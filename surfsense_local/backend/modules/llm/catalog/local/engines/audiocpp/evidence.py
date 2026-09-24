"""An audio.cpp GGUF's family, read from the front of its header.

audio.cpp writes its family before the files it embeds: Kokoro's voice packs
make the header 38.6 MB and Supertonic's 57 MB, past what the shared reader
widens to, while the family sits in the first 400 bytes. So this walks the keys
in order and stops there.
"""

import struct

from modules.llm.gguf import TruncatedHeaderError

_ARCHITECTURE = "general.architecture"
_FAMILY = "audiocpp.model_spec.family"
_STRING, _ARRAY = 8, 9
# GGUF's fixed-width value types and their sizes in bytes.
_WIDTH = {0: 1, 1: 1, 2: 2, 3: 2, 4: 4, 5: 4, 6: 4, 7: 1, 10: 8, 11: 8, 12: 8}


class _Cursor:
    def __init__(self, data: bytes) -> None:
        self._data = data
        self._at = 24  # magic, version, tensor count, key count

    def take(self, size: int) -> bytes:
        end = self._at + size
        if end > len(self._data):
            raise TruncatedHeaderError(
                f"the family needs {end} bytes, the prefix holds {len(self._data)}"
            )
        chunk = self._data[self._at : end]
        self._at = end
        return chunk

    def number(self, fmt: str) -> int:
        return struct.unpack(fmt, self.take(struct.calcsize(fmt)))[0]

    def string(self) -> str:
        return self.take(self.number("<Q")).decode()

    def skip(self, kind: int) -> None:
        if kind == _STRING:
            self.string()
        elif kind == _ARRAY:
            element, count = self.number("<I"), self.number("<Q")
            if element in _WIDTH:
                self.take(_WIDTH[element] * count)
            else:
                for _ in range(count):
                    self.skip(element)
        elif kind in _WIDTH:
            self.take(_WIDTH[kind])
        else:
            raise ValueError(f"not a GGUF value type: {kind}")


def audio_family(prefix: bytes) -> str | None:
    """The family audio.cpp dispatches on, or None for another engine's file."""
    cursor = _Cursor(prefix)
    while True:
        key = cursor.string()
        kind = cursor.number("<I")
        if kind != _STRING:
            cursor.skip(kind)
            continue
        value = cursor.string()
        if key == _ARCHITECTURE and value != "audiocpp":
            return None
        if key == _FAMILY:
            return value
