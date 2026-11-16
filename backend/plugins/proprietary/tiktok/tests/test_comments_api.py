"""Comments over the unsigned comment API, and its browser fallback (no network)."""

from __future__ import annotations

import asyncio
from typing import Any
from urllib.parse import parse_qs, urlsplit

from proprietary.scraping import sessions
from proprietary.tiktok.session import client, listing, proxy

_VIDEO = "https://www.tiktok.com/@cookinginthemidwest/video/7696145792720997663"


class _Holder:
    """A bound holder: the API's fetches are faked, only rotations are real."""

    def __init__(self) -> None:
        self.rotations = 0
        self.reasons: list[str] = []

    async def rotate(self, reason: str, *, country=None, seen=None) -> None:
        self.rotations += 1
        self.reasons.append(reason)


def _page(*cids: str, has_more: int = 1, cursor: int = 0) -> dict[str, Any]:
    return {
        "comments": [{"cid": c, "text": f"t{c}"} for c in cids],
        "has_more": has_more,
        "cursor": cursor,
        "total": 999,
    }


def _fake_api(monkeypatch, pages: list[Any]) -> list[dict[str, Any]]:
    """Serve ``pages`` as successive comment bodies; returns each request's shape."""
    requests: list[dict[str, Any]] = []

    async def fetch_json(url: str, **kw: Any) -> Any:
        query = {k: v[0] for k, v in parse_qs(urlsplit(url).query).items()}
        requests.append({"path": urlsplit(url).path, "query": query, **kw})
        return pages[min(len(requests) - 1, len(pages) - 1)]

    monkeypatch.setattr(client, "fetch_json", fetch_json)
    return requests


async def test_pages_by_cursor_until_enough_and_dedupes(monkeypatch):
    requests = _fake_api(
        monkeypatch,
        [_page("1", "2", cursor=20), _page("2", "3", "4", cursor=40), _page("5")],
    )

    with sessions.bind(_Holder()):  # a bound holder: no session of its own
        comments = await client.fetch_comments_api(_VIDEO, 4)

    assert [c["cid"] for c in comments] == ["1", "2", "3", "4"]
    assert [r["query"]["cursor"] for r in requests] == ["0", "20"]
    first = requests[0]
    assert first["path"] == "/api/comment/list/"
    assert first["query"] == {
        "aid": "1988",
        "aweme_id": "7696145792720997663",
        "count": "20",
        "cursor": "0",
    }
    # The comment API answers a cold session: no homepage warm-up, the video as referer.
    assert first["warm"] is False
    assert first["referer"] == _VIDEO


async def test_stops_when_the_thread_ends(monkeypatch):
    requests = _fake_api(monkeypatch, [_page("1", has_more=0), _page("2")])

    with sessions.bind(_Holder()):
        comments = await client.fetch_comments_api(_VIDEO, 10)

    assert [c["cid"] for c in comments] == ["1"]
    assert len(requests) == 1


async def test_a_withheld_thread_or_a_bad_url_returns_nothing(monkeypatch):
    requests = _fake_api(monkeypatch, [None])

    with sessions.bind(holder := _Holder()):
        assert await client.fetch_comments_api(_VIDEO, 5) == []
        assert await client.fetch_comments_api("https://www.tiktok.com/@a", 5) == []
    assert (
        len(requests) == 2
    )  # the next country was asked once; the profile URL sent nothing
    assert holder.reasons == ["comments withheld"]


async def test_a_withheld_first_page_is_asked_once_more_on_the_next_exit(monkeypatch):
    requests = _fake_api(monkeypatch, [None, _page("1", "2", has_more=0)])

    with sessions.bind(holder := _Holder()):
        comments = await client.fetch_comments_api(_VIDEO, 5)

    assert [c["cid"] for c in comments] == ["1", "2"]
    assert holder.rotations == 1
    assert requests[0]["query"] == requests[1]["query"]


async def test_reports_each_page_as_a_stage(monkeypatch):
    _fake_api(monkeypatch, [_page("1", "2", has_more=0)])
    heard: list[str] = []

    async def hear(message: str) -> None:
        heard.append(message)

    token = proxy.on_stage.set(hear)
    try:
        with sessions.bind(_Holder()):
            await client.fetch_comments_api(_VIDEO, 5)
    finally:
        proxy.on_stage.reset(token)

    assert heard == ["2 comments fetched"]


