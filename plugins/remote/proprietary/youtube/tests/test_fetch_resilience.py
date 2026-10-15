"""Offline resilience tests for the fetch seam and fan-out worker pool.

No network. ``proprietary.scraping.http.request`` is replaced by a script of
answers, so the rotate-on-block, redirect, keyed-POST and hedging paths run on
real :mod:`proprietary.scraping.sessions` holders deterministically, and the pool
is checked to close every session when the consumer stops early.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any

import pytest

from proprietary.scraping import http, sessions
from proprietary.youtube import innertube, scraper
from proprietary.youtube.innertube import (
    INNERTUBE_PUBLIC_API_KEY,
    INNERTUBE_SEARCH_URL,
    fetch_html,
    post_innertube,
)

_TIMINGS = http.Timings(False, 0.0, 0.0, 0.0, 0.0, 0)


def answer(
    status: int = 200, body: bytes = b'{"ok": true}', location: str | None = None
) -> dict[str, Any]:
    return {"status": status, "body": body, "location": location}


class FakeTransport:
    """Pops one scripted answer per request and records what was sent."""

    def __init__(self, answers: list[Any]) -> None:
        self.answers = answers
        self.sent: list[dict[str, Any]] = []

    async def request(self, method: str, url: str, **kw: Any) -> http.RawResponse:
        self.sent.append({"method": method, "url": url, **kw})
        step = self.answers.pop(0)
        if isinstance(step, Exception):
            raise step
        if callable(step):
            step = await step()
        headers = {"location": step["location"]} if step["location"] else {}
        r = http.RawResponse(
            step["status"], url, headers, {}, step["body"], (), _TIMINGS
        )
        blocked = kw["is_blocked"](r) if kw.get("is_blocked") else False
        return http.RawResponse(
            r.status, r.url, r.headers, {}, r.body, (), _TIMINGS, blocked
        )


@pytest.fixture
def transport(monkeypatch: pytest.MonkeyPatch):
    def install(answers: list[Any]) -> FakeTransport:
        fake = FakeTransport(answers)
        monkeypatch.setattr(http, "request", fake.request)
        return fake

    return install


async def _post_on_holder() -> tuple[dict | None, sessions.SessionHolder]:
    async with sessions.bound("youtube") as h:
        return await post_innertube(INNERTUBE_SEARCH_URL, {"context": {}}), h


async def test_post_rotates_on_429_then_succeeds(transport) -> None:
    fake = transport([answer(429), answer(200)])

    result, h = await _post_on_holder()

    assert result == {"ok": True}
    assert h.rotations == 1  # rotated exactly once to the healthy IP
    # The public key goes on the first try.
    assert (
        fake.sent[0]["url"] == f"{INNERTUBE_SEARCH_URL}?key={INNERTUBE_PUBLIC_API_KEY}"
    )
    assert fake.sent[0]["timeout"] == (4, 12)
    assert fake.sent[0]["allow_redirects"] is False


async def test_post_rotates_on_a_dead_exit_then_succeeds(transport) -> None:
    transport([http.TransportError("Timeout", 28, 4000.0), answer(200)])

    result, h = await _post_on_holder()

    assert result == {"ok": True}
    assert h.rotations == 1


async def test_post_gives_up_after_max_rotations(transport) -> None:
    # Every IP is blocked -> rotate up to the cap, then return None.
    transport([answer(429) for _ in range(innertube._MAX_ROTATIONS + 1)])

    result, h = await _post_on_holder()

    assert result is None
    assert h.rotations == innertube._MAX_ROTATIONS + 1


async def test_post_does_not_rotate_on_non_block_status(transport) -> None:
    # 404 is not a block: fail fast, no wasted IP rotations.
    fake = transport([answer(404)])

    result, h = await _post_on_holder()

    assert result is None
    assert h.rotations == 0
    assert len(fake.sent) == 1


async def test_a_refused_key_tries_once_without_it(transport) -> None:
    fake = transport([answer(400), answer(200)])

    result, _ = await _post_on_holder()

    assert result == {"ok": True}
    assert [s["url"] for s in fake.sent] == [
        f"{INNERTUBE_SEARCH_URL}?key={INNERTUBE_PUBLIC_API_KEY}",
        INNERTUBE_SEARCH_URL,
    ]


async def test_a_403_sweep_tries_one_keyless_exit_not_a_second_sweep(
    transport,
) -> None:
    # A 403 is a block, so the keyed call already rotated through every exit.
    keyed = [answer(403) for _ in range(innertube._MAX_ROTATIONS + 1)]
    fake = transport([*keyed, answer(403)])

    result, _ = await _post_on_holder()

    assert result is None
    assert [s["url"] for s in fake.sent] == [
        f"{INNERTUBE_SEARCH_URL}?key={INNERTUBE_PUBLIC_API_KEY}"
    ] * len(keyed) + [INNERTUBE_SEARCH_URL]


async def test_a_403_sweep_still_answers_when_only_the_key_was_refused(
    transport,
) -> None:
    keyed = [answer(403) for _ in range(innertube._MAX_ROTATIONS + 1)]
    fake = transport([*keyed, answer(200)])

    result, _ = await _post_on_holder()

    assert result == {"ok": True}
    assert fake.sent[-1]["url"] == INNERTUBE_SEARCH_URL


async def test_one_refused_exit_costs_one_rotation_however_many_saw_it(
    transport,
) -> None:
    def refused_after(delay: float):
        async def step() -> dict[str, Any]:
            await asyncio.sleep(delay)
            return answer(429)

        return step

    # Three requests in flight on one exit are refused one after another: the
    # first refusal rotates, the late two are about the exit already dropped.
    refusals = [refused_after(0.03 * n) for n in (1, 2, 3)]
    fake = transport([*refusals, answer(200), answer(200), answer(200)])

    async with sessions.bound("youtube") as h:
        results = await asyncio.gather(
            *(post_innertube(INNERTUBE_SEARCH_URL, {"context": {}}) for _ in range(3))
        )

    assert results == [{"ok": True}] * 3
    assert (h.rotations, h.burned) == (1, False)
    first, retries = fake.sent[:3], fake.sent[3:]
    assert len({id(s["session"]) for s in first}) == 1
    # Every retry runs on the one new exit.
    assert len({id(s["session"]) for s in retries}) == 1
    assert retries[0]["session"] is not first[0]["session"]


async def test_the_sorry_redirect_is_a_block_and_is_not_followed(transport) -> None:
    sorry = "https://www.google.com/sorry/index?continue=x"
    fake = transport([answer(302, b"", sorry), answer(200, b"<html>ok</html>")])

    async with sessions.bound("youtube") as h:
        html = await fetch_html("https://www.youtube.com/watch?v=abc")

    assert html == "<html>ok</html>"
    assert h.rotations == 1
    assert [s["url"] for s in fake.sent] == ["https://www.youtube.com/watch?v=abc"] * 2


async def test_a_plain_redirect_is_followed_once(transport) -> None:
    fake = transport([answer(301, b"", "/watch?v=xyz"), answer(200, b"page")])

    async with sessions.bound("youtube") as h:
        html = await fetch_html("https://www.youtube.com/watch?v=abc")

    assert html == "page"
    assert h.rotations == 0
    assert fake.sent[1]["url"] == "https://www.youtube.com/watch?v=xyz"


async def test_every_exit_blocked_returns_none_without_a_browser(transport) -> None:
    fake = transport([answer(429) for _ in range(innertube._MAX_ROTATIONS + 1)])

    async with sessions.bound("youtube"):
        html = await fetch_html("https://www.youtube.com/watch?v=zzz")

    assert html is None
    assert len(fake.sent) == innertube._MAX_ROTATIONS + 1


async def test_a_slow_request_is_hedged_on_a_fresh_exit(
    transport, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(innertube, "_HEDGE_API_S", 0.05)

    async def stuck() -> dict[str, Any]:
        await asyncio.sleep(5)
        return answer(200, b'{"slow": true}')

    fake = transport([stuck, answer(200, b'{"hedge": true}')])

    result, h = await _post_on_holder()

    assert result == {"hedge": True}
    # The hedge is a one-off on a new exit, never the holder's own session.
    assert fake.sent[0]["session"] is not None
    assert fake.sent[1].get("session") is None
    assert h.rotations == 0


async def test_hedging_off_sends_one_request(
    transport, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(innertube, "_HEDGE_API_S", 0.01)
    monkeypatch.setattr(innertube, "_MAX_HEDGES", 0)

    async def slowish() -> dict[str, Any]:
        await asyncio.sleep(0.1)
        return answer(200)

    fake = transport([slowish])

    result, _ = await _post_on_holder()

    assert result == {"ok": True}
    assert len(fake.sent) == 1


async def test_a_holder_refused_while_a_hedge_answers_is_burned(
    transport, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(innertube, "_HEDGE_API_S", 0.05)

    async def refused() -> dict[str, Any]:
        await asyncio.sleep(0.1)
        return answer(429)

    async def hedge() -> dict[str, Any]:
        await asyncio.sleep(0.2)
        return answer(200)

    transport([refused, hedge])

    result, h = await _post_on_holder()

    assert result == {"ok": True}
    # Not rotated now (the hedge answered), but its next request rotates first
    # and it is never kept idle.
    assert (h.rotations, h.burned) == (0, True)


async def test_fan_out_closes_all_sessions_on_early_stop(transport) -> None:
    transport([answer(200, b"x") for _ in range(100)])

    async def _job(n: int) -> AsyncIterator[dict]:
        for i in range(5):
            await fetch_html(f"https://www.youtube.com/watch?v={n}")
            yield {"job": n, "i": i}

    gen = scraper.fan_out([_job(n) for n in range(20)], concurrency=4)
    collected = []
    async for item in gen:
        collected.append(item)
        if len(collected) >= 3:  # consumer stops early (like a limit)
            break
    await gen.aclose()  # deterministically run fan_out's teardown
    await sessions.close_idle()

    assert collected[:3] == [{"job": 0, "i": i} for i in range(3)]
    assert sessions.live_sessions() == 0, "a worker leaked its proxy session"


async def test_fan_out_keeps_a_warm_holder_for_the_next_call(
    transport, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(innertube, "_KEEP_IDLE", True)
    transport([answer(200, b"x"), answer(200, b"y")])

    async def _job() -> AsyncIterator[dict]:
        yield {"html": await fetch_html("https://www.youtube.com/watch?v=a")}

    try:
        assert [i async for i in scraper.fan_out([_job()])] == [{"html": "x"}]
        assert sessions.live_sessions() == 1  # kept idle, not closed
        assert [i async for i in scraper.fan_out([_job()])] == [{"html": "y"}]
        assert sessions.live_sessions() == 1  # the same one, taken and returned
    finally:
        await sessions.close_idle()
    assert sessions.live_sessions() == 0


async def test_fan_out_empty_jobs_is_noop() -> None:
    out = [x async for x in scraper.fan_out([])]
    assert out == []
