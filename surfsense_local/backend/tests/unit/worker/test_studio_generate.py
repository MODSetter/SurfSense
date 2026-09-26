"""The one call every Studio format writes through."""

import asyncio
import time
from collections.abc import AsyncIterator
from types import SimpleNamespace

import pytest

from modules.llm.providers.llamacpp import LlamaCppProvider
from modules.llm.resolution import ResolvedGeneration
from tests.unit.llm.providers.llamacpp.fake_router import FakeRouter
from worker.jobs import JobCancelledError
from worker.studio.shared import cancellation, generate

pytestmark = pytest.mark.unit

SELECTION = SimpleNamespace(provider="llamacpp", name="qwen3", tier="compact")


def test_studio_asks_the_model_not_to_think() -> None:
    """Measured: Qwen3 1.7B thought for 15,000 tokens over a 12,000 token
    mindmap prompt, holding the only slot until the window ran out."""
    fake = FakeRouter(["qwen3"])
    fake.thinks = True
    provider = LlamaCppProvider("http://127.0.0.1:1234", transport=fake.transport())

    generate.run_model(ResolvedGeneration(SELECTION, provider), "system", [])

    assert fake.chat_bodies[-1]["chat_template_kwargs"] == {"enable_thinking": False}


def test_a_cap_reaches_llama_server() -> None:
    """Uncapped, a model that loops writes until its window is full."""
    fake = FakeRouter(["qwen3"])
    provider = LlamaCppProvider("http://127.0.0.1:1234", transport=fake.transport())

    generate.run_model(
        ResolvedGeneration(SELECTION, provider), "system", [], max_tokens=1200
    )

    assert fake.chat_bodies[-1]["max_tokens"] == 1200


class _ModelThatNeverFinishes:
    """Streams forever, or reads its prompt forever, until the caller hangs up."""

    def __init__(self, *, streams: bool) -> None:
        self.streams = streams
        self.hung_up = False

    async def chat(self, *_args: object, **_kwargs: object) -> AsyncIterator[str]:
        try:
            while True:
                await asyncio.sleep(0.02)
                if self.streams:
                    yield "more "
        finally:
            self.hung_up = True


@pytest.mark.parametrize("streams", [True, False], ids=["answering", "reading"])
def test_a_cancel_hangs_up_on_the_model(
    monkeypatch: pytest.MonkeyPatch, streams: bool
) -> None:
    """Closing the request is what stops llama-server: measured through the
    router, the slot went idle within 1.5 s of the client hanging up."""
    monkeypatch.setattr(generate, "CANCEL_POLL_SECONDS", 0.05)
    model = _ModelThatNeverFinishes(streams=streams)
    cancel_at = time.monotonic() + 0.2

    def raise_if_cancelled() -> None:
        if time.monotonic() > cancel_at:
            raise JobCancelledError

    with (
        cancellation.watching(raise_if_cancelled),
        pytest.raises(JobCancelledError),
    ):
        generate.run_model(ResolvedGeneration(SELECTION, model), "system", [])

    assert model.hung_up
