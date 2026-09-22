"""Reading a header without downloading the model it belongs to."""

import httpx
import pytest

from modules.llm.gguf import shape_from_file, shape_from_url
from modules.llm.gguf.source import INITIAL_BYTES, PROBE_BYTES
from tests.unit.llm.gguf.build import STRING, UINT32, array, gguf, kv

pytestmark = pytest.mark.unit


def a_gguf(vocab: int = 3) -> bytes:
    """A header whose size is driven by its vocabulary, as real ones are."""
    return gguf(
        [
            kv("general.architecture", STRING, "qwen3"),
            kv("qwen3.block_count", UINT32, 28),
            kv("qwen3.attention.head_count_kv", UINT32, 8),
            kv("qwen3.attention.key_length", UINT32, 128),
            kv("qwen3.attention.value_length", UINT32, 128),
            kv("qwen3.context_length", UINT32, 40960),
            array("tokenizer.ggml.tokens", STRING, [f"t{i}" for i in range(vocab)]),
        ]
    )


@pytest.mark.asyncio
async def test_only_the_front_of_the_file_is_requested() -> None:
    """The point of the whole exercise: price a 40 GB model without fetching it.

    The first ask is the probe rather than the pricing read. A file that is not
    a chat model answers there and costs a quarter of a megabyte, which is what
    makes reading the real file affordable on the refusal path. A chat model
    truncates and widens, so it pays exactly what it paid before.
    """
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.headers["Range"])
        return httpx.Response(206, content=a_gguf()[: INITIAL_BYTES])

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        shape = await shape_from_url(client, "https://example.invalid/m.gguf")

    assert seen == [f"bytes=0-{PROBE_BYTES - 1}"]
    assert shape.block_count == 28


@pytest.mark.asyncio
async def test_a_short_first_read_is_retried_wider_before_giving_up() -> None:
    """Header size scales with vocabulary, so one budget cannot suit every model."""
    whole = a_gguf(vocab=4000)
    sizes: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        start, end = request.headers["Range"].removeprefix("bytes=").split("-")
        size = int(end) - int(start) + 1
        sizes.append(size)
        # Starve the first read, satisfy the second.
        served = whole[: len(whole) // 3] if len(sizes) == 1 else whole
        return httpx.Response(206, content=served)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        shape = await shape_from_url(client, "https://example.invalid/m.gguf")

    assert len(sizes) == 2
    assert sizes[1] > sizes[0]
    assert shape.n_vocab == 4000


def test_a_local_file_reads_the_same_way(tmp_path) -> None:
    """An imported .gguf is the airgapped path, and it uses one code path."""
    path = tmp_path / "m.gguf"
    path.write_bytes(a_gguf())

    assert shape_from_file(path).architecture == "qwen3"
