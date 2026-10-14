"""The TikTok plugin as the app reaches it: its MCP server on the host, behind the license.

TikTok is faked at the scraper's two seams: `_get_page`, the HTTP GET a video or
profile page's rehydration blob comes from, and `_fetch_sync`, the stealth browser
that captures a feed's XHRs. The host, the license check, the tools, the flows and
TikTok's parsing are real.
"""

import json
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

import httpx2
import pytest
from mcp.client.client import Client
from mcp.client.streamable_http import streamable_http_client

from host.app import host_app
from host.tests.mcp_calls import call
from host.tests.serving import serving
from proprietary.license_check.tests.stand_in_keygen import (
    ACCOUNT,
    StandInKeygen,
    accounts_url,
)
from proprietary.tiktok.session import client, listing, proxy

LICENSE = {"Authorization": "License k-1"}


@pytest.fixture
def tiktok(monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    """The real TikTok plugin on the host, its license checked by a stand-in Keygen."""
    with serving(StandInKeygen({"k-1": "VALID"}).app) as keygen_url:
        monkeypatch.setenv("KEYGEN_API_URL", accounts_url(keygen_url))
        monkeypatch.setenv("KEYGEN_ACCOUNT_ID", ACCOUNT)
        with serving(host_app(plugins={"tiktok"})) as base:
            yield f"{base}/tiktok/mcp"


def item_struct(video_id: str, username: str) -> dict[str, Any]:
    """One post as TikTok's blob and item_list XHRs carry it."""
    return {
        "id": video_id,
        "desc": f"clip {video_id}",
        "author": {"id": f"u-{username}", "uniqueId": username},
        "stats": {"playCount": 1000, "diggCount": 50},
    }


def blob_page(scope: str, data: dict[str, Any]) -> str:
    blob = {"__DEFAULT_SCOPE__": {scope: data}}
    return (
        '<script id="__UNIVERSAL_DATA_FOR_REHYDRATION__" '
        f'type="application/json">{json.dumps(blob)}</script>'
    )


@dataclass
class Page:
    status: int
    text: str = ""
    cookies: dict[str, str] = field(default_factory=dict)


@dataclass
class TikTok:
    """What the fake TikTok serves; each feed is the XHR body the page whose URL holds its key fires."""

    feeds: dict[str, dict[str, Any]] = field(default_factory=dict)
    status: int = 200
    browsed: list[str] = field(default_factory=list)


@pytest.fixture
def web(monkeypatch: pytest.MonkeyPatch) -> TikTok:
    tiktok_web = TikTok(
        feeds={
            "/tag/": {"itemList": [item_struct("h1", "ada"), item_struct("h2", "bo")]},
            "/explore": {
                "itemList": [item_struct("t1", "cy"), item_struct("t2", "di")]
            },
            "/search/user": {
                "user_list": [
                    {
                        "user_info": {
                            "uid": "9",
                            "unique_id": "nasa",
                            "nickname": "NASA",
                            "follower_count": 30_000_000,
                        }
                    }
                ]
            },
            "/video/": {
                "comments": [
                    {"cid": "c1", "text": "great", "user": {"unique_id": "eve"}},
                    {"cid": "c2", "text": "same", "user": {"unique_id": "fay"}},
                ]
            },
            "/@": {"itemList": [item_struct("p1", "scout2015")]},
        }
    )

    async def get_page(session: Any, url: str) -> Page:
        if tiktok_web.status != 200:
            return Page(tiktok_web.status)
        if "/video/" in url:
            video_id = url.rsplit("/", 1)[1]
            username = url.split("@")[1].split("/")[0]
            return Page(
                200,
                blob_page(
                    "webapp.video-detail",
                    {"itemInfo": {"itemStruct": item_struct(video_id, username)}},
                ),
            )
        username = url.split("@")[1]
        user = {"id": "u1", "uniqueId": username, "nickname": "Scout"}
        stats = {"followerCount": 1200, "videoCount": 40}
        return Page(
            200,
            blob_page(
                "webapp.user-detail", {"userInfo": {"user": user, "stats": stats}}
            ),
        )

    def fetch_sync(url, target_count, markers, extract, interact, **kwargs):
        tiktok_web.browsed.append(url)
        page = next((key for key in tiktok_web.feeds if key in url), None)
        body = tiktok_web.feeds[page] if page else {}
        return extract(body)[:target_count]

    monkeypatch.setattr(client, "_get_page", get_page)
    monkeypatch.setattr(listing, "_fetch_sync", fetch_sync)
    monkeypatch.setattr(proxy, "_MIN_INTERVAL_S", 0)
    return tiktok_web


async def test_it_offers_four_read_only_tools_that_reach_the_web(tiktok: str) -> None:
    async with (
        httpx2.AsyncClient(headers=LICENSE) as http,
        Client(streamable_http_client(tiktok, http_client=http)) as mcp_client,
    ):
        tools = (await mcp_client.list_tools()).tools

    assert sorted(tool.name for tool in tools) == [
        "comments",
        "scrape",
        "trending",
        "user_search",
    ]
    for tool in tools:
        assert tool.annotations is not None
        assert tool.annotations.read_only_hint is True
        assert tool.annotations.open_world_hint is True


async def test_a_scrape_returns_its_videos_with_a_summary_and_progress(
    tiktok: str, web: TikTok
) -> None:
    progress: list[float] = []

    result = await call(
        tiktok,
        "scrape",
        {
            "urls": ["https://www.tiktok.com/@ada/video/123"],
            "hashtags": ["cats"],
            "results_per_page": 2,
            "max_items": 3,
        },
        LICENSE,
        progress,
    )

    assert not result.is_error
    items = result.structured_content["items"]
    assert [item["id"] for item in items] == ["123", "h1", "h2"]
    assert web.browsed == ["https://www.tiktok.com/tag/cats"]
    summary = result.content[0].text
    assert "https://www.tiktok.com/@ada/video/123" in summary
    assert "https://www.tiktok.com/@bo/video/h2" in summary
    assert progress == [1, 2, 3]


async def test_a_withheld_profile_feed_still_returns_the_account(
    tiktok: str, web: TikTok
) -> None:
    """TikTok often withholds a profile's videos from anonymous access; the account still comes back."""
    del web.feeds["/@"]

    result = await call(tiktok, "scrape", {"profiles": ["@scout2015"]}, LICENSE)

    assert not result.is_error
    profile, withheld = result.structured_content["items"]
    assert (profile["name"], profile["fans"]) == ("scout2015", 1200)
    assert withheld["errorCode"] == "no_items"
    assert "no_items" in result.content[0].text


async def test_tiktok_refusing_every_address_reads_as_the_tool_s_error(
    tiktok: str, web: TikTok
) -> None:
    web.status = 403

    result = await call(
        tiktok, "scrape", {"urls": ["https://www.tiktok.com/@ada/video/1"]}, LICENSE
    )

    assert result.is_error
    assert "TikTok refused anonymous access" in result.content[0].text


async def test_a_video_s_comments_come_with_a_summary_and_progress(
    tiktok: str, web: TikTok
) -> None:
    progress: list[float] = []

    result = await call(
        tiktok,
        "comments",
        {"video_urls": ["https://www.tiktok.com/@ada/video/123"]},
        LICENSE,
        progress,
    )

    assert not result.is_error
    items = result.structured_content["items"]
    assert [item["text"] for item in items] == ["great", "same"]
    assert "eve: great" in result.content[0].text
    assert progress == [1, 2]


async def test_trending_returns_the_explore_feed(tiktok: str, web: TikTok) -> None:
    progress: list[float] = []

    result = await call(tiktok, "trending", {"max_items": 2}, LICENSE, progress)

    assert not result.is_error
    assert [item["id"] for item in result.structured_content["items"]] == ["t1", "t2"]
    assert "https://www.tiktok.com/@cy/video/t1" in result.content[0].text
    assert progress == [1, 2]


async def test_a_user_search_returns_accounts(tiktok: str, web: TikTok) -> None:
    progress: list[float] = []

    result = await call(tiktok, "user_search", {"queries": ["nasa"]}, LICENSE, progress)

    assert not result.is_error
    (account,) = result.structured_content["items"]
    assert (account["name"], account["fans"]) == ("nasa", 30_000_000)
    assert "https://www.tiktok.com/@nasa" in result.content[0].text
    assert progress == [1]


async def test_a_call_naming_nothing_to_scrape_is_refused(tiktok: str) -> None:
    result = await call(tiktok, "scrape", {}, LICENSE)

    assert result.is_error
    assert "at least one of 'urls', 'profiles', or 'hashtags'" in result.content[0].text


@pytest.mark.parametrize(
    ("tool", "arguments"),
    [("comments", {"video_urls": []}), ("user_search", {"queries": []})],
)
async def test_a_call_naming_no_video_or_query_is_refused(
    tiktok: str, tool: str, arguments: dict[str, Any]
) -> None:
    result = await call(tiktok, tool, arguments, LICENSE)

    assert result.is_error


async def test_a_url_that_is_not_http_is_refused(tiktok: str, web: TikTok) -> None:
    result = await call(tiktok, "scrape", {"urls": ["ftp://tiktok.com/@ada"]}, LICENSE)

    assert result.is_error
    assert "Not an http(s) URL" in result.content[0].text
    assert web.browsed == []


def test_without_a_license_the_plugin_answers_nothing(tiktok: str) -> None:
    refused = httpx2.post(tiktok, json={})

    assert (refused.status_code, refused.json()) == (401, {"reason": "missing_license"})
