"""A call's pages render side by side and still come out in input order (GS-4).

Two queries used to cost the sum of their renders (31.1 s warm). Google is
faked at the render seam, ``fetch_serp_html``; the scheduling, the paging stop
and the limit are the real ones.
"""

import asyncio

import pytest

from proprietary.google_search import fetch, scraper
from proprietary.google_search.schemas import GoogleSearchScrapeInput


def _serp(term: str, results: int = 2) -> str:
    blocks = "".join(
        f'<div class="tF2Cxc"><a href="https://{term}.example/{i}"><h3>{term} {i}</h3>'
        f"</a></div>"
        for i in range(results)
    )
    return f'<html><body><div id="rso">{blocks}</div></body></html>'


def _term(url: str) -> str:
    return url.split("q=", 1)[1].split("&", 1)[0]


def _page(url: str) -> int:
    start = url.split("start=", 1)[1].split("&", 1)[0] if "start=" in url else "0"
    return int(start) // 10 + 1


@pytest.fixture(autouse=True)
def _one_warm_ip(monkeypatch):
    monkeypatch.setattr(fetch, "_pool", {"p1": 0.0})  # render_slots() == 2


async def test_two_queries_render_at_once_and_keep_their_order(monkeypatch):
    started: list[str] = []
    both = asyncio.Event()

    async def fetch_serp_html(url, *, mobile=False):
        started.append(_term(url))
        if len(started) == 2:
            both.set()
        await asyncio.wait_for(both.wait(), 2)  # times out when run one by one
        if _term(url) == "pie":
            await asyncio.sleep(0.05)  # the first query finishes last
        return _serp(_term(url))

    monkeypatch.setattr(scraper, "fetch_serp_html", fetch_serp_html)

    items = await scraper.scrape_serps(GoogleSearchScrapeInput(queries="pie\ncake"))

    assert [item["searchQuery"]["term"] for item in items] == ["pie", "cake"]
    assert started == ["pie", "cake"]


async def test_the_kill_switch_renders_one_page_at_a_time(monkeypatch):
    monkeypatch.setattr(scraper, "_PARALLEL_PAGES", False)
    inflight = 0
    most = 0

    async def fetch_serp_html(url, *, mobile=False):
        nonlocal inflight, most
        inflight += 1
        most = max(most, inflight)
        await asyncio.sleep(0.01)
        inflight -= 1
        return _serp(_term(url))

    monkeypatch.setattr(scraper, "fetch_serp_html", fetch_serp_html)

    items = await scraper.scrape_serps(
        GoogleSearchScrapeInput(queries="pie\ncake\ntart")
    )

    assert len(items) == 3 and most == 1


async def test_pages_past_a_term_s_last_one_are_dropped(monkeypatch):
    """Page 2 is empty, so the term ends there: page 3, rendered ahead, is
    dropped, and the next query's page still comes after page 2."""
    rendered: list[tuple[str, int]] = []

    async def fetch_serp_html(url, *, mobile=False):
        term, page = _term(url), _page(url)
        rendered.append((term, page))
        if term == "pie" and page == 1:
            await asyncio.sleep(0.05)  # pages 2 and 3 land first
        return _serp(term, results=0 if (term, page) == ("pie", 2) else 2)

    monkeypatch.setattr(scraper, "fetch_serp_html", fetch_serp_html)

    items = await scraper.scrape_serps(
        GoogleSearchScrapeInput(queries="pie\ncake", maxPagesPerQuery=3)
    )

    pages = [(i["searchQuery"]["term"], i["searchQuery"]["page"]) for i in items]
    assert pages == [("pie", 1), ("pie", 2), ("cake", 1), ("cake", 2), ("cake", 3)]
    # Ahead of the head by less than the concurrency (2), never the whole list.
    assert rendered[:2] == [("pie", 1), ("pie", 2)]


async def test_one_by_one_a_page_past_the_end_is_never_rendered(monkeypatch):
    monkeypatch.setattr(scraper, "_PARALLEL_PAGES", False)
    rendered: list[int] = []

    async def fetch_serp_html(url, *, mobile=False):
        rendered.append(_page(url))
        return _serp("pie", results=0 if _page(url) == 2 else 2)

    monkeypatch.setattr(scraper, "fetch_serp_html", fetch_serp_html)

    items = await scraper.scrape_serps(
        GoogleSearchScrapeInput(queries="pie", maxPagesPerQuery=4)
    )

    assert [i["searchQuery"]["page"] for i in items] == [1, 2]
    assert rendered == [1, 2]


async def test_a_term_whose_page_fails_stops_there(monkeypatch):
    async def fetch_serp_html(url, *, mobile=False):
        return None if _page(url) == 1 else _serp("pie")

    monkeypatch.setattr(scraper, "fetch_serp_html", fetch_serp_html)
    monkeypatch.setattr(scraper.searxng, "enabled", lambda: False)

    items = await scraper.scrape_serps(
        GoogleSearchScrapeInput(queries="pie", maxPagesPerQuery=2)
    )

    assert items == []


async def test_reaching_the_limit_cancels_the_pages_still_rendering(monkeypatch):
    cancelled: list[str] = []

    async def fetch_serp_html(url, *, mobile=False):
        if _term(url) == "cake":
            try:
                await asyncio.sleep(10)
            except asyncio.CancelledError:
                cancelled.append("cake")
                raise
        return _serp(_term(url))

    monkeypatch.setattr(scraper, "fetch_serp_html", fetch_serp_html)

    items = await asyncio.wait_for(
        scraper.scrape_serps(GoogleSearchScrapeInput(queries="pie\ncake"), limit=1),
        2,
    )

    assert [i["searchQuery"]["term"] for i in items] == ["pie"]
    assert cancelled == ["cake"]


async def test_on_a_cold_pool_the_first_page_warms_an_ip_before_the_rest(monkeypatch):
    """Two queries on a cold pool each vetted a fresh IP and both paid a /sorry
    solve; the first page now renders alone, and the rest share its IP."""
    pool: dict[str, float] = {}
    monkeypatch.setattr(fetch, "_pool", pool)
    events: list[str] = []

    async def fetch_serp_html(url, *, mobile=False):
        events.append(f"start {_term(url)}")
        await asyncio.sleep(0.01)
        pool["p1"] = 0.0  # the render warmed its IP
        events.append(f"end {_term(url)}")
        return _serp(_term(url))

    monkeypatch.setattr(scraper, "fetch_serp_html", fetch_serp_html)

    items = await scraper.scrape_serps(
        GoogleSearchScrapeInput(queries="pie\ncake\ntart")
    )

    assert [i["searchQuery"]["term"] for i in items] == ["pie", "cake", "tart"]
    assert events[:2] == ["start pie", "end pie"]
    # Then two at once on the warm IP.
    assert events[2:4] == ["start cake", "start tart"]
