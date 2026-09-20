"""Where header bytes come from: a file on disk, or the front of a remote file.

Hugging Face serves `Range` requests on model files, so a model can be priced
before a single weight is downloaded. That is what puts a real fit badge on a
search result.
"""

from pathlib import Path

import httpx

from modules.llm.fit import ModelShape
from modules.llm.gguf.reader import TruncatedHeaderError
from modules.llm.gguf.shape import read_header

# A 135M model's metadata ends at 1.77 MB, but Qwen3-Coder-30B-A3B's runs to
# 5.94 MB with 579 tensor entries after it. Header size scales with vocabulary,
# not with model size, so start wide and widen once more before giving up.
INITIAL_BYTES = 8 * 1024 * 1024
WIDENED_BYTES = 24 * 1024 * 1024


def shape_from_file(path: Path) -> ModelShape:
    with path.open("rb") as handle:
        return _read_widening(lambda n: _read_prefix(handle, n))


async def shape_from_url(client: httpx.AsyncClient, url: str) -> ModelShape:
    """Read only the header of a remote GGUF, over HTTP range requests."""

    async def fetch(size: int) -> bytes:
        reply = await client.get(url, headers={"Range": f"bytes=0-{size - 1}"})
        reply.raise_for_status()
        return reply.content

    data = await fetch(INITIAL_BYTES)
    try:
        return read_header(data)
    except TruncatedHeaderError:
        return read_header(await fetch(WIDENED_BYTES))


def _read_prefix(handle, size: int) -> bytes:
    handle.seek(0)
    return handle.read(size)


def _read_widening(fetch) -> ModelShape:
    try:
        return read_header(fetch(INITIAL_BYTES))
    except TruncatedHeaderError:
        return read_header(fetch(WIDENED_BYTES))
