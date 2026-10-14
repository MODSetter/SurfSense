"""A streamed line holding U+2028, U+2029 or U+0085 stays one line, wherever reads cut it.

opencode and llama-server leave those raw inside a JSON string, as text pulled
from a Word file or a PDF can carry them.
"""

import json
from collections.abc import AsyncIterator
from itertools import pairwise

import httpx
import pytest

from modules.llm.model_route.client import RoutedGenerator
from modules.llm.providers.llamacpp.model_events import watch_models
from modules.llm.providers.openai_compatible.chat import OpenAICompatibleChatProvider
from modules.llm.providers.openai_responses.events import deltas
from modules.llm.providers.sse_lines import sse_lines
from modules.llm.providers.types import Delta, Message

pytestmark = pytest.mark.unit

SEPARATED = "line one\u2028line two\u2029para\x85next"


def _cut(text: str, *at: int) -> list[bytes]:
    """`text`'s bytes as reads would cut them, `at` byte offsets."""
    data = text.encode()
    edges = [0, *at, len(data)]
    return [data[a:b] for a, b in pairwise(edges)]


def _cut_inside_separators(text: str) -> list[bytes]:
    """Cut in the middle of each separator's bytes, and once more after it."""
    data = text.encode()
    at = []
    for separator in ("\u2028", "\u2029", "\x85"):
        start = data.index(separator.encode())
        at += [start + 1, start + len(separator.encode())]
    return _cut(text, *sorted(at))


def _streaming(chunks: list[bytes]) -> httpx.MockTransport:
    async def body() -> AsyncIterator[bytes]:
        for chunk in chunks:
            yield chunk

    return httpx.MockTransport(lambda _: httpx.Response(200, content=body()))


async def _lines(chunks: list[bytes]) -> list[str]:
    async with (
        httpx.AsyncClient(transport=_streaming(chunks)) as client,
        client.stream("GET", "http://upstream/") as reply,
    ):
        return [line async for line in sse_lines(reply)]


async def test_only_a_line_feed_ends_a_line() -> None:
    """The separators stay inside their line, even cut through their bytes."""
    stream = f"data: {SEPARATED}\n\ndata: [DONE]\n\n"

    assert await _lines(_cut_inside_separators(stream)) == [
        f"data: {SEPARATED}",
        "",
        "data: [DONE]",
        "",
    ]


async def test_a_carriage_return_split_from_its_line_feed_is_still_one_ending() -> None:
    """CRLF, cut between the two bytes."""
    stream = "data: a\r\n\r\ndata: b\r\n"

    assert await _lines(_cut(stream, 8, 10)) == ["data: a", "", "data: b"]


async def test_the_last_line_counts_without_a_line_feed() -> None:
    """A stream may stop without ending its last line."""
    assert await _lines(_cut("data: a\ndata: b", 9)) == ["data: a", "data: b"]


async def test_a_chat_reply_keeps_its_separators() -> None:
    """A local or remote model's delta reaches the chat whole."""
    chunk = {"choices": [{"delta": {"content": SEPARATED}}]}
    stream = f"data: {json.dumps(chunk, ensure_ascii=False)}\n\ndata: [DONE]\n\n"
    model = OpenAICompatibleChatProvider(
        "http://remote/v1", transport=_streaming(_cut_inside_separators(stream))
    )

    replies = [d async for d in model.chat_deltas("m", [Message("user", "hi")])]

    assert replies == [Delta(SEPARATED)]


async def test_a_responses_reply_keeps_its_separators() -> None:
    """An OpenAI or ChatGPT plan reply's text delta reaches the chat whole."""
    events = [
        {"type": "response.output_text.delta", "delta": SEPARATED},
        {"type": "response.completed", "response": {"status": "completed"}},
    ]
    stream = "".join(
        f"event: {e['type']}\ndata: {json.dumps(e, ensure_ascii=False)}\n\n"
        for e in events
    )

    async with (
        httpx.AsyncClient(transport=_streaming(_cut_inside_separators(stream))) as c,
        c.stream("POST", "http://upstream/responses") as reply,
    ):
        replies = [delta async for delta in deltas(reply)]

    assert replies == [Delta(SEPARATED)]


async def test_a_load_stage_keeps_its_separators() -> None:
    """The router's load report is read whole."""
    frame = {
        "model": "Qwen3-1.7B-Q4_K_M",
        "data": {
            "status": "loading",
            "progress": {"current": SEPARATED, "value": 0.5},
        },
    }
    stream = f"data: {json.dumps(frame, ensure_ascii=False)}\n\n"

    (progress,) = [
        p
        async for p in watch_models(
            "http://router", transport=_streaming(_cut_inside_separators(stream))
        )
    ]

    assert progress.stage == SEPARATED


async def test_a_routed_reply_keeps_its_separators() -> None:
    """A worker reads the API's reply whole."""
    frame = {"type": "text", "text": SEPARATED}
    stream = f"data: {json.dumps(frame, ensure_ascii=False)}\n\ndata: [DONE]\n\n"
    routed = RoutedGenerator(
        "http://127.0.0.1:1",
        None,
        transport=_streaming(_cut_inside_separators(stream)),
    )

    replies = [text async for text in routed.chat("m", [Message("user", "hi")])]

    assert replies == [SEPARATED]
