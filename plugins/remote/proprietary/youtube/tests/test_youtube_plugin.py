"""The YouTube plugin as the app reaches it: its MCP server on the host, behind the license.

YouTube itself is faked at the scraper's network seams, `post_innertube` and
`fetch_html`, and its proxy sessions; the host, the license check, the tools and
YouTube's parsing are real.
"""

import json
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from typing import Any

import httpx2
import pytest
from mcp.client.client import Client
from mcp.client.streamable_http import streamable_http_client

from host.app import host_app
from host.tests.mcp_calls import call
from host.tests.serving import serving
from proprietary.license_check import keygen
from proprietary.license_check.tests.stand_in_keygen import ACCOUNT, StandInKeygen
from proprietary.youtube import comments, scraper
from proprietary.youtube.innertube import INNERTUBE_SEARCH_URL

LICENSE = {"Authorization": "License k-1"}


@pytest.fixture
def youtube(monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    """The real YouTube plugin on the host, its license checked by a stand-in Keygen."""
    with serving(StandInKeygen({"k-1": "VALID"}).app) as keygen_url:
        monkeypatch.setattr(keygen, "KEYGEN_API_URL", keygen_url)
        monkeypatch.setattr(keygen, "SURFSENSE_ACCOUNT_ID", ACCOUNT)
        with serving(host_app(plugins={"youtube"})) as base:
            yield f"{base}/youtube/mcp"


def no_proxy_sessions(monkeypatch: pytest.MonkeyPatch) -> None:
    class Holder:
        async def close(self) -> None:
            pass

    async def open_holder() -> Holder:
        return Holder()

    @asynccontextmanager
    async def bind(holder: Holder) -> AsyncIterator[Holder]:
        yield holder

    monkeypatch.setattr(scraper, "open_proxy_holder", open_holder)
    monkeypatch.setattr(scraper, "bind_proxy_holder", bind)


def video(number: int) -> dict[str, Any]:
    """One search result as InnerTube's /search lists it."""
    return {
        "videoRenderer": {
            "videoId": f"vid{number}",
            "title": {"runs": [{"text": f"Video {number}"}]},
            "shortViewCountText": {"simpleText": f"{number}K views"},
            "ownerText": {
                "runs": [
                    {
                        "text": "Ada",
                        "navigationEndpoint": {
                            "browseEndpoint": {
                                "browseId": "UCada",
                                "canonicalBaseUrl": "/@ada",
                            }
                        },
                    }
                ]
            },
        }
    }


def continuation(token: str) -> dict[str, Any]:
    return {
        "continuationItemRenderer": {
            "continuationEndpoint": {"continuationCommand": {"token": token}}
        }
    }


def comment(cid: str, *, reply: bool = False) -> dict[str, Any]:
    return {
        "payload": {
            "commentEntityPayload": {
                "properties": {
                    "commentId": cid,
                    "content": {"content": f"text {cid}"},
                    "publishedTime": "2 days ago",
                    "replyLevel": 1 if reply else 0,
                },
                "author": {"displayName": f"@user{cid}"},
                "toolbar": {"likeCountNotliked": "3", "replyCount": "1"},
            }
        }
    }


def comments_page() -> dict[str, Any]:
    """A /next comments page: two threads, C1 with a reply loader, no next page."""
    thread = {
        "commentThreadRenderer": {
            "commentViewModel": {"commentViewModel": {"commentId": "C1"}},
            "replies": {
                "commentRepliesRenderer": {"contents": [continuation("REPLIES1")]}
            },
        }
    }
    return {
        "frameworkUpdates": {
            "entityBatchUpdate": {"mutations": [comment("C1"), comment("C2")]}
        },
        "onResponseReceivedEndpoints": [
            {"reloadContinuationItemsCommand": {"continuationItems": [thread]}}
        ],
    }


def watch_page() -> str:
    """A watch page whose comments section seeds the /next call."""
    initial = {
        "itemSectionRenderer": {
            "sectionIdentifier": "comment-item-section",
            "contents": [continuation("SECTION")],
        }
    }
    return f"<html><script>var ytInitialData = {json.dumps(initial)};</script></html>"


@pytest.fixture
def youtube_answers(monkeypatch: pytest.MonkeyPatch) -> list[dict]:
    """YouTube answering searches and comment pages; keeps each payload posted."""
    posted: list[dict] = []

    async def post_innertube(
        base_url: str, payload: dict, *, api_key: str | None = None
    ) -> dict | None:
        posted.append(payload)
        if base_url == INNERTUBE_SEARCH_URL:
            return {"contents": [video(n) for n in (1, 2, 3)]}
        return {
            "SECTION": comments_page(),
            "REPLIES1": {
                "frameworkUpdates": {
                    "entityBatchUpdate": {"mutations": [comment("R1", reply=True)]}
                }
            },
        }.get(payload.get("continuation"))

    async def fetch_html(url: str, *, cookies: dict | None = None) -> str:
        return watch_page()

    no_proxy_sessions(monkeypatch)
    monkeypatch.setattr(scraper, "post_innertube", post_innertube)
    monkeypatch.setattr(comments, "fetch_html", fetch_html)
    return posted


async def test_it_offers_read_only_tools_that_reach_the_web(youtube: str) -> None:
    """Read-only and open-world, so the app lets a first-party read skip asking."""
    async with (
        httpx2.AsyncClient(headers=LICENSE) as http,
        Client(streamable_http_client(youtube, http_client=http)) as client,
    ):
        tools = (await client.list_tools()).tools

    assert sorted(tool.name for tool in tools) == ["comments", "scrape"]
    for tool in tools:
        assert tool.annotations is not None
        assert (tool.annotations.read_only_hint, tool.annotations.open_world_hint) == (
            True,
            True,
        )


async def test_a_search_returns_its_videos_with_a_summary_and_progress(
    youtube: str, youtube_answers: list[dict]
) -> None:
    progress: list[float] = []

    result = await call(
        youtube,
        "scrape",
        {"search_queries": ["asyncio"], "max_results": 2},
        LICENSE,
        progress,
    )

    assert not result.is_error
    items = result.structured_content["items"]
    assert [item["title"] for item in items] == ["Video 1", "Video 2"]
    assert result.content[0].text.startswith("2 YouTube items")
    assert progress[-1] == 2
    assert youtube_answers[0]["query"] == "asyncio"


async def test_a_video_s_comments_come_with_their_replies(
    youtube: str, youtube_answers: list[dict]
) -> None:
    progress: list[float] = []

    result = await call(
        youtube,
        "comments",
        {"urls": ["https://www.youtube.com/watch?v=abc"], "sort_by": "TOP_COMMENTS"},
        LICENSE,
        progress,
    )

    assert not result.is_error
    items = result.structured_content["items"]
    assert [(item["cid"], item["replyToCid"]) for item in items] == [
        ("C1", None),
        ("R1", "C1"),
        ("C2", None),
    ]
    assert result.content[0].text.startswith("3 YouTube comments")
    assert progress[-1] == 3


async def test_youtube_refusing_every_request_returns_no_items(
    youtube: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The scraper reads a block as nothing found; it raises no refusal to map."""

    async def refused(
        base_url: str, payload: dict, *, api_key: str | None = None
    ) -> None:
        return None

    no_proxy_sessions(monkeypatch)
    monkeypatch.setattr(scraper, "post_innertube", refused)

    result = await call(youtube, "scrape", {"search_queries": ["asyncio"]}, LICENSE)

    assert not result.is_error
    assert result.structured_content["items"] == []


async def test_a_call_naming_nothing_to_scrape_is_refused(youtube: str) -> None:
    result = await call(youtube, "scrape", {}, LICENSE)

    assert result.is_error
    assert "urls" in result.content[0].text


async def test_a_url_that_is_not_http_is_refused(youtube: str) -> None:
    result = await call(youtube, "comments", {"urls": ["ftp://youtube.com/x"]}, LICENSE)

    assert result.is_error
    assert "Not an http(s) URL" in result.content[0].text


async def test_comments_for_no_video_are_refused(youtube: str) -> None:
    result = await call(youtube, "comments", {"urls": []}, LICENSE)

    assert result.is_error


def test_without_a_license_the_plugin_answers_nothing(youtube: str) -> None:
    refused = httpx2.post(youtube, json={})

    assert (refused.status_code, refused.json()) == (401, {"reason": "missing_license"})
