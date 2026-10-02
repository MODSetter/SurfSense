"""How far the model has read the prompt reaches the caller before the answer.

Measured against b11050 in router mode: with `return_progress` a streamed chat
sends chunks carrying `prompt_progress` (`total`, `cache`, `processed`,
`time_ms`) once per 2,048-token batch, before the first token. `processed`
starts at `cache`, so the work left is what lies past the cache.
"""

import asyncio
import json
from collections.abc import AsyncIterator

import httpx
import pytest

from modules.llm.providers.llamacpp import LlamaCppProvider
from modules.llm.providers.openai_compatible import chat as openai_chat
from modules.llm.providers.openai_compatible.chat import OpenAICompatibleChatProvider
from modules.llm.providers.types import Delta, Message, PromptProgress
from tests.unit.llm.providers.llamacpp.fake_router import FakeRouter

pytestmark = pytest.mark.unit

ASKS = {"return_progress": True}


def _progress(total: int, cache: int, processed: int) -> str:
    return (
        'data: {"choices":[{"delta":{"role":"assistant","content":null}}],'
        f'"prompt_progress":{{"total":{total},"cache":{cache},'
        f'"processed":{processed},"time_ms":0}}}}\n\n'
    )


def _provider(body: str) -> OpenAICompatibleChatProvider:
    return OpenAICompatibleChatProvider(
        "http://local/v1",
        transport=httpx.MockTransport(lambda _: httpx.Response(200, text=body)),
        prompt_progress=ASKS,
    )


async def test_progress_streams_before_the_answer_as_the_work_past_the_cache() -> None:
    """A cached prefix is already read, so it is neither work done nor work left."""
    body = (
        _progress(12505, 505, 505)
        + _progress(12505, 505, 2553)
        + _progress(12505, 505, 12505)
        + 'data: {"choices":[{"delta":{"content":"Hi"}}]}\n\ndata: [DONE]\n\n'
    )

    deltas = [d async for d in _provider(body).chat_deltas("m", [Message("user", "hi")])]

    assert deltas == [
        Delta("", progress=PromptProgress(0, 12000)),
        Delta("", progress=PromptProgress(2048, 12000)),
        Delta("", progress=PromptProgress(12000, 12000)),
        Delta("Hi"),
    ]


async def test_callers_that_only_want_the_answer_never_see_progress() -> None:
    """Titles, Studio and the connection check read `chat()` as the reply."""
    body = (
        _progress(4096, 0, 2048)
        + 'data: {"choices":[{"delta":{"content":"Hi"}}]}\n\ndata: [DONE]\n\n'
    )

    chunks = [c async for c in _provider(body).chat("m", [Message("user", "hi")])]

    assert chunks == ["Hi"]


async def test_the_local_runtime_asks_for_progress() -> None:
    """Without the field llama.cpp sends none."""
    fake = FakeRouter(["qwen3"])
    provider = LlamaCppProvider("http://127.0.0.1:1234", transport=fake.transport())

    async for _ in provider.chat_deltas("qwen3", [Message("user", "hi")]):
        pass

    assert fake.chat_bodies[-1]["return_progress"] is True


async def test_a_remote_endpoint_is_never_sent_the_field() -> None:
    """`return_progress` is llama.cpp's, and a strict endpoint rejects a field
    it does not know."""
    bodies: list[dict] = []

    def reply(request: httpx.Request) -> httpx.Response:
        bodies.append(json.loads(request.content))
        return httpx.Response(
            200, text='data: {"choices":[{"delta":{"content":"Hi"}}]}\n\ndata: [DONE]\n\n'
        )

    remote = OpenAICompatibleChatProvider(
        "http://remote/v1", transport=httpx.MockTransport(reply)
    )

    deltas = [d async for d in remote.chat_deltas("m", [Message("user", "hi")])]

    assert deltas == [Delta("Hi")]
    assert "return_progress" not in bodies[-1]


async def test_a_slow_read_keeps_the_load_budget_until_the_first_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A batch can take longer than the gap allowed between tokens. Progress
    is proof of work, not the start of the answer, so it must not start the
    tight clock."""
    monkeypatch.setattr(openai_chat, "FIRST_TOKEN_SECONDS", 1.0)
    monkeypatch.setattr(openai_chat, "BETWEEN_TOKENS_SECONDS", 0.05)

    async def reads_slowly() -> AsyncIterator[bytes]:
        for processed in (0, 2048, 4096):
            await asyncio.sleep(0.15)
            yield _progress(4096, 0, processed).encode()
        await asyncio.sleep(0.15)
        yield b'data: {"choices":[{"delta":{"content":"Done"}}]}\n\ndata: [DONE]\n\n'

    local = OpenAICompatibleChatProvider(
        "http://local/v1",
        transport=httpx.MockTransport(
            lambda _: httpx.Response(200, content=reads_slowly())
        ),
        prompt_progress=ASKS,
    )

    chunks = [c async for c in local.chat("m", [Message("user", "hi")])]

    assert chunks == ["Done"]
