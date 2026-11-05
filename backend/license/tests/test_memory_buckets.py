"""The per-process buckets the rate limits fall back to without Redis: forgotten an hour
after their last use, never more than the cap, and spent in order, the address first."""

from __future__ import annotations

import pytest

from license import token_bucket
from license.settings import config
from license.tests.job_pack_portal import PackPortal

pytestmark = pytest.mark.unit

HOUR = 3600.0


@pytest.fixture
def memory(monkeypatch: pytest.MonkeyPatch) -> None:
    def redis_down() -> None:
        raise OSError("no Redis in unit tests")

    monkeypatch.setattr(token_bucket, "_redis", redis_down)
    monkeypatch.setattr(token_bucket, "_memory_buckets", {})


class Clock:
    def __init__(self, now: float) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now


async def take(scope: str) -> int:
    return await token_bucket.acquire_token(scope, capacity=2, refill_per_sec=2 / HOUR)


async def test_a_bucket_idle_for_an_hour_is_forgotten(
    memory: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Idle that long, it is full again, so forgetting it changes no answer."""
    clock = Clock(1_800_000_000.0)
    monkeypatch.setattr(token_bucket.time, "time", clock)
    await take("license:refresh:ip:198.51.100.1")
    clock.now += HOUR - 120
    await take("license:refresh:ip:198.51.100.2")
    clock.now += 120

    await take("license:refresh:ip:198.51.100.3")

    assert list(token_bucket._memory_buckets) == [
        "license:refresh:ip:198.51.100.2",
        "license:refresh:ip:198.51.100.3",
    ]


async def test_the_buckets_are_capped_dropping_the_least_recently_used(
    memory: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A flood of addresses cannot grow the process without bound."""
    monkeypatch.setattr(token_bucket, "_MAX_MEMORY_BUCKETS", 3)
    for scope in ("a", "b", "c", "a"):
        await take(scope)

    await take("d")

    assert set(token_bucket._memory_buckets) == {"c", "a", "d"}


@pytest.mark.parametrize(
    ("route", "per_address", "per_key"),
    [
        (
            "refresh",
            "LICENSE_REFRESH_RATE_LIMIT_IP_PER_HOUR",
            "LICENSE_REFRESH_RATE_LIMIT_PER_HOUR",
        ),
        (
            "job-pack",
            "LICENSE_JOB_PACK_RATE_LIMIT_IP_PER_HOUR",
            "LICENSE_JOB_PACK_RATE_LIMIT_PER_HOUR",
        ),
    ],
)
async def test_a_caller_the_address_bucket_refuses_spends_nothing_of_the_keys(
    pack_portal: PackPortal,
    monkeypatch: pytest.MonkeyPatch,
    route: str,
    per_address: str,
    per_key: str,
) -> None:
    """Otherwise one address could drain the key a firm's other computers share."""
    monkeypatch.setattr(config, per_address, 1)
    monkeypatch.setattr(config, per_key, 2)
    send = pack_portal.refresh if route == "refresh" else pack_portal.ask

    codes = [
        (await send("KEY-nobody", ip=ip)).status_code
        for ip in ("203.0.113.1", "203.0.113.1", "203.0.113.2", "203.0.113.3")
    ]

    assert codes == [404, 429, 404, 429]