def _browser(monkeypatch) -> list[str]:
    browsed: list[str] = []

    async def draw(url, target_count, markers, extract, interact, **kwargs):
        browsed.append(url)
        return extract({"comments": [{"cid": "b1"}]})[:target_count]

    monkeypatch.setattr(listing, "_draw", draw)
    return browsed


async def test_fast_path_skips_the_browser(monkeypatch):
    browsed = _browser(monkeypatch)

    async def api(url: str, count: int) -> list[dict]:
        return [{"cid": "a1"}]

    monkeypatch.setattr(listing, "fetch_comments_api", api)

    assert await listing.fetch_comments(_VIDEO, 5) == [{"cid": "a1"}]
    assert browsed == []


async def test_empty_or_failed_api_falls_back_to_the_browser(monkeypatch):
    browsed = _browser(monkeypatch)
    for outcome in ([], RuntimeError("signed now")):

        async def api(url: str, count: int, outcome=outcome) -> list[dict]:
            if isinstance(outcome, Exception):
                raise outcome
            return outcome

        monkeypatch.setattr(listing, "fetch_comments_api", api)

        assert await listing.fetch_comments(_VIDEO, 5) == [{"cid": "b1"}]
    assert browsed == [_VIDEO, _VIDEO]


async def test_kill_switch_sends_comments_through_the_browser(monkeypatch):
    browsed = _browser(monkeypatch)

    async def api(url: str, count: int) -> list[dict]:
        raise AssertionError("the API must not be called")

    monkeypatch.setattr(listing, "fetch_comments_api", api)
    monkeypatch.setattr(listing, "_COMMENTS_API", False)

    assert await listing.fetch_comments(_VIDEO, 5) == [{"cid": "b1"}]
    assert browsed == [_VIDEO]


async def test_each_browser_attempt_is_reported_as_a_stage(monkeypatch):
    calls = 0

    async def draw(url, target_count, markers, extract, interact, **kwargs):
        nonlocal calls
        calls += 1
        return [] if calls == 1 else [{"cid": "b1"}]

    monkeypatch.setattr(listing, "_draw", draw)
    monkeypatch.setattr(listing, "_COMMENTS_API", False)
    monkeypatch.setattr(
        listing, "country_for_rotation", lambda n: ("us", "gb", "de")[n % 3]
    )
    heard: list[str] = []

    async def hear(message: str) -> None:
        heard.append(message)

    token = proxy.on_stage.set(hear)
    try:
        await listing.fetch_comments(_VIDEO, 5)
    finally:
        proxy.on_stage.reset(token)

    assert heard == [
        "comments: browser attempt 1 (us)",
        "comments: browser attempt 2 (gb)",
    ]


async def test_a_withheld_later_page_is_asked_once_more_on_the_next_exit(
    monkeypatch,
):
    requests = _fake_api(
        monkeypatch, [_page("1", "2", cursor=20), None, _page("3", has_more=0)]
    )

    with sessions.bind(holder := _Holder()):
        comments = await client.fetch_comments_api(_VIDEO, 5)

    assert [c["cid"] for c in comments] == ["1", "2", "3"]
    assert holder.rotations == 1
    assert requests[1]["query"]["cursor"] == requests[2]["query"]["cursor"] == "20"


async def test_an_api_that_could_not_be_reached_is_not_rotated_again(monkeypatch):
    requests = _fake_api(monkeypatch, [client._UNREACHABLE])

    with sessions.bind(holder := _Holder()):
        assert await client.fetch_comments_api(_VIDEO, 5) == []

    assert len(requests) == 1
    assert holder.rotations == 0


async def test_browser_fallbacks_wait_for_the_call_s_browser_slots(monkeypatch):
    async def api(url: str, count: int) -> list[dict]:
        return []  # withheld: every thread falls back to the browser

    running = peak = 0

    async def draw(url, target_count, markers, extract, interact, **kwargs):
        nonlocal running, peak
        running += 1
        peak = max(peak, running)
        await asyncio.sleep(0.02)
        running -= 1
        return extract({"comments": [{"cid": url}]})[:target_count]

    monkeypatch.setattr(listing, "fetch_comments_api", api)
    monkeypatch.setattr(listing, "_draw", draw)
    token = listing.BROWSER_SLOTS.set(asyncio.Semaphore(2))
    try:
        found = await asyncio.gather(
            *(listing.fetch_comments(f"{_VIDEO}?v={n}", 1) for n in range(4))
        )
    finally:
        listing.BROWSER_SLOTS.reset(token)

    assert all(found)
    assert peak == 2
