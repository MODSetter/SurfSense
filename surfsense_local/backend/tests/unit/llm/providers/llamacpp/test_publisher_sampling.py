"""The runtime sends a curated model's sampling; a caller's own temperature wins."""

import pytest

from modules.llm.catalog.local.engines.llamacpp.manifest_fields import SamplingSet
from modules.llm.providers.llamacpp import LlamaCppProvider
from modules.llm.providers.types import Message
from tests.unit.llm.providers.llamacpp.fake_router import FakeRouter

pytestmark = pytest.mark.unit


def provider(fake: FakeRouter) -> LlamaCppProvider:
    """A runtime whose curated entry commits Qwen3's thinking set."""
    return LlamaCppProvider(
        "http://127.0.0.1:1234",
        transport=fake.transport(),
        publisher_sampling=lambda model, reasoning: SamplingSet(
            temperature=0.6, top_p=0.95, top_k=20, min_p=0.0
        ),
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


async def test_a_request_carries_the_publishers_whole_set() -> None:
    """top_p, top_k and min_p shape the answer as much as the temperature does."""
    fake = FakeRouter(["qwen3"])

    _ = [c async for c in provider(fake).chat("qwen3", [Message("user", "hi")])]

    body = fake.chat_bodies[0]
    assert (body["top_p"], body["top_k"], body["min_p"]) == (0.95, 20, 0.0)


async def test_a_mode_with_no_set_sends_no_sampling() -> None:
    """llama-server's defaults stand where the publisher committed nothing."""
    fake = FakeRouter(["qwen3"])
    bare = LlamaCppProvider(
        "http://127.0.0.1:1234",
        transport=fake.transport(),
        publisher_sampling=lambda model, reasoning: None,
    )

    _ = [c async for c in bare.chat("qwen3", [Message("user", "hi")])]

    assert not {"temperature", "top_p", "top_k", "min_p"} & set(fake.chat_bodies[0])
