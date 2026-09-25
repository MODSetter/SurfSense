"""A thinking model's trace reaches the caller as reasoning, apart from the answer.

Without it the person watches an empty reply for the whole think, which on a
laptop is the longest part of the turn.
"""

import asyncio
from collections.abc import AsyncIterator

import httpx
import pytest

from modules.llm.providers.llamacpp import LlamaCppProvider
from modules.llm.providers.openai_compatible import chat as openai_chat
from modules.llm.providers.openai_compatible.chat import OpenAICompatibleChatProvider
from modules.llm.providers.types import Delta, Message
from tests.unit.llm.providers.llamacpp.fake_router import FakeRouter

pytestmark = pytest.mark.unit


def thinking_provider() -> LlamaCppProvider:
    """A provider whose model reasons before it answers."""
    fake = FakeRouter(["qwen3"])
    fake.thinks = True
    return LlamaCppProvider("http://127.0.0.1:1234", transport=fake.transport())


async def test_the_trace_streams_as_reasoning_before_the_answer() -> None:
    """In arrival order, each piece marked, so the chat can show both apart."""
    deltas = [
        d
        async for d in thinking_provider().chat_deltas("qwen3", [Message("user", "hi")])
    ]

    assert deltas == [
        Delta("Okay, the user", reasoning=True),
        Delta(" says hi.", reasoning=True),
        Delta("Hel"),
        Delta("lo"),
    ]


async def test_callers_that_only_want_the_answer_never_see_the_trace() -> None:
    """Titles, Studio and the connection check read `chat()` as the reply."""
    chunks = [
        c async for c in thinking_provider().chat("qwen3", [Message("user", "hi")])
    ]

    assert "".join(chunks) == "Hello"


async def test_a_remote_endpoints_reasoning_field_is_read_as_the_trace() -> None:
    """vLLM, Ollama and OpenRouter send `reasoning` where llama.cpp sends
    `reasoning_content`."""
    body = (
        'data: {"choices":[{"delta":{"reasoning":"Hmm."}}]}\n\n'
        'data: {"choices":[{"delta":{"content":"Hi"}}]}\n\n'
        "data: [DONE]\n\n"
    )
    remote = OpenAICompatibleChatProvider(
        "http://remote/v1",
        transport=httpx.MockTransport(lambda _: httpx.Response(200, text=body)),
    )

    deltas = [d async for d in remote.chat_deltas("m", [Message("user", "hi")])]

    assert deltas == [Delta("Hmm.", reasoning=True), Delta("Hi")]


async def test_a_long_think_is_not_mistaken_for_a_model_that_never_started(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The first-token budget is for loading. A trace that keeps flowing past it
    is a model at work, and only silence between its pieces is a fault."""
    monkeypatch.setattr(openai_chat, "FIRST_TOKEN_SECONDS", 0.2)
    monkeypatch.setattr(openai_chat, "BETWEEN_TOKENS_SECONDS", 0.2)

    async def thinks_for_half_a_second() -> AsyncIterator[bytes]:
        for _ in range(5):
            await asyncio.sleep(0.1)
            yield b'data: {"choices":[{"delta":{"reasoning_content":"..."}}]}\n\n'
        yield b'data: {"choices":[{"delta":{"content":"Done"}}]}\n\ndata: [DONE]\n\n'

    remote = OpenAICompatibleChatProvider(
        "http://remote/v1",
        transport=httpx.MockTransport(
            lambda _: httpx.Response(200, content=thinks_for_half_a_second())
        ),
    )

    chunks = [c async for c in remote.chat("m", [Message("user", "hi")])]

    assert chunks == ["Done"]
