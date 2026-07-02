"""``web.discover`` executor: route a query to the first configured search provider."""

from __future__ import annotations

from collections.abc import Sequence

from app.capabilities.types import Executor
from app.capabilities.web.discover.providers.base import DiscoverProvider
from app.capabilities.web.discover.schemas import DiscoverInput, DiscoverOutput


class NoDiscoverProviderError(RuntimeError):
    """Raised when no search provider is configured (no platform key/host set)."""


def build_discover_executor(
    providers: Sequence[DiscoverProvider] | None = None,
) -> Executor:
    """Bind the executor to a provider set (defaults to the real env-keyed providers)."""
    registry = list(providers) if providers is not None else _default_providers()

    async def execute(payload: DiscoverInput) -> DiscoverOutput:
        provider = next((p for p in registry if p.is_available()), None)
        if provider is None:
            raise NoDiscoverProviderError(
                "web.discover has no configured search provider "
                "(set a SearXNG host or a Linkup/Baidu key)."
            )
        hits = await provider.search(payload.query, payload.top_k)
        # Enforce the verb's documented cap here, once, for every provider:
        # some backends (e.g. SearXNG) treat `top_k` as a hint and over-return.
        return DiscoverOutput(hits=hits[: payload.top_k])

    return execute


def _default_providers() -> list[DiscoverProvider]:
    from app.capabilities.web.discover.providers.baidu import BaiduProvider
    from app.capabilities.web.discover.providers.linkup import LinkupProvider
    from app.capabilities.web.discover.providers.searxng import SearxngProvider

    return [SearxngProvider(), LinkupProvider(), BaiduProvider()]
