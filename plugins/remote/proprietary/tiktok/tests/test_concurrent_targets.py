"""Video URLs, comment threads and a profile's blob run concurrently, in input order."""

from __future__ import annotations

import asyncio
import json

import pytest

from proprietary.scraping import sessions
from proprietary.tiktok.flows.profile import iter_profile
from proprietary.tiktok.orchestrator import scrape_tiktok, scrape_tiktok_comments
from proprietary.tiktok.schemas import TikTokScrapeInput
from proprietary.tiktok.session import listing
from proprietary.tiktok.targets.types import TikTokTarget


def _video_page(video_id: str) -> str:
    blob = {
        "__DEFAULT_SCOPE__": {
            "webapp.video-detail": {
                "itemInfo": {
                    "itemStruct": {"id": video_id, "author": {"uniqueId": "a"}}
                }
            }
        }
    }
    return (
        '<script id="__UNIVERSAL_DATA_FOR_REHYDRATION__" type="application/json">'
        f"{json.dumps(blob)}</script>"
    )


class _Tracker:
    def __init__(self) -> None:
        self.running = 0
        self.peak = 0
        self.holders: set[int] = set()

    async def run(self, delay: float) -> None:
        self.running += 1
        self.peak = max(self.peak, self.running)
        holder = sessions.current()
        assert holder is not None  # each worker binds its own proxy session
        self.holders.add(id(holder))
        try:
            await asyncio.sleep(delay)
        finally:
            self.running -= 1


async def test_video_urls_run_concurrently_and_keep_their_order():
    tracker = _Tracker()
    # The first video is the slowest: order must still be the input's.
    delays = {"1": 0.05, "2": 0.01, "3": 0.0}

    async def fetch(url: str) -> str:
        video_id = url.rsplit("/", 1)[1]
        await tracker.run(delays[video_id])
        return _video_page(video_id)

    items = await scrape_tiktok(
        TikTokScrapeInput(
            postURLs=[f"https://www.tiktok.com/@a/video/{i}" for i in ("1", "2", "3")]
        ),
        fetch=fetch,
    )

    assert [i["id"] for i in items] == ["1", "2", "3"]
    assert tracker.peak == 3
    assert len(tracker.holders) == 3


async def test_browser_targets_load_two_at_a_time_in_order():
    running = 0
    peak = 0

    async def fetch(_url: str) -> str:
        return ""

    async def fake_listing(url: str, _count: int) -> list[dict]:
        nonlocal running, peak
        running += 1
        peak = max(peak, running)
        # The first hashtag is the slowest: order must still be the input's.
        await asyncio.sleep(0.05 if url.endswith("/a") else 0.01)
        running -= 1
        return [{"id": url[-1]}]

    items = await scrape_tiktok(
        TikTokScrapeInput(hashtags=["a", "b", "c"], resultsPerPage=1),
        fetch=fetch,
        fetch_listing=fake_listing,
    )

    assert [i["id"] for i in items] == ["a", "b", "c"]
    assert peak == 2


async def test_browser_concurrency_has_a_kill_switch(monkeypatch):
    from proprietary.tiktok import orchestrator

    monkeypatch.setattr(orchestrator, "_BROWSER_CONCURRENCY", 1)
    running = 0

    async def fake_listing(url: str, _count: int) -> list[dict]:
        nonlocal running
        running += 1
        assert running == 1
        await asyncio.sleep(0.01)
        running -= 1
        return [{"id": url[-1]}]

    items = await scrape_tiktok(
        TikTokScrapeInput(hashtags=["a", "b"], resultsPerPage=1),
        fetch_listing=fake_listing,
    )

    assert [i["id"] for i in items] == ["a", "b"]


async def test_user_search_queries_run_concurrently_in_order():
    from proprietary.tiktok.orchestrator import search_tiktok_users

    running = 0
    peak = 0

    async def fetch_users(url: str, _count: int) -> list[dict]:
        nonlocal running, peak
        running += 1
        peak = max(peak, running)
        await asyncio.sleep(0.05 if "q=a" in url else 0.01)
        running -= 1
        return [{"uid": url[-1], "unique_id": url[-1]}]

    items = await search_tiktok_users(["a", "b"], per_query=1, fetch_users=fetch_users)

    assert [i["name"] for i in items] == ["a", "b"]
    assert peak == 2


