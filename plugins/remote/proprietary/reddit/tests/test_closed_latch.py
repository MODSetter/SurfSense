"""Reddit's closed logged-out reads: fail fast, and remember it for a while.

No network. A fake holder walks fake exits the way ``_RotatingSession`` walks
countries; the 403 body is Reddit's "blocked by network security" page.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import pytest

from proprietary.reddit import fetch
from proprietary.reddit.fetch import (
    RedditAccessBlockedError,
    _current_session,
    fetch_page,
)

_PAGE = "<shreddit-app></shreddit-app>"
_CLOSED_PAGE = (
    Path(__file__).parent / "fixtures/blocked_by_network_security.html"
).read_bytes()


class _Page:
    def __init__(self, status: int, body: bytes | None = None) -> None:
        self.status = status
        self.body = body if body is not None else _PAGE.encode()


class _Exit:
    """One exit: page GETs answer ``status`` with ``body``."""

    def __init__(self, country: str, status: int, body: bytes | None = None) -> None:
        self.country = country
        self.status = status
        self.body = body
        self.gets = 0

    async def get(self, url, headers=None, cookies=None):
        self.gets += 1
        return _Page(self.status, self.body)


class _Holder:
    """Rotates through ``exits``; every warm mints a jar unless ``mint`` is off."""

    def __init__(self, exits: list[_Exit], *, mint: bool = True) -> None:
        self._exits = exits
        self.session = exits[0]
        self.country = exits[0].country
        self.rotations = 0
        self.warmed = False
        self.cookies: dict[str, str] = {}
        self.warm_calls = 0
        self._mint = mint

    async def warm(self) -> bool:
        self.warm_calls += 1
        if self._mint:
            self.cookies = {"loid": "x"}
        return True

    async def rotate(self):
        self.rotations += 1
        self.session = self._exits[min(self.rotations, len(self._exits) - 1)]
        self.country = self.session.country
        self.warmed = False
        self.cookies = {}
        return self.session

    async def pace(self) -> None:
        return None

    async def close(self) -> None:
        return None


def _closed_exits(n: int = fetch._MAX_ROTATIONS + 1) -> list[_Exit]:
    countries = ["us", "gb", "de", "ca", "nl", "fr"]
    return [_Exit(countries[i % len(countries)], 403, _CLOSED_PAGE) for i in range(n)]


async def _fetch_on(holder: _Holder, path: str = "r/python/about") -> Any:
    token = _current_session.set(holder)
    try:
        return await fetch_page(path)
    finally:
        _current_session.reset(token)


async def test_each_warm_and_fetch_is_reported_as_a_stage() -> None:
    """The give-up path warms twice; the caller hears each warm and fetch."""
    heard: list[str] = []

    async def report(message: str) -> None:
        heard.append(message)

    token = fetch.on_stage.set(report)
    try:
        with pytest.raises(RedditAccessBlockedError):
            await _fetch_on(_Holder(_closed_exits()))
    finally:
        fetch.on_stage.reset(token)

    assert heard == [
        "warming an anonymous session (us)",
        "fetching r/python/about",
        "warming an anonymous session (gb)",
        "fetching r/python/about",
    ]


async def test_two_countries_showing_the_closed_page_end_the_call() -> None:
    """Two warms, not nine: the endpoint is closed, not this exit."""
    holder = _Holder(_closed_exits())

    with pytest.raises(RedditAccessBlockedError) as raised:
        await _fetch_on(holder)

    assert (holder.warm_calls, holder.rotations) == (2, 1)
    message = str(raised.value)
    assert "logged-out reads are closed" in message
    assert "blocked by network security" in message
    assert "gb and us" in message
    assert "checks again after" in message


async def test_while_latched_a_call_fails_before_any_warm() -> None:
    await _latch(_Holder(_closed_exits()))
    later = _Holder([_Exit("us", 200)])

    started = time.perf_counter()
    with pytest.raises(RedditAccessBlockedError, match="logged-out reads are closed"):
        await _fetch_on(later)

    assert time.perf_counter() - started < 0.5
    assert (later.warm_calls, later.session.gets) == (0, 0)


async def test_a_call_with_no_bound_session_fails_before_opening_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await _latch(_Holder(_closed_exits()))
    opened: list[bool] = []

    async def no_holder() -> Any:
        opened.append(True)
        raise AssertionError("opened a proxy session while latched")

    monkeypatch.setattr(fetch, "open_proxy_holder", no_holder)

    with pytest.raises(RedditAccessBlockedError):
        await fetch_page("r/python/about")
    assert opened == []


async def test_one_country_showing_it_is_a_dirty_exit_and_rotates_on() -> None:
    holder = _Holder([_Exit("us", 403, _CLOSED_PAGE), _Exit("gb", 200)])

    assert await _fetch_on(holder) == _PAGE
    assert holder.rotations == 1
    assert fetch._closed.until == 0.0


async def test_the_page_before_a_warm_does_not_count() -> None:
    """A cold request meets the same page on the bot wall the warm clears."""
    holder = _Holder(_closed_exits(), mint=False)

    with pytest.raises(RedditAccessBlockedError, match=r"rotated IPs \(403\)"):
        await _fetch_on(holder)

    assert holder.rotations == fetch._MAX_ROTATIONS
    assert fetch._closed.until == 0.0


async def test_a_plain_403_still_rotates_through_every_country() -> None:
    holder = _Holder([_Exit(c, 403, b"Forbidden") for c in ("us", "gb", "de")] * 3)

    with pytest.raises(RedditAccessBlockedError, match=r"rotated IPs \(403\)"):
        await _fetch_on(holder)

    assert holder.rotations == fetch._MAX_ROTATIONS


async def test_after_the_latch_one_call_probes_and_a_200_reopens() -> None:
    await _latch(_Holder(_closed_exits()))
    fetch._closed.until = time.monotonic() - 1  # the latch ran out
    probe = _Holder([_Exit("us", 200)])

    assert await _fetch_on(probe) == _PAGE
    assert (fetch._closed.until, fetch._closed.sightings) == (0.0, {})


async def test_other_calls_still_fail_fast_while_one_probes() -> None:
    await _latch(_Holder(_closed_exits()))
    fetch._closed.until = time.monotonic() - 1
    fetch._closed.check()  # the probing call takes the lease

    with pytest.raises(RedditAccessBlockedError):
        await _fetch_on(_Holder([_Exit("us", 200)]))


async def test_a_probe_that_meets_the_page_again_latches_after_one_warm() -> None:
    await _latch(_Holder(_closed_exits()))
    fetch._closed.until = time.monotonic() - 1
    probe = _Holder(_closed_exits())

    with pytest.raises(RedditAccessBlockedError):
        await _fetch_on(probe)

    assert probe.warm_calls == 1
    assert fetch._closed.until > time.monotonic() + fetch._CLOSED_LATCH_S - 60


async def test_latch_off_still_fails_fast_but_keeps_no_memory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(fetch, "_CLOSED_LATCH_S", 0.0)
    first = _Holder(_closed_exits())
    with pytest.raises(RedditAccessBlockedError, match=r"fails the same way\.$"):
        await _fetch_on(first)
    assert first.warm_calls == 2
    later = _Holder([_Exit("us", 200)])

    assert await _fetch_on(later) == _PAGE
    assert later.warm_calls == 1


async def test_quorum_zero_turns_the_check_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(fetch, "_CLOSED_QUORUM", 0)
    holder = _Holder(_closed_exits())

    with pytest.raises(RedditAccessBlockedError, match=r"rotated IPs \(403\)"):
        await _fetch_on(holder)

    assert holder.rotations == fetch._MAX_ROTATIONS


async def test_the_warm_is_one_plain_request_whose_cookies_every_page_carries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reddit sets ``loid`` on its first answer, a challenge page: no browser needed."""
    asked: list[tuple[str, dict[str, str]]] = []

    class _Session:
        def __init__(self, **kwargs: Any) -> None:
            pass

        async def __aenter__(self) -> _Session:
            return self

        async def __aexit__(self, *exc: object) -> None:
            return None

        async def get(self, url: str, headers=None, cookies=None) -> Any:
            asked.append((url, cookies or {}))
            if len(asked) == 1:
                return type(
                    "P", (), {"status": 200, "cookies": {"loid": "x"}, "body": b"wall"}
                )()
            return type("P", (), {"status": 200, "cookies": {}, "body": b"<html/>"})()

    monkeypatch.setattr(fetch, "FetcherSession", _Session)
    monkeypatch.setattr(fetch, "get_sticky_proxy_url", lambda *_: "http://p:1")

    async with fetch.proxy_session():
        page = await fetch.fetch_page("svc/shreddit/community-more-posts/new", {})

    assert page == "<html/>"
    assert len(asked) == 2
    # A first request with no cookie draws a reCAPTCHA page, and the exit's full
    # pages a JavaScript check after it (probe 2026-10-22, three countries).
    assert asked[0][1] == {"over18": "1"}
    assert asked[1][1]["loid"] == "x"


