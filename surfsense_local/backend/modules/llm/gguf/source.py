"""Where header bytes come from: a file on disk, or the front of a remote file.

Hugging Face serves `Range` requests on model files, so a model can be priced
before a single weight is downloaded. That is what puts a real fit badge on a
search result.

The widening is the whole point of this module. Header size scales with
vocabulary rather than with model size, so no single prefix suits every model,
and a short read is a retry rather than a refusal.
"""

from pathlib import Path

import httpx

from modules.llm.fit import ModelShape
from modules.llm.gguf.header_prefix import (
    GgufHeader,
    TruncatedHeaderError,
    read_header_prefix,
)
from modules.llm.gguf.shape import to_shape

# A 135M model's metadata ends at 1.77 MB, but Qwen3-Coder-30B-A3B's runs to
# 5.94 MB with 579 tensor entries after it. Header size scales with vocabulary,
# not with model size, so start wide and widen once more before giving up.
INITIAL_BYTES = 8 * 1024 * 1024
WIDENED_BYTES = 24 * 1024 * 1024


def header_from_file(path: Path) -> GgufHeader:
    """The whole header, for callers that need the tensor table.

    The authoring script's expert accounting reads tensors, which the shape
    deliberately does not carry.
    """
    with path.open("rb") as handle:

        def fetch(size: int) -> bytes:
            handle.seek(0)
            return handle.read(size)

        return _widening(fetch)


def shape_from_file(path: Path) -> ModelShape:
    return to_shape(header_from_file(path))


async def header_from_url(client: httpx.AsyncClient, url: str) -> GgufHeader:
    """Read only the header of a remote GGUF, over HTTP range requests."""

    async def fetch(size: int) -> bytes:
        reply = await client.get(url, headers={"Range": f"bytes=0-{size - 1}"})
        reply.raise_for_status()
        return reply.content

    try:
        return read_header_prefix(await fetch(INITIAL_BYTES))
    except TruncatedHeaderError:
        return read_header_prefix(await fetch(WIDENED_BYTES))


async def shape_from_url(client: httpx.AsyncClient, url: str) -> ModelShape:
    return to_shape(await header_from_url(client, url))


def _widening(fetch) -> GgufHeader:
    try:
        return read_header_prefix(fetch(INITIAL_BYTES))
    except TruncatedHeaderError:
        return read_header_prefix(fetch(WIDENED_BYTES))
