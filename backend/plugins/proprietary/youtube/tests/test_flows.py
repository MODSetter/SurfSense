"""Scraper and comments flows against a fake YouTube that counts requests.

No network: ``post_innertube`` and ``fetch_html`` are replaced, so the fan-out's
holders never open a session.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import pytest

from proprietary.youtube import comments, scraper
from proprietary.youtube.innertube import (
    INNERTUBE_BROWSE_URL,
    INNERTUBE_NEXT_URL,
    INNERTUBE_SEARCH_URL,
)
from proprietary.youtube.schemas import (
    SubtitleTrack,
    YouTubeCommentsInput,
    YouTubeScrapeInput,
)

_FIXTURES = Path(__file__).parent / "fixtures"


def load(name: str) -> dict:
    return json.loads((_FIXTURES / name).read_text(encoding="utf-8"))


def page_html(initial: dict, player: dict | None = None) -> str:
    html = f"<script>var ytInitialData = {json.dumps(initial)};</script>"
    if player is not None:
        html += f"<script>var ytInitialPlayerResponse = {json.dumps(player)};</script>"
    return html


def watch_html(video_id: str) -> str:
    return page_html({}, {"videoDetails": {"videoId": video_id, "title": video_id}})


class FakeYouTube:
    """Answers by URL / payload and records every request in order."""

    def __init__(self) -> None:
        self.posts: list[tuple[str, dict]] = []
        self.gets: list[str] = []
        self.next_pages: dict[str, dict] = {}
        self.browse_pages: dict[str, dict] = {}
        self.html_pages: dict[str, str] = {}
        # url or continuation -> (urls that must be requested first, its event)
        self.gates: dict[str, tuple[set[str], asyncio.Event]] = {}

    async def _gate(self, key: str) -> None:
        for needed, event in self.gates.values():
            if needed <= set(self.gets):
                event.set()
        if key in self.gates:
            await asyncio.wait_for(self.gates[key][1].wait(), 2)

    async def post_innertube(
        self, base_url: str, payload: dict, *, api_key: str | None = None
    ) -> dict | None:
        self.posts.append((base_url, payload))
        key = payload.get("continuation") or payload.get("browseId")
        await self._gate(key)
        if base_url == INNERTUBE_SEARCH_URL:
            return {"contents": [_search_video("srch1")]}
        if base_url == INNERTUBE_NEXT_URL:
            return self.next_pages.get(key or f"video:{payload.get('videoId')}")
        if base_url == INNERTUBE_BROWSE_URL:
            return self.browse_pages.get(key)
        return None

    async def fetch_html(self, url: str, *, cookies: dict | None = None) -> str | None:
        self.gets.append(url)
        await self._gate(url)
        if url in self.html_pages:
            return self.html_pages[url]
        if "/watch?v=" in url:
            return watch_html(url.rsplit("=", 1)[-1])
        return None


def _search_video(video_id: str) -> dict:
    return {"videoRenderer": {"videoId": video_id, "title": {"runs": [{"text": "t"}]}}}


@pytest.fixture
def youtube(monkeypatch: pytest.MonkeyPatch) -> FakeYouTube:
    fake = FakeYouTube()
    monkeypatch.setattr(scraper, "post_innertube", fake.post_innertube)
    monkeypatch.setattr(scraper, "fetch_html", fake.fetch_html)
    monkeypatch.setattr(comments, "fetch_html", fake.fetch_html)
    return fake


# --- scrape -------------------------------------------------------------------


async def test_urls_and_search_queries_both_run(youtube: FakeYouTube) -> None:
    request = YouTubeScrapeInput(
        startUrls=[{"url": "https://www.youtube.com/watch?v=abcdefghijk"}],
        searchQueries=["sourdough"],
        maxResults=1,
    )

    items = await scraper.scrape_youtube(request)

    assert sorted(item["id"] for item in items) == ["abcdefghijk", "srch1"]
    assert [url for url, _ in youtube.posts] == [INNERTUBE_SEARCH_URL]


async def test_a_translation_language_alone_fetches_no_translation(
    youtube: FakeYouTube,
) -> None:
    request = YouTubeScrapeInput(
        searchQueries=["sourdough"], maxResults=1, subtitlesLanguage="fr"
    )

    await scraper.scrape_youtube(request)

    assert [url for url, _ in youtube.posts] == [INNERTUBE_SEARCH_URL]


async def test_subtitles_in_another_language_come_with_a_translation(
    youtube: FakeYouTube, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def no_subtitles(video_id: str, **kwargs: Any) -> list:
        return []

    monkeypatch.setattr(scraper, "fetch_subtitles", no_subtitles)
    youtube.next_pages["video:srch1"] = {
        "videoPrimaryInfoRenderer": {"title": {"runs": [{"text": "Pain au levain"}]}}
    }
    request = YouTubeScrapeInput(
        searchQueries=["sourdough"],
        maxResults=1,
        downloadSubtitles=True,
        subtitlesLanguage="fr",
    )

    items = await scraper.scrape_youtube(request)

    translation = [p for url, p in youtube.posts if url == INNERTUBE_NEXT_URL]
    assert [p["context"]["client"]["hl"] for p in translation] == ["fr"]
    assert items[0]["translatedTitle"] == "Pain au levain"


async def test_a_video_s_subtitles_and_translation_load_alongside_its_page(
    youtube: FakeYouTube, monkeypatch: pytest.MonkeyPatch
) -> None:
    subtitles_started = asyncio.Event()

    async def subtitles(video_id: str, **kwargs: Any) -> list:
        subtitles_started.set()
        return [SubtitleTrack(language="fr", srt="1")]

    monkeypatch.setattr(scraper, "fetch_subtitles", subtitles)
    fetch_page = youtube.fetch_html

    async def slow_page(url: str, **kw: Any) -> str | None:
        # Sequential code would ask for subtitles only after this returns.
        await asyncio.wait_for(subtitles_started.wait(), 1)
        assert [p.get("videoId") for _, p in youtube.posts] == ["abcdefghijk"]
        return await fetch_page(url, **kw)

    monkeypatch.setattr(scraper, "fetch_html", slow_page)
    request = YouTubeScrapeInput(
        startUrls=[{"url": "https://www.youtube.com/watch?v=abcdefghijk"}],
        maxResults=1,
        downloadSubtitles=True,
        subtitlesLanguage="fr",
    )

    items = await scraper.scrape_youtube(request)

    assert items[0]["subtitles"] == [
        {"srtUrl": None, "type": None, "language": "fr", "srt": "1"}
    ]
    assert [url for url, _ in youtube.posts] == [INNERTUBE_NEXT_URL]


async def test_a_page_s_items_fetch_their_subtitles_four_at_a_time_in_order(
    youtube: FakeYouTube, monkeypatch: pytest.MonkeyPatch
) -> None:
    running, most = 0, 0

    async def subtitles(video_id: str, **kwargs: Any) -> list:
        nonlocal running, most
        running += 1
        most = max(most, running)
        await asyncio.sleep(0.02 if video_id != "v0" else 0.05)
        running -= 1
        return [SubtitleTrack(language="en", srt=video_id)]

    async def search(base_url: str, payload: dict, **kw: Any) -> dict:
        return {"contents": [_search_video(f"v{n}") for n in range(6)]}

    monkeypatch.setattr(scraper, "fetch_subtitles", subtitles)
    monkeypatch.setattr(scraper, "post_innertube", search)
    request = YouTubeScrapeInput(
        searchQueries=["sourdough"], maxResults=5, downloadSubtitles=True
    )

    items = await scraper.scrape_youtube(request)

    assert [item["id"] for item in items] == ["v0", "v1", "v2", "v3", "v4"]
    assert [item["order"] for item in items] == [0, 1, 2, 3, 4]
    assert [item["subtitles"][0]["srt"] for item in items] == [
        item["id"] for item in items
    ]
    assert most == 4


async def test_turned_down_a_page_s_items_finalize_one_at_a_time(
    youtube: FakeYouTube, monkeypatch: pytest.MonkeyPatch
) -> None:
    running, most = 0, 0

    async def subtitles(video_id: str, **kwargs: Any) -> list:
        nonlocal running, most
        running += 1
        most = max(most, running)
        await asyncio.sleep(0.01)
        running -= 1
        return [SubtitleTrack(language="en", srt=video_id)]

    async def search(base_url: str, payload: dict, **kw: Any) -> dict:
        return {"contents": [_search_video(f"v{n}") for n in range(3)]}

    monkeypatch.setattr(scraper, "_FINALIZE_CONCURRENCY", 1)
    monkeypatch.setattr(scraper, "fetch_subtitles", subtitles)
    monkeypatch.setattr(scraper, "post_innertube", search)
    request = YouTubeScrapeInput(
        searchQueries=["sourdough"], maxResults=3, downloadSubtitles=True
    )

    items = await scraper.scrape_youtube(request)

    assert [item["id"] for item in items] == ["v0", "v1", "v2"]
    assert most == 1


def _playlist_page(ids: list[str], token: str | None) -> dict:
    page: dict[str, Any] = {
        "contents": [{"lockupViewModel": {"contentId": vid}} for vid in ids]
    }
    if token:
        page["continuationCommand"] = {"token": token}
    return page


async def test_a_playlist_stops_paging_at_the_limit(youtube: FakeYouTube) -> None:
    ids = [f"video{n:06d}" for n in range(5)]
    youtube.browse_pages["VLPL1"] = _playlist_page(ids, "PAGE2")
    youtube.browse_pages["PAGE2"] = _playlist_page(["videoPAGE02"], None)
    request = YouTubeScrapeInput(
        startUrls=[{"url": "https://www.youtube.com/playlist?list=PL1"}], maxResults=3
    )

    items = await scraper.scrape_youtube(request)

    assert sorted(item["id"] for item in items) == ids[:3]
    assert [payload.get("browseId") for _, payload in youtube.posts] == ["VLPL1"]


# The seed fixture's "Popular" sort chip token.
_POPULAR_CHIP = "TOKEN-9"


def _channel_pages(youtube: FakeYouTube) -> None:
    seed = load("channel_mkbhd_seed.json")
    shorts = {
        "items": [
            {
                "shortsLockupViewModel": {
                    "onTap": {
                        "innertubeCommand": {"reelWatchEndpoint": {"videoId": vid}}
                    }
                }
            }
            for vid in ("short000001", "short000002", "short000003")
        ]
    }
    streams = load("channel_mkbhd_latest_chip.json")
    base = "https://www.youtube.com/@mkbhd"
    youtube.html_pages[f"{base}/videos"] = page_html(seed)
    youtube.html_pages[f"{base}/shorts"] = page_html(shorts)
    youtube.html_pages[f"{base}/streams"] = page_html(streams)


async def test_a_channel_fetches_its_tabs_together_and_emits_them_in_order(
    youtube: FakeYouTube,
) -> None:
    _channel_pages(youtube)
    base = "https://www.youtube.com/@mkbhd"
    seed = load("channel_mkbhd_seed.json")
    seed["about"] = {
        "showEngagementPanelEndpoint": {"continuationCommand": {"token": "ABOUT"}}
    }
    youtube.html_pages[f"{base}/videos"] = page_html(seed)
    youtube.browse_pages["ABOUT"] = {"aboutChannelViewModel": {"country": "Iceland"}}
    # About answers only once the shorts and streams seeds have been requested:
    # a sequential flow would time out here.
    youtube.gates["ABOUT"] = ({f"{base}/shorts", f"{base}/streams"}, asyncio.Event())
    request = YouTubeScrapeInput(
        startUrls=[{"url": base}], maxResults=2, maxResultsShorts=2, maxResultStreams=2
    )

    items = await scraper.scrape_youtube(request)

    assert [item["type"] for item in items] == [
        "video",
        "video",
        "shorts",
        "shorts",
        "stream",
        "stream",
    ]
    assert {item["channelLocation"] for item in items} == {"Iceland"}
    # The videos seed comes first: the other tabs reuse its connection.
    assert youtube.gets[0] == f"{base}/videos"
    # The default sort reads the seed's own first page: no Latest-chip browse.
    assert [payload.get("continuation") for _, payload in youtube.posts] == ["ABOUT"]


async def test_a_channel_sorted_by_popularity_uses_its_chip(
    youtube: FakeYouTube,
) -> None:
    _channel_pages(youtube)
    youtube.browse_pages[_POPULAR_CHIP] = load("channel_mkbhd_latest_chip.json")
    request = YouTubeScrapeInput(
        startUrls=[{"url": "https://www.youtube.com/@mkbhd"}],
        maxResults=1,
        sortVideosBy="POPULAR",
    )

    items = await scraper.scrape_youtube(request)

    assert [item["type"] for item in items] == ["video"]
    assert [payload.get("continuation") for _, payload in youtube.posts] == [
        _POPULAR_CHIP
    ]


async def test_a_channel_skips_the_tabs_capped_at_zero(youtube: FakeYouTube) -> None:
    _channel_pages(youtube)
    request = YouTubeScrapeInput(
        startUrls=[{"url": "https://www.youtube.com/@mkbhd"}], maxResults=1
    )

    items = await scraper.scrape_youtube(request)

    assert len(items) == 1
    assert youtube.gets == ["https://www.youtube.com/@mkbhd/videos"]


# --- comments -----------------------------------------------------------------


def _comment_pages(youtube: FakeYouTube) -> None:
    youtube.next_pages["video:jNQXAC9IVRw"] = load("next_video_jNQXAC9IVRw.json")
    youtube.next_pages["TOKEN-1"] = load("comments_page_jNQXAC9IVRw.json")
    replies = load("replies_page_jNQXAC9IVRw.json")
    youtube.next_pages["TOKEN-3"] = replies  # the first thread (985 replies)
    youtube.next_pages["TOKEN-7"] = replies  # its "Show more replies" page


def _comments_request(limit: int) -> YouTubeCommentsInput:
    return YouTubeCommentsInput(
        startUrls=[{"url": "https://www.youtube.com/watch?v=jNQXAC9IVRw"}],
        maxComments=limit,
        sortCommentsBy="TOP_COMMENTS",
    )


def _next_calls(youtube: FakeYouTube) -> list[str | None]:
    return [
        payload.get("continuation") or payload.get("videoId")
        for _, payload in youtube.posts
    ]


async def test_comments_fetch_only_the_reply_threads_the_budget_reaches(
    youtube: FakeYouTube,
) -> None:
    _comment_pages(youtube)

    items = await comments.scrape_comments(_comments_request(5))

    assert [item["replyToCid"] is None for item in items] == [True] + [False] * 4
    assert items[0]["title"] == "Me at the zoo"
    # Seed by video id, the section, and one reply page: no watch HTML, and no
    # prefetch of threads the budget cannot reach.
    assert _next_calls(youtube) == ["jNQXAC9IVRw", "TOKEN-1", "TOKEN-3"]
    assert youtube.gets == []


async def test_a_long_reply_thread_pages_up_to_the_budget(
    youtube: FakeYouTube,
) -> None:
    _comment_pages(youtube)

    items = await comments.scrape_comments(_comments_request(15))

    first = items[0]["cid"]
    assert [item["replyToCid"] for item in items[1:]] == [first] * 14
    assert _next_calls(youtube) == ["jNQXAC9IVRw", "TOKEN-1", "TOKEN-3", "TOKEN-7"]


# Estimated reply counts on the comments page of the test below.
_ESTIMATES = {"C1": "5", "C2": "20"}


def _thread_page(cids: list[str], token: str | None, *, level: int = 1) -> dict:
    mutations = [
        {
            "payload": {
                "commentEntityPayload": {
                    "properties": {"commentId": cid, "replyLevel": level},
                    "toolbar": {"replyCount": _ESTIMATES.get(cid, "")},
                }
            }
        }
        for cid in cids
    ]
    items: list[dict] = [
        {
            "commentThreadRenderer": {
                "commentViewModel": {"commentViewModel": {"commentId": cid}},
                "replies": {
                    "continuationItemRenderer": {
                        "continuationEndpoint": {
                            "continuationCommand": {"token": f"T-{cid}"}
                        }
                    }
                },
            }
        }
        for cid in cids
        if level == 0
    ]
    if token:
        items.append(
            {
                "continuationItemRenderer": {
                    "button": {
                        "buttonRenderer": {
                            "command": {"continuationCommand": {"token": token}}
                        }
                    }
                }
            }
        )
    return {
        "frameworkUpdates": {"entityBatchUpdate": {"mutations": mutations}},
        "onResponseReceivedEndpoints": [
            {"appendContinuationItemsAction": {"continuationItems": items}}
        ],
    }


async def test_a_thread_past_its_estimate_is_fetched_on_while_budget_lasts(
    youtube: FakeYouTube,
) -> None:
    """C1 claims 5 replies but has 1, so C2 gets more budget than planned."""
    youtube.next_pages["video:abcdefghijk"] = load("next_video_jNQXAC9IVRw.json")
    youtube.next_pages["TOKEN-1"] = _thread_page(["C1", "C2"], None, level=0)
    youtube.next_pages["T-C1"] = _thread_page(["R1"], None)
    youtube.next_pages["T-C2"] = _thread_page(["S1", "S2"], "P2")
    youtube.next_pages["P2"] = _thread_page(["S3", "S4"], "P3")
    youtube.next_pages["P3"] = _thread_page(["S5", "S6"], None)
    request = YouTubeCommentsInput(
        startUrls=[{"url": "https://www.youtube.com/watch?v=abcdefghijk"}],
        maxComments=10,
        sortCommentsBy="TOP_COMMENTS",
    )

    items = await comments.scrape_comments(request)

    assert [item["cid"] for item in items] == [
        "C1",
        "R1",
        "C2",
        "S1",
        "S2",
        "S3",
        "S4",
        "S5",
        "S6",
    ]
    assert _next_calls(youtube)[-1] == "P3"


async def test_the_watch_page_seed_is_one_switch_away(
    youtube: FakeYouTube, monkeypatch: pytest.MonkeyPatch
) -> None:
    """YOUTUBE_COMMENTS_NEXT_SEED=0 seeds from the watch page, as before."""
    monkeypatch.setattr(comments, "_NEXT_SEED", False)
    _comment_pages(youtube)
    initial = load("next_video_jNQXAC9IVRw.json")
    player = {"videoDetails": {"videoId": "jNQXAC9IVRw", "title": "Me at the zoo"}}
    youtube.html_pages["https://www.youtube.com/watch?v=jNQXAC9IVRw"] = page_html(
        initial, player
    )

    items = await comments.scrape_comments(_comments_request(2))

    assert len(items) == 2
    assert items[0]["title"] == "Me at the zoo"
    assert youtube.gets == ["https://www.youtube.com/watch?v=jNQXAC9IVRw"]
    assert _next_calls(youtube) == ["TOKEN-1", "TOKEN-3"]


async def test_a_next_answer_without_the_comments_section_asks_the_watch_page(
    youtube: FakeYouTube,
) -> None:
    """A /next layout we do not read is not comments turned off."""
    _comment_pages(youtube)
    youtube.next_pages["video:jNQXAC9IVRw"] = {"contents": {}}
    initial = load("next_video_jNQXAC9IVRw.json")
    player = {"videoDetails": {"videoId": "jNQXAC9IVRw", "title": "Me at the zoo"}}
    youtube.html_pages["https://www.youtube.com/watch?v=jNQXAC9IVRw"] = page_html(
        initial, player
    )

    items = await comments.scrape_comments(_comments_request(2))

    assert len(items) == 2
    assert items[0]["title"] == "Me at the zoo"
    assert youtube.gets == ["https://www.youtube.com/watch?v=jNQXAC9IVRw"]
    assert _next_calls(youtube) == ["jNQXAC9IVRw", "TOKEN-1", "TOKEN-3"]
