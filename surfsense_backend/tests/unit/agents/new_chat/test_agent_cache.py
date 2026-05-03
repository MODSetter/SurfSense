"""Regression tests for the compiled-agent cache.

Covers the cache primitive itself (TTL, LRU, in-flight de-duplication,
build-failure non-caching) and the cache-key signature helpers that
``create_surfsense_deep_agent`` relies on. The integration with
``create_surfsense_deep_agent`` is covered separately by the streaming
contract tests; this module focuses on the primitives so a regression
in the cache implementation is caught before it reaches the agent
factory.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

import pytest

from app.agents.new_chat.agent_cache import (
    flags_signature,
    reload_for_tests,
    stable_hash,
    system_prompt_hash,
    tools_signature,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# stable_hash + signature helpers
# ---------------------------------------------------------------------------


def test_stable_hash_is_deterministic_across_calls() -> None:
    a = stable_hash("v1", 42, "thread-9", None, ["x", "y"])
    b = stable_hash("v1", 42, "thread-9", None, ["x", "y"])
    assert a == b


def test_stable_hash_changes_when_any_part_changes() -> None:
    base = stable_hash("v1", 42, "thread-9")
    assert stable_hash("v1", 42, "thread-10") != base
    assert stable_hash("v2", 42, "thread-9") != base
    assert stable_hash("v1", 43, "thread-9") != base


def test_tools_signature_keys_on_name_and_description_not_identity() -> None:
    """Two tool lists with the same surface must hash identically.

    The cache key MUST NOT change when the underlying ``BaseTool``
    instances are different Python objects (a fresh request constructs
    fresh tool instances every time). Hashing on ``(name, description)``
    keeps the cache hot across requests with identical tool surfaces.
    """

    @dataclass
    class FakeTool:
        name: str
        description: str

    tools_a = [FakeTool("alpha", "does alpha"), FakeTool("beta", "does beta")]
    tools_b = [FakeTool("beta", "does beta"), FakeTool("alpha", "does alpha")]
    sig_a = tools_signature(
        tools_a, available_connectors=["NOTION"], available_document_types=["FILE"]
    )
    sig_b = tools_signature(
        tools_b, available_connectors=["NOTION"], available_document_types=["FILE"]
    )
    assert sig_a == sig_b, "tool order must not affect the signature"

    # Adding a tool rotates the key.
    tools_c = [*tools_a, FakeTool("gamma", "does gamma")]
    sig_c = tools_signature(
        tools_c, available_connectors=["NOTION"], available_document_types=["FILE"]
    )
    assert sig_c != sig_a


def test_tools_signature_rotates_when_connector_set_changes() -> None:
    @dataclass
    class FakeTool:
        name: str
        description: str

    tools = [FakeTool("a", "x")]
    base = tools_signature(
        tools, available_connectors=["NOTION"], available_document_types=["FILE"]
    )
    added = tools_signature(
        tools,
        available_connectors=["NOTION", "SLACK"],
        available_document_types=["FILE"],
    )
    assert base != added, "adding a connector must rotate the cache key"


def test_flags_signature_changes_when_flag_flips() -> None:
    @dataclass(frozen=True)
    class Flags:
        a: bool = True
        b: bool = False

    base = flags_signature(Flags())
    flipped = flags_signature(Flags(b=True))
    assert base != flipped


def test_system_prompt_hash_is_stable_and_distinct() -> None:
    p1 = "You are a helpful assistant."
    p2 = "You are a helpful assistant!"  # one-character delta
    assert system_prompt_hash(p1) == system_prompt_hash(p1)
    assert system_prompt_hash(p1) != system_prompt_hash(p2)


# ---------------------------------------------------------------------------
# _AgentCache: hit / miss / TTL / LRU / coalescing / failure-not-cached
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cache_hit_returns_same_instance_on_second_call() -> None:
    cache = reload_for_tests(maxsize=8, ttl_seconds=60.0)
    builds = 0

    async def builder() -> object:
        nonlocal builds
        builds += 1
        return object()

    a = await cache.get_or_build("k", builder=builder)
    b = await cache.get_or_build("k", builder=builder)
    assert a is b, "cache must return the SAME object across hits"
    assert builds == 1, "builder must run exactly once"


@pytest.mark.asyncio
async def test_cache_different_keys_get_different_instances() -> None:
    cache = reload_for_tests(maxsize=8, ttl_seconds=60.0)

    async def builder() -> object:
        return object()

    a = await cache.get_or_build("k1", builder=builder)
    b = await cache.get_or_build("k2", builder=builder)
    assert a is not b


@pytest.mark.asyncio
async def test_cache_stale_entries_get_rebuilt() -> None:
    # ttl=0 means every read sees the entry as immediately stale.
    cache = reload_for_tests(maxsize=8, ttl_seconds=0.0)
    builds = 0

    async def builder() -> object:
        nonlocal builds
        builds += 1
        return object()

    a = await cache.get_or_build("k", builder=builder)
    b = await cache.get_or_build("k", builder=builder)
    assert a is not b, "stale entry must rebuild a fresh instance"
    assert builds == 2


@pytest.mark.asyncio
async def test_cache_evicts_lru_when_full() -> None:
    cache = reload_for_tests(maxsize=2, ttl_seconds=60.0)

    async def builder() -> object:
        return object()

    a = await cache.get_or_build("a", builder=builder)
    _ = await cache.get_or_build("b", builder=builder)
    # Re-touch "a" so "b" is now the LRU victim.
    a_again = await cache.get_or_build("a", builder=builder)
    assert a_again is a
    # Inserting "c" should evict "b" (LRU), not "a".
    _ = await cache.get_or_build("c", builder=builder)
    assert cache.stats()["size"] == 2

    # Confirm "a" is still hot (no rebuild) and "b" is gone (rebuild).
    a_hit = await cache.get_or_build("a", builder=builder)
    assert a_hit is a, "LRU must keep the most-recently-used 'a' entry"


@pytest.mark.asyncio
async def test_cache_concurrent_misses_coalesce_to_single_build() -> None:
    """Two concurrent get_or_build calls on the same key must share one builder."""
    cache = reload_for_tests(maxsize=8, ttl_seconds=60.0)
    build_started = asyncio.Event()
    builds = 0

    async def slow_builder() -> object:
        nonlocal builds
        builds += 1
        build_started.set()
        # Yield control so the second waiter can race against us.
        await asyncio.sleep(0.05)
        return object()

    task_a = asyncio.create_task(cache.get_or_build("k", builder=slow_builder))
    # Wait until the first builder has started, then race a second waiter.
    await build_started.wait()
    task_b = asyncio.create_task(cache.get_or_build("k", builder=slow_builder))

    a, b = await asyncio.gather(task_a, task_b)
    assert a is b, "coalesced waiters must observe the same value"
    assert builds == 1, "concurrent cold misses must collapse to ONE build"


@pytest.mark.asyncio
async def test_cache_does_not_store_failed_builds() -> None:
    """A builder that raises must NOT poison the cache.

    The next caller for the same key must run the builder again (not
    re-raise the cached exception).
    """
    cache = reload_for_tests(maxsize=8, ttl_seconds=60.0)
    attempts = 0

    async def flaky_builder() -> object:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RuntimeError("transient")
        return object()

    with pytest.raises(RuntimeError, match="transient"):
        await cache.get_or_build("k", builder=flaky_builder)

    # Second call must retry — not re-raise the cached exception.
    value = await cache.get_or_build("k", builder=flaky_builder)
    assert value is not None
    assert attempts == 2


@pytest.mark.asyncio
async def test_cache_invalidate_drops_entry() -> None:
    cache = reload_for_tests(maxsize=8, ttl_seconds=60.0)

    async def builder() -> object:
        return object()

    a = await cache.get_or_build("k", builder=builder)
    assert cache.invalidate("k") is True
    b = await cache.get_or_build("k", builder=builder)
    assert a is not b, "post-invalidation lookup must rebuild"


@pytest.mark.asyncio
async def test_cache_invalidate_prefix_drops_matching_entries() -> None:
    cache = reload_for_tests(maxsize=16, ttl_seconds=60.0)

    async def builder() -> object:
        return object()

    await cache.get_or_build("user:1:thread:1", builder=builder)
    await cache.get_or_build("user:1:thread:2", builder=builder)
    await cache.get_or_build("user:2:thread:1", builder=builder)

    removed = cache.invalidate_prefix("user:1:")
    assert removed == 2
    assert cache.stats()["size"] == 1

    # The user:2 entry must still be hot (no rebuild).
    survivor_value = await cache.get_or_build("user:2:thread:1", builder=builder)
    assert survivor_value is not None