async def test_the_limit_cancels_video_fetches_still_running():
    started: list[str] = []
    cancelled: list[str] = []

    async def fetch(url: str) -> str:
        video_id = url.rsplit("/", 1)[1]
        started.append(video_id)
        if video_id != "1":
            try:
                await asyncio.sleep(5)
            except asyncio.CancelledError:
                cancelled.append(video_id)
                raise
        return _video_page(video_id)

    items = await asyncio.wait_for(
        scrape_tiktok(
            TikTokScrapeInput(
                postURLs=[f"https://www.tiktok.com/@a/video/{i}" for i in "123"]
            ),
            limit=1,
            fetch=fetch,
        ),
        timeout=2,
    )

    assert [i["id"] for i in items] == ["1"]
    # limit=1 runs one video at a time, so video 3 never starts; one that
    # started after video 1 is cancelled.
    assert "3" not in started
    assert cancelled == started[1:]


async def test_a_profile_s_blob_is_fetched_while_the_feed_loads():
    blob_started = asyncio.Event()

    async def fetch(url: str) -> str:
        blob_started.set()
        return ""

    async def fake_listing(_url: str, _count: int) -> list[dict]:
        # Returns only once the blob GET has started: the two overlap.
        await asyncio.wait_for(blob_started.wait(), timeout=1)
        return [{"id": "v1"}]

    items = await scrape_tiktok(
        TikTokScrapeInput(profiles=["a"], resultsPerPage=2),
        fetch=fetch,
        fetch_listing=fake_listing,
    )

    assert [i["id"] for i in items] == ["v1"]


async def test_comment_threads_run_concurrently_and_keep_their_order():
    tracker = _Tracker()
    delays = {"1": 0.05, "2": 0.0}

    async def fetch_comments(url: str, count: int) -> list[dict]:
        video_id = url.rsplit("/", 1)[1]
        await tracker.run(delays[video_id])
        return [{"cid": f"{video_id}-{n}"} for n in range(count)]

    items = await scrape_tiktok_comments(
        [
            "https://www.tiktok.com/@a/video/1",
            "https://www.tiktok.com/@a/video/2",
        ],
        per_video=2,
        fetch_comments_fn=fetch_comments,
    )

    assert [i["id"] for i in items] == ["1-0", "1-1", "2-0", "2-1"]
    assert tracker.peak == 2


async def test_comment_calls_bind_their_own_browser_slots():
    seen: list[object] = []

    async def fetch_comments(url: str, count: int) -> list[dict]:
        seen.append(listing.BROWSER_SLOTS.get())
        return [{"cid": url}]

    await scrape_tiktok_comments(
        ["https://www.tiktok.com/@a/video/1", "https://www.tiktok.com/@a/video/2"],
        per_video=1,
        fetch_comments_fn=fetch_comments,
    )

    assert isinstance(seen[0], asyncio.Semaphore) and seen[0] is seen[1]
    assert listing.BROWSER_SLOTS.get() is None  # reset once the call ends


async def test_a_failed_listing_awaits_the_cancelled_blob():
    blob_ended: list[str] = []

    async def fetch(url: str) -> str:
        try:
            await asyncio.sleep(5)
        except asyncio.CancelledError:
            blob_ended.append("cancelled")
            raise
        return ""

    async def fetch_listing(_url: str, _count: int) -> list[dict]:
        await asyncio.sleep(0)
        raise RuntimeError("listing failed")

    target = TikTokTarget("profile", "a", "https://www.tiktok.com/@a")
    with pytest.raises(RuntimeError):
        async for _ in iter_profile(
            target, cap=1, fetch=fetch, fetch_listing=fetch_listing
        ):
            pass

    assert blob_ended == ["cancelled"]  # done before the flow returned
