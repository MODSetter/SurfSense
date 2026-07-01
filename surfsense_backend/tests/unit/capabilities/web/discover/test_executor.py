"""`web.discover` executor: pick the first configured provider; self-disable when none.

Boundary mocked: the providers (injected fakes). NOT mocked: the executor's
provider-selection and self-disable behavior.
"""

from __future__ import annotations

import pytest

from app.capabilities.web.discover.executor import (
    NoDiscoverProviderError,
    build_discover_executor,
)
from app.capabilities.web.discover.schemas import (
    DiscoverHit,
    DiscoverInput,
    DiscoverOutput,
)

pytestmark = pytest.mark.unit


class _FakeProvider:
    def __init__(
        self, name: str, available: bool, hits: list[DiscoverHit] | None = None
    ):
        self.name = name
        self._available = available
        self._hits = hits or []
        self.calls: list[tuple[str, int]] = []

    def is_available(self) -> bool:
        return self._available

    async def search(self, query: str, top_k: int) -> list[DiscoverHit]:
        self.calls.append((query, top_k))
        return self._hits


def _hit(url: str, provider: str) -> DiscoverHit:
    return DiscoverHit(url=url, title=url, snippet="s", provider=provider)


async def test_uses_the_first_available_provider():
    first = _FakeProvider(
        "searxng", available=True, hits=[_hit("https://a.com", "searxng")]
    )
    second = _FakeProvider(
        "linkup", available=True, hits=[_hit("https://b.com", "linkup")]
    )
    execute = build_discover_executor(providers=[first, second])

    out = await execute(DiscoverInput(query="acme pricing", top_k=5))

    assert isinstance(out, DiscoverOutput)
    assert [h.url for h in out.hits] == ["https://a.com"]
    assert first.calls == [("acme pricing", 5)]
    assert second.calls == []  # first available short-circuits


async def test_skips_unavailable_providers():
    off = _FakeProvider("searxng", available=False)
    on = _FakeProvider("linkup", available=True, hits=[_hit("https://b.com", "linkup")])
    execute = build_discover_executor(providers=[off, on])

    out = await execute(DiscoverInput(query="q"))

    assert [h.provider for h in out.hits] == ["linkup"]
    assert off.calls == []


async def test_self_disables_when_no_provider_is_configured():
    execute = build_discover_executor(
        providers=[_FakeProvider("searxng", available=False)]
    )

    with pytest.raises(NoDiscoverProviderError):
        await execute(DiscoverInput(query="q"))
