"""Read a GGUF header from a byte prefix, never the weights.

llama.cpp's own parser is the one that gets hardened against malformed files,
and the search tier parses bytes from arbitrary repositories, so this wraps
`gguf.GGUFReader` rather than carrying a parser of our own. Two things stand in
the way, and this module is exactly the adapter around them:

- `GGUFReader` memory maps a **path**, so a prefix held in memory is written to
  a temporary file first.
- Its constructor always walks the tensor table and slices each tensor's data at
  an offset inside the weights, which a prefix does not have. numpy shortens a
  slice that runs past the end rather than raising, so the shortfall would
  surface later as a confident wrong answer instead of a retry.

Two private methods are therefore overridden: `_get` bounds checks every read,
and `_build_tensors` keeps names, dimensions and types without touching data.
Both are private upstream, which is why `gguf` is pinned to an exact version and
`test_header_prefix.py` asserts that version beside the two behaviours.
"""

import os
import tempfile
from dataclasses import dataclass
from typing import Any, Literal, NamedTuple

import numpy as np
import numpy.typing as npt
from gguf.gguf_reader import GGUFReader, ReaderField

# The pseudo fields the reader synthesises for the file's own counts. They are
# not model metadata and no caller looks them up by these names.
_SYNTHETIC_PREFIX = "GGUF."


class TruncatedHeaderError(ValueError):
    """The metadata block runs past the bytes we were given.

    A `ValueError`, because that is what it is: bytes that do not parse. Callers
    that can widen the read catch it by name and retry; callers that merely need
    to skip an unusable file catch `ValueError` and get both this and a file
    that was never a GGUF, which is the behaviour they want.

    Distinct from a malformed file: the caller's remedy is a wider read, not a
    rejection. Vocabulary lists make header size scale with vocabulary rather
    than with model size, so a budget that suits a 135M model fails on a 30B one.
    """


class HeaderTensor(NamedTuple):
    """One tensor-table row, without its weights.

    `ggml_type` is kept as the raw integer rather than the enum: an id this
    build of the package does not know is a tensor we cannot size, not a header
    we should refuse.
    """

    name: str
    dims: tuple[int, ...]
    ggml_type: int


@dataclass(frozen=True)
class GgufHeader:
    metadata: dict[str, Any]
    tensors: tuple[HeaderTensor, ...]


class HeaderPrefixReader(GGUFReader):
    """`GGUFReader` over bytes that stop before the weights."""

    header_tensors: tuple[HeaderTensor, ...]

    def _get(
        self,
        offset: int,
        dtype: npt.DTypeLike,
        count: int = 1,
        override_order: Literal["I", "S", "<"] | None = None,
    ):
        """Every read, bounds checked.

        The base class slices a memory map, and numpy answers a slice past the
        end with a shorter array rather than an error. Left alone, a prefix that
        stopped mid header would parse into a confident wrong shape.
        """
        itemsize = int(np.empty([], dtype=dtype).itemsize)
        start = int(offset)
        end = start + itemsize * int(count)
        if start < 0 or end > len(self.data):
            raise TruncatedHeaderError(
                f"header needs {end} bytes, the prefix holds {len(self.data)}"
            )
        return super()._get(offset, dtype, count, override_order)

    def _build_tensors(self, start_offs: int, fields: list[ReaderField]) -> None:
        """Names, dimensions and types. Never the data.

        The base class slices each tensor at its offset in the weights, which a
        prefix does not carry. Everything the estimator and the authoring script
        want lives in the table itself.
        """
        tensors: list[HeaderTensor] = []
        for field in fields:
            _name_len, name_data, _n_dims, dims, raw_dtype, _offset = field.parts
            tensors.append(
                HeaderTensor(
                    name=str(bytes(name_data), encoding="utf-8"),
                    dims=tuple(int(d) for d in dims.tolist()),
                    ggml_type=int(raw_dtype[0]),
                )
            )
        self.header_tensors = tuple(tensors)
        self.tensors = []

    def header(self) -> GgufHeader:
        """The parsed header, with the reader's own bookkeeping fields dropped."""
        metadata = {
            name: field.contents()
            for name, field in self.fields.items()
            if not name.startswith(_SYNTHETIC_PREFIX)
        }
        return GgufHeader(metadata=metadata, tensors=self.header_tensors)

    def close(self) -> None:
        """Release the memory map so the temporary file can be removed.

        Windows refuses to unlink a mapped file, and this runs once per searched
        model, so the map is closed explicitly rather than left to the collector.
        """
        mapping = getattr(self.data, "_mmap", None)
        if mapping is not None:
            mapping.close()


def read_header_prefix(prefix: bytes) -> GgufHeader:
    """Metadata and tensor table from the front of a GGUF file.

    Raises `TruncatedHeaderError` when the prefix stops inside the header, and
    `ValueError` when it was never a GGUF at all.
    """
    handle, name = tempfile.mkstemp(suffix=".gguf-header")
    try:
        with os.fdopen(handle, "wb") as file:
            file.write(prefix)
        reader = HeaderPrefixReader(name)
        try:
            return reader.header()
        finally:
            reader.close()
    finally:
        os.unlink(name)
