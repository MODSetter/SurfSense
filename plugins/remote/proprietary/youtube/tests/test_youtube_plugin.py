"""The YouTube plugin as the app reaches it: its MCP server on the host, behind the license.

YouTube itself is faked at the scraper's network seams, `post_innertube` and
`fetch_html`, so its proxy holders never open a session; the host, the license
check, the tools and YouTube's parsing are real.
"""

import json
from collections.abc import Iterator
from typing import Any

import httpx2
import pytest
from mcp.client.client import Client
from mcp.client.streamable_http import streamable_http_client

from host.app import host_app
from host.tests.mcp_calls import call
from host.tests.serving import serving
from mcp_server import progress as progress_module
from mcp_server.results import ELLIPSIS, MAX_TEXT_BYTES
from proprietary.license_check.tests.stand_in_keygen import (
    ACCOUNT,
    StandInKeygen,
    accounts_url,
)
from proprietary.youtube import comments, scraper
from proprietary.youtube.innertube import INNERTUBE_SEARCH_URL
from proprietary.youtube.schemas import SubtitleTrack

LICENSE = {"Authorization": "License k-1"}


@pytest.fixture
def youtube(monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    """The real YouTube plugin on the host, its license checked by a stand-in Keygen."""
    with serving(StandInKeygen({"k-1": "VALID"}).app) as keygen_url:
        monkeypatch.setenv("KEYGEN_API_URL", accounts_url(keygen_url))
        monkeypatch.setenv("KEYGEN_ACCOUNT_ID", ACCOUNT)
        with serving(host_app(plugins={"youtube"})) as base:
            yield f"{base}/youtube/mcp"


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


@pytest.fixture
def every_stage(monkeypatch: pytest.MonkeyPatch) -> None:
    """Progress is sent at most once a second; these calls take milliseconds."""
    monkeypatch.setattr(progress_module, "INTERVAL_SECONDS", 0.0)


async def test_a_search_returns_its_videos_with_a_summary_and_progress(
    youtube: str, youtube_answers: list[dict], every_stage: None
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
    # The agent reads each item in the text (opencode drops structured content).
    summary, *lines = result.content[0].text.split("\n")
    assert summary == "2 YouTube items"
    assert [json.loads(line)["title"] for line in lines] == ["Video 1", "Video 2"]
    assert json.loads(lines[0])["viewCount"] == 1000
    assert progress[-1] == 2
    assert youtube_answers[0]["query"] == "asyncio"


async def test_asked_for_subtitles_the_agent_reads_the_whole_transcript(
    youtube: str, youtube_answers: list[dict], monkeypatch: pytest.MonkeyPatch
) -> None:
    transcript = "1\n00:00:01,000 --> 00:00:02,000\nword\n\n" * 200  # ~7 KB

    async def subtitles(video_id: str, **kwargs: Any) -> list[SubtitleTrack]:
        return [SubtitleTrack(type="auto_generated", language="en", srt=transcript)]

    monkeypatch.setattr(scraper, "fetch_subtitles", subtitles)

    result = await call(
        youtube,
        "scrape",
        {"search_queries": ["asyncio"], "max_results": 1, "download_subtitles": True},
        LICENSE,
    )

    _, line = result.content[0].text.split("\n", 1)
    assert json.loads(line)["subtitles"] == [{"language": "en", "srt": transcript}]


async def test_each_video_s_transcript_gets_a_share_of_the_text(
    youtube: str, youtube_answers: list[dict], monkeypatch: pytest.MonkeyPatch
) -> None:
    cue = "1\n00:00:01,000 --> 00:00:02,000\n"
    # About 20 KB each; quotes and Cyrillic take more bytes in the text than
    # they have characters.
    transcripts = {
        "vid1": f"{cue}word\n\n" * 500,
        "vid2": f'{cue}"quoted"\n\n' * 400,
        "vid3": f"{cue}\u0441\u043b\u043e\u0432\u043e\n\n" * 450,
    }

    async def subtitles(video_id: str, **kwargs: Any) -> list[SubtitleTrack]:
        srt = transcripts[video_id]
        return [SubtitleTrack(type="auto_generated", language="en", srt=srt)]

    monkeypatch.setattr(scraper, "fetch_subtitles", subtitles)

    result = await call(
        youtube,
        "scrape",
        {"search_queries": ["asyncio"], "max_results": 3, "download_subtitles": True},
        LICENSE,
    )

    text = result.content[0].text
    assert len(text.encode()) <= MAX_TEXT_BYTES
    summary, *lines = text.split("\n")
    assert summary == "3 YouTube items"
    shown = [json.loads(line) for line in lines]
    assert [video["url"] for video in shown] == [
        f"https://www.youtube.com/watch?v=vid{n}" for n in (1, 2, 3)
    ]
    for video in shown:
        srt = video["subtitles"][0]["srt"]
        assert srt.endswith(ELLIPSIS)
        assert transcripts[video["id"]].startswith(srt.removesuffix(ELLIPSIS))
        assert len(srt) > 5_000  # a third of the cap, not CLIP_CHARS
    # Whole for a client that reads structured content.
    items = result.structured_content["items"]
    assert [item["subtitles"][0]["srt"] for item in items] == list(transcripts.values())


def test_one_video_s_transcript_keeps_nearly_the_whole_cap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("KEYGEN_ACCOUNT_ID", ACCOUNT)  # read at the server's import
    from proprietary.youtube import server

    item = {
        "id": "vid1",
        "url": "https://www.youtube.com/watch?v=vid1",
        "publishedTimeText": "3 days ago",
        "text": "d" * 5_000,
        "subtitles": [{"language": "en", "srt": "word " * 10_000}],
    }

    video = server._video_sharing_cap(1)(item)

    line = json.dumps(video, ensure_ascii=False, separators=(",", ":"))
    assert MAX_TEXT_BYTES - 1_000 < len(line.encode()) < MAX_TEXT_BYTES
    # The posting time is all a list page gives; the description clips as usual.
    assert (video["id"], video["publishedTimeText"]) == ("vid1", "3 days ago")
    assert video["text"] == "d" * 2_000 + ELLIPSIS


async def test_its_lifespan_holds_the_shared_pools_open(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("KEYGEN_ACCOUNT_ID", ACCOUNT)  # read at the server's import
    from proprietary.youtube import server

    async with server.lifespan():
        pass


async def test_a_video_s_comments_come_with_their_replies(
    youtube: str, youtube_answers: list[dict], every_stage: None
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
    summary, *lines = result.content[0].text.split("\n")
    assert summary == "3 YouTube comments"
    assert [json.loads(line)["cid"] for line in lines] == ["C1", "R1", "C2"]
    assert progress[-1] == 3


async def test_youtube_refusing_every_request_returns_no_items(
    youtube: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The scraper reads a block as nothing found; it raises no refusal to map."""

    async def refused(
        base_url: str, payload: dict, *, api_key: str | None = None
    ) -> None:
        return None

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
