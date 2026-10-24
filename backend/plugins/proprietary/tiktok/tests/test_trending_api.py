"""Trending over the unsigned Explore API, and its browser fallback (no network)."""

from __future__ import annotations

from typing import Any

from proprietary.scraping import sessions
from proprietary.tiktok.session import client, listing


def test_explore_params_are_the_page_s_own_shape():
    first = client.explore_params("gb", first=True)
    more = client.explore_params("gb", first=False)

    # Minimal params return a different, evergreen feed: pin the browser's shape.
    assert first["categoryType"] == "120"
    assert first["device_platform"] == "web_pc"
    assert first["is_new_user"] == "true"
    assert first["aid"] == "1988"
    assert first["app_name"] == "tiktok_web"
    assert first["region"] == "GB"
    assert (first["count"], first["pullType"], first["enable_cache"]) == (
        "8",
        "1",
        "true",
    )
    assert (more["count"], more["pullType"], more["enable_cache"]) == (
        "16",
        "2",
        "false",
    )
    assert client.explore_params("", first=True)["region"] == "US"


class _Holder:
    def __init__(self) -> None:
        self.exit = sessions.Exit("us")
        self.rotations = 0

    async def rotate(self, reason: str, *, country=None, seen=None) -> None:
        self.rotations += 1
        self.exit = sessions.Exit(country)


def _fake_api(monkeypatch, pages: list[Any]) -> list[str]:
    """Serve ``pages`` as successive Explore bodies; returns the URLs requested."""
    requested: list[str] = []

    class _Session:
        async def __aenter__(self):
            return _Holder()

        async def __aexit__(self, *_exc):
            return None

    async def fetch_json(url: str, *, referer: str | None = None, **_kw: Any) -> Any:
        assert referer == "https://www.tiktok.com/explore"
        requested.append(url)
        return pages[min(len(requested) - 1, len(pages) - 1)]

    monkeypatch.setattr(client, "proxy_session", _Session)
    monkeypatch.setattr(client, "fetch_json", fetch_json)
    return requested


def _feed(*ids: str) -> dict[str, Any]:
    return {"itemList": [{"id": i} for i in ids]}


async def test_pulls_until_enough_and_dedupes_by_id(monkeypatch):
    requested = _fake_api(
        monkeypatch, [_feed("1", "2"), _feed("2", "3", "4"), _feed("5")]
    )

    items = await client.fetch_trending_api(4)

    assert [i["id"] for i in items] == ["1", "2", "3", "4"]
    assert len(requested) == 2
    assert "pullType=1" in requested[0] and "count=8" in requested[0]
    assert "pullType=2" in requested[1] and "count=16" in requested[1]


async def test_stops_when_a_pull_brings_nothing_new(monkeypatch):
    requested = _fake_api(monkeypatch, [_feed("1"), _feed("1"), _feed("2")])

    items = await client.fetch_trending_api(5)

    assert [i["id"] for i in items] == ["1"]
    assert len(requested) == 2


async def test_withheld_body_returns_nothing(monkeypatch):
    requested = _fake_api(monkeypatch, [None])

    assert await client.fetch_trending_api(5) == []
    assert len(requested) == 2  # the next country was asked once


async def test_a_withheld_first_pull_is_asked_again_with_the_next_exit_s_region(
    monkeypatch,
):
    monkeypatch.setattr(
        client, "rotate", lambda h, reason, *, seen: h.rotate(reason, country="gb")
    )
    requested = _fake_api(monkeypatch, [None, _feed("1", "2")])

    items = await client.fetch_trending_api(2)

    assert [i["id"] for i in items] == ["1", "2"]
    assert "region=US" in requested[0]
    assert "region=GB" in requested[1] and "pullType=1" in requested[1]


def _browser(monkeypatch) -> list[str]:
    browsed: list[str] = []

    async def draw(url, target_count, markers, extract, interact, **kwargs):
        browsed.append(url)
        return extract(_feed("b1", "b2"))[:target_count]

    monkeypatch.setattr(listing, "_draw", draw)
    return browsed


async def test_fast_path_skips_the_browser(monkeypatch):
    browsed = _browser(monkeypatch)

    async def api(count: int) -> list[dict]:
        return [{"id": "a1"}]

    monkeypatch.setattr(listing, "fetch_trending_api", api)

    items = await listing.fetch_trending("https://www.tiktok.com/explore", 5)

    assert items == [{"id": "a1"}]
    assert browsed == []


async def test_empty_or_failed_api_falls_back_to_the_browser(monkeypatch):
    browsed = _browser(monkeypatch)
    for outcome in ([], RuntimeError("signed now")):

        async def api(count: int, outcome=outcome) -> list[dict]:
            if isinstance(outcome, Exception):
                raise outcome
            return outcome

        monkeypatch.setattr(listing, "fetch_trending_api", api)

        items = await listing.fetch_trending("https://www.tiktok.com/explore", 5)

        assert [i["id"] for i in items] == ["b1", "b2"]
    assert browsed == ["https://www.tiktok.com/explore"] * 2


async def test_kill_switch_sends_trending_through_the_browser(monkeypatch):
    browsed = _browser(monkeypatch)

    async def api(count: int) -> list[dict]:
        raise AssertionError("the API must not be called")

    monkeypatch.setattr(listing, "fetch_trending_api", api)
    monkeypatch.setattr(listing, "_TRENDING_API", False)

    items = await listing.fetch_trending("https://www.tiktok.com/explore", 5)

    assert [i["id"] for i in items] == ["b1", "b2"]
    assert browsed == ["https://www.tiktok.com/explore"]


class _JsonPage:
    def __init__(self, status: int, body: bytes):
        self.status = status
        self.body = body
        self.cookies = {}

    def json(self) -> Any:
        import json

        return json.loads(self.body)


class _JsonHolder:
    rotations = 0


async def test_fetch_json_parses_or_returns_none(monkeypatch):
    client._warmed_at[_JsonHolder] = 0  # warmed: only the API GET is faked
    for body, expected in (
        (b'{"itemList": []}', {"itemList": []}),
        (b"", None),
        (b"<html>not json</html>", None),
    ):

        async def get_page(h, url, headers, *, stage, body=body):
            assert headers["Referer"] == "https://www.tiktok.com/explore"
            return _JsonPage(200, body)

        monkeypatch.setattr(client, "_get_page", get_page)
        monkeypatch.setattr(client, "pace", _no_pace)
        with sessions.bind(_JsonHolder):
            got = await client.fetch_json(
                "https://www.tiktok.com/api/x", referer="https://www.tiktok.com/explore"
            )
        assert got == expected


async def _no_pace(_h) -> None:
    return None
