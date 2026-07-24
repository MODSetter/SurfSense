"""Warm sticky-IP pool bookkeeping (the scale-critical logic in fetch.py).

These pure, lock-guarded helpers decide whether a render reuses a warm IP,
grows the pool (a paid solve), or waits — and how a finished render admits or
evicts its IP. Get the pending/inflight accounting wrong and the pool either
over-solves (cost) or funnels every render onto one IP (re-wall), so the
transitions are worth pinning down offline.
"""

import pytest

from app.proprietary.platforms.google_search import fetch

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _clean_pool():
    def reset():
        fetch._pool.clear()
        fetch._pool_inflight.clear()
        fetch._pool_pending = 0
        fetch._exemption_jar.clear()

    reset()
    yield
    reset()


def test_take_grows_when_pool_empty():
    action, proxy = fetch._pool_take()
    assert action == "grow" and proxy is None
    assert fetch._pool_pending == 1


def test_take_reuses_warm_under_cap():
    fetch._pool["p1"] = 1.0
    action, proxy = fetch._pool_take()
    assert action == "reuse" and proxy == "p1"
    assert fetch._pool_inflight["p1"] == 1


def test_take_spreads_across_least_loaded_ip():
    fetch._pool.update({"p1": 1.0, "p2": 1.0})
    fetch._pool_inflight["p1"] = 1  # p2 is idle
    action, proxy = fetch._pool_take()
    assert action == "reuse" and proxy == "p2"


def test_take_waits_when_full_and_every_ip_capped(monkeypatch):
    monkeypatch.setattr(fetch, "_WARM_POOL_TARGET", 2)
    monkeypatch.setattr(fetch, "_WARM_IP_MAX_CONCURRENCY", 1)
    fetch._pool.update({"p1": 1.0, "p2": 1.0})
    fetch._pool_inflight.update({"p1": 1, "p2": 1})
    action, proxy = fetch._pool_take()
    assert action == "wait" and proxy is None
    assert fetch._pool_pending == 0  # a wait must NOT reserve a solve


def test_take_grows_only_up_to_target_counting_pending(monkeypatch):
    monkeypatch.setattr(fetch, "_WARM_POOL_TARGET", 2)
    monkeypatch.setattr(fetch, "_WARM_IP_MAX_CONCURRENCY", 1)
    fetch._pool["p1"] = 1.0
    fetch._pool_inflight["p1"] = 1  # warm but capped
    assert fetch._pool_take()[0] == "grow"  # pool(1)+pending(0) < 2
    assert fetch._pool_pending == 1
    assert fetch._pool_take()[0] == "wait"  # pool(1)+pending(1) == 2 → no more solves


def test_settle_good_admits_and_releases():
    fetch._pool_pending = 1
    fetch._pool_inflight["p1"] = 1
    fetch._pool_settle("p1", good=True, grew=True)
    assert "p1" in fetch._pool
    assert "p1" not in fetch._pool_inflight
    assert fetch._pool_pending == 0


def test_settle_walled_evicts_ip_and_drops_exemption():
    fetch._pool["p1"] = 1.0
    fetch._pool_inflight["p1"] = 1
    fetch._exemption_jar["p1"] = [{"name": "GOOGLE_ABUSE_EXEMPTION"}]
    fetch._pool_settle("p1", good=False, grew=False)
    assert "p1" not in fetch._pool
    assert "p1" not in fetch._exemption_jar


def test_adopt_releases_pending_and_pins_ip():
    fetch._pool_pending = 1  # reserved by a grow that we satisfy via the store
    fetch._pool_adopt("shared")
    assert fetch._pool_pending == 0
    assert "shared" in fetch._pool
    assert fetch._pool_inflight["shared"] == 1


def test_abort_grow_releases_the_reserved_slot():
    fetch._pool_pending = 2
    fetch._pool_abort_grow()
    assert fetch._pool_pending == 1
