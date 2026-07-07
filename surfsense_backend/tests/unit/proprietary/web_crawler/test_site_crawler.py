"""``crawl_site`` BFS behavior: depth, same-site scope, dedupe, and page caps.

Boundary mocked: the engine (a fake ``crawl_url`` serving a canned link graph).
NOT mocked: the frontier/depth/dedupe/scope logic under test.
"""

from __future__ import annotations

import pytest

from app.proprietary.web_crawler import CrawlOutcome, CrawlOutcomeStatus
from app.proprietary.web_crawler.site_crawler import crawl_site

pytestmark = pytest.mark.unit

_SUCCESS = CrawlOutcomeStatus.SUCCESS
_FAILED = CrawlOutcomeStatus.FAILED


class _FakeEngine:
    """Serves a canned ``(status, links)`` per URL and records fetch order."""

    def __init__(self, graph: dict[str, tuple[CrawlOutcomeStatus, list[str]]]):
        self._graph = graph
        self.calls: list[str] = []

    async def crawl_url(self, url: str) -> CrawlOutcome:
        self.calls.append(url)
        status, links = self._graph.get(url, (_FAILED, []))
        if status is _SUCCESS:
            return CrawlOutcome(
                status=_SUCCESS,
                result={
                    "content": f"C:{url}",
                    "metadata": {"title": url},
                    "links": links,
                },
            )
        return CrawlOutcome(status=status, error="boom")


async def test_depth_zero_fetches_only_the_seed() -> None:
    engine = _FakeEngine({"https://e.com/": (_SUCCESS, ["https://e.com/a"])})

    pages = await crawl_site(
        engine, ["https://e.com/"], max_crawl_depth=0, max_crawl_pages=10
    )

    assert engine.calls == ["https://e.com/"]
    assert len(pages) == 1
    assert pages[0].depth == 0
    assert pages[0].referrer is None
    assert pages[0].content == "C:https://e.com/"


async def test_depth_one_follows_same_site_links_only() -> None:
    engine = _FakeEngine(
        {
            "https://e.com/": (
                _SUCCESS,
                ["https://e.com/a", "https://e.com/b", "https://other.com/x"],
            ),
            "https://e.com/a": (_SUCCESS, []),
            "https://e.com/b": (_SUCCESS, []),
        }
    )

    pages = await crawl_site(
        engine, ["https://e.com/"], max_crawl_depth=1, max_crawl_pages=10
    )

    assert set(engine.calls) == {
        "https://e.com/",
        "https://e.com/a",
        "https://e.com/b",
    }
    depths = {page.url: page.depth for page in pages}
    assert depths["https://e.com/a"] == 1
    referrers = {page.url: page.referrer for page in pages}
    assert referrers["https://e.com/a"] == "https://e.com/"


async def test_depth_caps_further_recursion() -> None:
    engine = _FakeEngine(
        {
            "https://e.com/": (_SUCCESS, ["https://e.com/a"]),
            "https://e.com/a": (_SUCCESS, ["https://e.com/b"]),
            "https://e.com/b": (_SUCCESS, []),
        }
    )

    pages = await crawl_site(
        engine, ["https://e.com/"], max_crawl_depth=1, max_crawl_pages=10
    )

    # depth 1 reaches /a but must NOT descend to /b (depth 2).
    assert set(engine.calls) == {"https://e.com/", "https://e.com/a"}
    assert all(page.url != "https://e.com/b" for page in pages)


async def test_max_pages_caps_total_fetches() -> None:
    graph: dict[str, tuple[CrawlOutcomeStatus, list[str]]] = {
        "https://e.com/": (_SUCCESS, [f"https://e.com/{i}" for i in range(10)])
    }
    for i in range(10):
        graph[f"https://e.com/{i}"] = (_SUCCESS, [])
    engine = _FakeEngine(graph)

    pages = await crawl_site(
        engine, ["https://e.com/"], max_crawl_depth=1, max_crawl_pages=3
    )

    assert len(pages) == 3
    assert len(engine.calls) == 3


async def test_dedupes_on_canonical_url() -> None:
    engine = _FakeEngine(
        {
            "https://e.com/": (
                _SUCCESS,
                ["https://e.com/a", "https://e.com/a#frag", "https://e.com/a?"],
            ),
            "https://e.com/a": (_SUCCESS, ["https://e.com/"]),  # links back to seed
        }
    )

    await crawl_site(engine, ["https://e.com/"], max_crawl_depth=3, max_crawl_pages=10)

    assert engine.calls.count("https://e.com/a") == 1
    assert engine.calls.count("https://e.com/") == 1


async def test_failed_page_is_recorded_and_not_expanded() -> None:
    engine = _FakeEngine({"https://e.com/": (_FAILED, [])})

    pages = await crawl_site(
        engine, ["https://e.com/"], max_crawl_depth=2, max_crawl_pages=10
    )

    assert len(pages) == 1
    assert pages[0].status is _FAILED
    assert pages[0].content is None
    assert pages[0].error == "boom"


async def test_multiple_seeds_are_all_entry_points() -> None:
    engine = _FakeEngine(
        {
            "https://a.com/": (_SUCCESS, []),
            "https://b.com/": (_SUCCESS, []),
        }
    )

    pages = await crawl_site(
        engine,
        ["https://a.com/", "https://b.com/"],
        max_crawl_depth=0,
        max_crawl_pages=10,
    )

    assert {page.url for page in pages} == {"https://a.com/", "https://b.com/"}
    assert all(page.depth == 0 for page in pages)
