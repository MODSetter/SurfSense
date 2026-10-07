"""The search cache: one Hugging Face answer per query per window."""

from pathlib import Path

import pytest

from modules.llm.catalog.local.engines.llamacpp.search.hits import SearchHit
from modules.llm.catalog.local.manifest import load_local_manifest
from modules.llm.catalog.local.search_cache import SearchCache
from modules.llm.catalog.local.service import LocalCatalogService

pytestmark = pytest.mark.unit


def hit(repo: str = "unsloth/gemma-3-4b-it-GGUF") -> SearchHit:
    """A search hit with the fields the cache stores."""
    return SearchHit(repo=repo, downloads=100, likes=10)


def test_a_cached_search_returns_without_a_second_lookup() -> None:
    """A repeated query inside the window is served from the cache."""
    cache = SearchCache(ttl_seconds=300)
    cache.put("gemma", 30, [hit()], now=0.0)

    assert cache.get("gemma", 30, now=1.0) == [hit()]


def test_a_different_query_is_not_served_from_the_cache() -> None:
    """The cache is keyed on the exact query."""
    cache = SearchCache(ttl_seconds=300)
    cache.put("gemma", 30, [hit()], now=0.0)

    assert cache.get("qwen", 30, now=1.0) is None


def test_a_different_limit_is_not_served_from_the_cache() -> None:
    """The cache is keyed on the query and the limit."""
    cache = SearchCache(ttl_seconds=300)
    cache.put("gemma", 30, [hit()], now=0.0)

    assert cache.get("gemma", 10, now=1.0) is None


def test_an_expired_entry_is_not_served() -> None:
    """Entries older than the window are forgotten."""
    cache = SearchCache(ttl_seconds=300)
    cache.put("gemma", 30, [hit()], now=0.0)

    assert cache.get("gemma", 30, now=301.0) is None


def test_a_refreshed_query_replaces_the_stale_answer() -> None:
    """A new lookup after expiry stores the fresh answer."""
    cache = SearchCache(ttl_seconds=300)
    cache.put("gemma", 30, [hit("old/repo")], now=0.0)
    cache.put("gemma", 30, [hit("new/repo")], now=301.0)

    assert cache.get("gemma", 30, now=302.0) == [hit("new/repo")]


@pytest.mark.asyncio
async def test_repeated_searches_cost_one_network_request(tmp_path: Path) -> None:
    """Two identical searches through the service hit Hugging Face once."""
    service = LocalCatalogService(
        load_local_manifest(), tmp_path / "models", tmp_path / "lib"
    )
    calls: list[tuple[str, int]] = []

    async def fake_search(query: str, *, limit: int = 30) -> list[SearchHit]:
        calls.append((query, limit))
        return [hit()]

    service.llamacpp.search = fake_search  # type: ignore[method-assign]

    first = await service.search("gemma")
    second = await service.search("gemma")

    assert first == second == [hit()]
    assert calls == [("gemma", 30)]
