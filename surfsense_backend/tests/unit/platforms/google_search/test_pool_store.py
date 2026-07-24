"""Cross-process warm-IP exemption store (best-effort Redis cache).

Redis itself isn't unit-testable here, but the boundary is: adopt must skip IPs
this process already holds (or the fleet re-uses nothing new), and every path
must degrade to a silent no-op when Redis is down (or a hiccup would break the
fetch instead of just costing a solve).
"""

import pytest

from app.proprietary.platforms.google_search import pool_store as ps

pytestmark = pytest.mark.unit


class _FakeRedis:
    def __init__(self):
        self.store: dict[str, str] = {}

    def ping(self):
        return True

    def set(self, k, v, ex=None):
        self.store[k] = v

    def get(self, k):
        return self.store.get(k)

    def delete(self, k):
        self.store.pop(k, None)

    def scan_iter(self, match=None, count=None):
        return list(self.store.keys())


@pytest.fixture
def fake(monkeypatch):
    r = _FakeRedis()
    monkeypatch.setattr(ps, "_client", r)
    monkeypatch.setattr(ps, "_disabled", False)
    return r


def test_key_is_stable_and_prefixed():
    assert ps._key("http://a").startswith(ps._PREFIX)
    assert ps._key("http://a") == ps._key("http://a")
    assert ps._key("http://a") != ps._key("http://b")


def test_publish_then_adopt_excludes_held_ips(fake):
    ps._publish_sync("http://a", [{"n": 1}])
    ps._publish_sync("http://b", [{"n": 2}])
    proxy, cookies = ps._adopt_sync(exclude={"http://a"})
    assert proxy == "http://b" and cookies == [{"n": 2}]


def test_adopt_none_when_all_held(fake):
    ps._publish_sync("http://a", [])
    assert ps._adopt_sync(exclude={"http://a"}) is None


def test_evict_removes_entry(fake):
    ps._publish_sync("http://a", [{"n": 1}])
    ps._evict_sync("http://a")
    assert ps._adopt_sync(exclude=set()) is None


def test_disabled_is_silent_noop(monkeypatch):
    monkeypatch.setattr(ps, "_disabled", True)
    monkeypatch.setattr(ps, "_client", None)
    assert ps._adopt_sync(set()) is None
    ps._publish_sync("x", [{"n": 1}])  # must not raise
    ps._evict_sync("x")  # must not raise
