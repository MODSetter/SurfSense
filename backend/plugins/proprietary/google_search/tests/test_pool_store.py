"""Warm IPs shared across copies through Redis (best-effort).

Adopt must skip IPs this copy already holds, or the fleet re-uses nothing new;
and with no Redis every call is a silent no-op, so a hiccup costs a solve
instead of breaking the fetch.
"""

from collections.abc import Iterator
from pathlib import Path

import pytest

from host.tests.redis_server import redis_url
from proprietary.google_search import pool_store as ps


@pytest.fixture
def redis(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    """A store on a real Redis, emptied of warm IPs other tests left."""
    with redis_url(tmp_path) as url:
        monkeypatch.setenv("REDIS_URL", url)
        monkeypatch.setattr(ps, "_client", None)
        monkeypatch.setattr(ps, "_disabled", False)
        monkeypatch.setattr(ps, "_PREFIX", f"{ps._PREFIX}{tmp_path.name}:")
        yield url


def test_key_is_stable_and_prefixed():
    assert ps._key("http://a").startswith(ps._PREFIX)
    assert ps._key("http://a") == ps._key("http://a")
    assert ps._key("http://a") != ps._key("http://b")


async def test_publish_then_adopt_excludes_held_ips(redis):
    await ps.publish("http://a", [{"n": 1}])
    await ps.publish("http://b", [{"n": 2}])
    assert await ps.adopt(exclude={"http://a"}) == ("http://b", [{"n": 2}])


async def test_adopt_none_when_all_held(redis):
    await ps.publish("http://a", [])
    assert await ps.adopt(exclude={"http://a"}) is None


async def test_evict_removes_entry(redis):
    await ps.publish("http://a", [{"n": 1}])
    await ps.evict("http://a")
    assert await ps.adopt(exclude=set()) is None


async def test_without_redis_every_call_is_a_silent_noop(monkeypatch):
    monkeypatch.delenv("REDIS_URL", raising=False)
    monkeypatch.setattr(ps, "_client", None)
    monkeypatch.setattr(ps, "_disabled", False)
    assert await ps.adopt(set()) is None
    await ps.publish("x", [{"n": 1}])
    await ps.evict("x")


async def test_redis_unreachable_is_a_silent_noop(monkeypatch):
    monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:1/0")
    monkeypatch.setattr(ps, "_client", None)
    monkeypatch.setattr(ps, "_disabled", False)
    assert await ps.adopt(set()) is None
    await ps.publish("x", [{"n": 1}])
    await ps.evict("x")
