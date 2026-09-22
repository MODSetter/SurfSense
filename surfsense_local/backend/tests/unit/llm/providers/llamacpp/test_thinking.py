"""Turning thinking off where a caller asked for a short answer.

A thinking model spends its whole budget on `reasoning_content` before it emits
a single `content` token, so any call with a small `max_tokens` comes back
empty. Measured against Qwen3 1.7B at b11050: a 12 token title request returned
`content: ''`, `finish_reason: length`, and a populated trace.
"""

import pytest

from modules.chat.title import generate_title
from modules.llm.providers.llamacpp import LlamaCppProvider
from modules.llm.providers.openai_compatible.chat import OpenAICompatibleChatProvider
from modules.llm.providers.types import Message
from tests.unit.llm.providers.llamacpp.fake_router import FakeRouter

pytestmark = pytest.mark.unit


def thinking_provider() -> tuple[LlamaCppProvider, FakeRouter]:
    """A provider whose model reasons before it answers."""
    fake = FakeRouter(["qwen3"])
    fake.thinks = True
    return LlamaCppProvider("http://127.0.0.1:1234", transport=fake.transport()), fake


@pytest.mark.asyncio
async def test_a_thinking_model_still_produces_a_title() -> None:
    """The bug this exists for: 12 tokens of budget, all of it spent thinking.

    Asserted through `generate_title` rather than on the request body, because
    the defect is that a caller's `reasoning=False` reached nothing. A test that
    only checked the field would pass with the translation wired to the wrong
    end.
    """
    provider, _ = thinking_provider()

    assert await generate_title(provider, "qwen3", "explain the refund policy")


@pytest.mark.asyncio
async def test_the_answer_path_keeps_its_reasoning() -> None:
    """Thinking is switched off per call, never for the runtime.

    The answer has no token cap and is the one place the trace earns its cost,
    so a router level `--reasoning-budget 0` would pay for a title with every
    reply.
    """
    provider, fake = thinking_provider()

    async for _ in provider.chat("qwen3", [Message("user", "hi")]):
        pass

    assert "thinking_budget_tokens" not in fake.chat_bodies[-1]


@pytest.mark.asyncio
async def test_a_remote_endpoint_is_never_sent_the_field() -> None:
    """`thinking_budget_tokens` is llama.cpp's, and strict endpoints 400 on it.

    Only a caller that knows what it is talking to may add it, so the shared
    OpenAI client keeps ignoring `reasoning` as it does today.
    """
    fake = FakeRouter(["qwen3"])
    remote = OpenAICompatibleChatProvider(
        "http://127.0.0.1:1234/v1", transport=fake.transport()
    )

    async for _ in remote.chat("qwen3", [Message("user", "hi")], reasoning=False):
        pass

    assert fake.chat_bodies[-1].keys() == {"model", "messages", "stream"}