async def test_page_fetches_make_one_attempt_per_exit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: dict[str, Any] = {}

    class _Session:
        def __init__(self, **kwargs: Any) -> None:
            seen.update(kwargs)

        async def __aenter__(self) -> _Session:
            return self

    monkeypatch.setattr(fetch, "FetcherSession", _Session)
    monkeypatch.setattr(fetch, "get_sticky_proxy_url", lambda *_: "http://p:1")
    monkeypatch.setattr(fetch, "_country_for_rotation", lambda _n: "us")

    await fetch.open_proxy_holder()

    assert (seen["retries"], seen["timeout"]) == (1, (5, fetch._REQUEST_TIMEOUT_S))


async def _latch(holder: _Holder) -> None:
    """Drive ``holder`` into the closed page until the latch is set."""
    with pytest.raises(RedditAccessBlockedError):
        await _fetch_on(holder)
    assert fetch._closed.until > time.monotonic()


async def test_a_route_is_asked_for_as_reddit_spells_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``more-comments`` with a trailing slash is a 403 network-security page."""
    asked: list[str] = []

    class _Session:
        def __init__(self, **kwargs: Any) -> None:
            pass

        async def __aenter__(self) -> _Session:
            return self

        async def __aexit__(self, *exc: object) -> None:
            return None

        async def get(self, url: str, headers=None, cookies=None) -> Any:
            asked.append(url)
            return type(
                "P", (), {"status": 200, "cookies": {"loid": "x"}, "body": b""}
            )()

        async def post(self, url: str, data=None, headers=None, cookies=None) -> Any:
            asked.append(url)
            return type("P", (), {"status": 200, "cookies": {}, "body": b"<html/>"})()

    monkeypatch.setattr(fetch, "FetcherSession", _Session)
    monkeypatch.setattr(fetch, "get_sticky_proxy_url", lambda *_: "http://p:1")

    async with fetch.proxy_session():
        await fetch.fetch_page("comments/abc/")
        await fetch.fetch_page(
            "svc/shreddit/more-comments/Python/t3_abc",
            {"top-level": "1"},
            form={"cursor": "c"},
        )

    assert asked[1:] == [
        "https://www.reddit.com/comments/abc/",
        "https://www.reddit.com/svc/shreddit/more-comments/Python/t3_abc?top-level=1",
    ]


async def test_a_post_comes_from_reddit_s_own_page_not_from_a_search(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A POST with the stealth headers' Google referer is a 403 (probe 2026-10-22)."""
    posted: list[dict[str, str]] = []

    class _Session:
        def __init__(self, **kwargs: Any) -> None:
            pass

        async def __aenter__(self) -> _Session:
            return self

        async def __aexit__(self, *exc: object) -> None:
            return None

        async def get(self, url: str, headers=None, cookies=None) -> Any:
            return type(
                "P", (), {"status": 200, "cookies": {"loid": "x"}, "body": b""}
            )()

        async def post(self, url: str, data=None, headers=None, cookies=None) -> Any:
            posted.append(headers or {})
            return type("P", (), {"status": 200, "cookies": {}, "body": b"<html/>"})()

    monkeypatch.setattr(fetch, "FetcherSession", _Session)
    monkeypatch.setattr(fetch, "get_sticky_proxy_url", lambda *_: "http://p:1")

    async with fetch.proxy_session():
        await fetch.fetch_page(
            "svc/shreddit/more-comments/P/t3_a", form={"cursor": "c"}
        )

    (headers,) = posted
    assert (headers["Referer"], headers["Origin"]) == (
        "https://www.reddit.com/",
        "https://www.reddit.com",
    )
