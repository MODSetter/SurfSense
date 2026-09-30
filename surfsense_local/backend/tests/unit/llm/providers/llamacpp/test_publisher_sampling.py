"""The runtime sends a curated model's temperature unless the caller chose one."""

import pytest

from modules.llm.providers.llamacpp import LlamaCppProvider
from modules.llm.providers.types import Message
from tests.unit.llm.providers.llamacpp.fake_router import FakeRouter

pytestmark = pytest.mark.unit


def provider(fake: FakeRouter) -> LlamaCppProvider:
    """A runtime whose curated entry commits a temperature of 0.6."""
    return LlamaCppProvider(
        "http://127.0.0.1:1234",
        transport=fake.transport(),
        publisher_temperature=lambda model, reasoning: 0.6,
    )


async def test_a_request_carries_the_publishers_temperature() -> None:
    """Chat sets none of its own, so the entry's reviewed setting applies."""
    fake = FakeRouter(["qwen3"])

    _ = [c async for c in provider(fake).chat("qwen3", [Message("user", "hi")])]

    assert fake.chat_bodies[0]["temperature"] == 0.6


async def test_a_callers_own_temperature_wins() -> None:
    """A title is asked for at zero to be the same every time."""
    fake = FakeRouter(["qwen3"])

    _ = [
        c
        async for c in provider(fake).chat(
            "qwen3", [Message("user", "hi")], temperature=0
        )
    ]

    assert fake.chat_bodies[0]["temperature"] == 0
