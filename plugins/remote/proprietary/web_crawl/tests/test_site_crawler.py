"""``crawl_site`` BFS behavior: depth, same-site scope, dedupe, page caps and concurrency.

Boundary mocked: the engine (a fake ``crawl_url`` serving a canned link graph).
NOT mocked: the frontier/depth/dedupe/scope logic under test.
"""

from __future__ import annotations

import asyncio
import random

import pytest

from proprietary.web_crawl import CrawlOutcome, CrawlOutcomeStatus
from proprietary.web_crawl.connector import PageLimits
from proprietary.web_crawl.site_crawler import crawl_site

_SUCCESS = CrawlOutcomeStatus.SUCCESS
_FAILED = CrawlOutcomeStatus.FAILED


class _FakeEngine:
    """Serves a canned ``(status, links)`` per URL and records fetch order."""

    def __init__(self, graph: dict[str, tuple[CrawlOutcomeStatus, list[str]]]):
        self._graph = graph
        self.calls: list[str] = []

    async def crawl_url(self, url: str, *_limits) -> CrawlOutcome:
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


class _RedirectingEngine(_FakeEngine):
    """Like ``_FakeEngine``, but some URLs redirect: ``loaded_url`` differs."""

    def __init__(self, graph, redirects: dict[str, str]):
        super().__init__(graph)
        self._redirects = redirects

    async def crawl_url(self, url: str, *_limits) -> CrawlOutcome:
        target = self._redirects.get(url, url)
        outcome = await super().crawl_url(target)
        self.calls[-1] = url
        if outcome.result is not None:
            outcome.result["loaded_url"] = target
        return outcome


async def test_a_redirect_onto_a_crawled_page_is_dropped() -> None:
    """c08: the domain root (302 to /en/latest/) came back as a second copy of
    the start page, and its links were followed again."""
    engine = _RedirectingEngine(
        {
            "https://e.com/en/latest/": (
                _SUCCESS,
                ["https://e.com", "https://e.com/en/latest/api/"],
            ),
            "https://e.com/en/latest/api/": (_SUCCESS, []),
        },
        redirects={"https://e.com": "https://e.com/en/latest/"},
    )

    pages = await crawl_site(
        engine, ["https://e.com/en/latest/"], max_crawl_depth=2, max_crawl_pages=10
    )

    assert [page.url for page in pages] == [
        "https://e.com/en/latest/",
        "https://e.com/en/latest/api/",
    ]
    assert engine.calls.count("https://e.com") == 1


async def test_a_link_to_a_loaded_url_is_not_fetched_again() -> None:
    """A start URL that redirects: links to where it landed are already crawled."""
    engine = _RedirectingEngine(
        {
            "https://e.com/home": (
                _SUCCESS,
                ["https://e.com/home#top", "https://e.com/about"],
            ),
            "https://e.com/about": (_SUCCESS, []),
        },
        redirects={"https://e.com/": "https://e.com/home"},
    )

    pages = await crawl_site(
        engine, ["https://e.com/"], max_crawl_depth=1, max_crawl_pages=10
    )

    assert engine.calls == ["https://e.com/", "https://e.com/about"]
    assert pages[0].loaded_url == "https://e.com/home"


async def test_limits_reach_every_fetch() -> None:
    seen: list[object] = []

    class _Engine(_FakeEngine):
        async def crawl_url(self, url: str, *limits) -> CrawlOutcome:
            seen.extend(limits)
            return await super().crawl_url(url)

    limits = PageLimits(max_length=10, max_links=3)
    await crawl_site(
        _Engine({"https://e.com/": (_SUCCESS, [])}),
        ["https://e.com/"],
        max_crawl_depth=0,
        max_crawl_pages=1,
        limits=limits,
    )
    # The second argument is the tier hook (see the progress test below).
    assert seen[0] is limits


class _TimedEngine(_FakeEngine):
    """Each fetch takes a while; records how many run at once, overall and per host."""

    def __init__(self, graph, *, delay=lambda _url: 0.01, status=None):
        super().__init__(graph)
        self._delay = delay
        self._status = status or {}
        self.active: dict[str, int] = {}
        self.peak: dict[str, int] = {}
        self.peak_total = 0
        self.started_with: list[int] = []

    async def crawl_url(self, url: str, *_args) -> CrawlOutcome:
        host = url.split("/")[2]
        self.started_with.append(sum(self.active.values()))
        self.active[host] = self.active.get(host, 0) + 1
        self.peak[host] = max(self.peak.get(host, 0), self.active[host])
        self.peak_total = max(self.peak_total, sum(self.active.values()))
        try:
            await asyncio.sleep(self._delay(url))
        finally:
            self.active[host] -= 1
        if url in self._status:
            self.calls.append(url)
            return CrawlOutcome(
                status=_FAILED, error=f"Scrapling static: HTTP {self._status[url]}"
            )
        return await super().crawl_url(url)


def _site(host: str, count: int) -> dict[str, tuple[CrawlOutcomeStatus, list[str]]]:
    links = [f"https://{host}/{i}" for i in range(count)]
    graph = {f"https://{host}/": (_SUCCESS, links)}
    graph.update({link: (_SUCCESS, []) for link in links})
    return graph


async def test_a_level_is_fetched_side_by_side_but_kept_in_order() -> None:
    """c08: ten pages took the sum of their fetches, one after another."""
    rng = random.Random(7)
    engine = _TimedEngine(_site("e.com", 12), delay=lambda _u: rng.uniform(0, 0.03))

    pages = await crawl_site(
        engine, ["https://e.com/"], max_crawl_depth=1, max_crawl_pages=10
    )

    assert [page.url for page in pages] == ["https://e.com/"] + [
        f"https://e.com/{i}" for i in range(9)
    ]
    assert len(engine.calls) == 10
    assert engine.peak["e.com"] == 4  # the per-host cap


async def test_hosts_share_the_overall_cap() -> None:
    graph = {}
    seeds = []
    for host in ("a.com", "b.com", "c.com"):
        for i in range(4):
            seeds.append(f"https://{host}/{i}")
            graph[f"https://{host}/{i}"] = (_SUCCESS, [])
    engine = _TimedEngine(graph, delay=lambda _u: 0.03)

    pages = await crawl_site(engine, seeds, max_crawl_depth=0, max_crawl_pages=20)

    assert [page.url for page in pages] == seeds
    assert engine.peak_total == 6


async def test_one_at_a_time_when_the_switch_says_so(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("WEB_CRAWL_CONCURRENCY", "1")
    engine = _TimedEngine(_site("e.com", 5))

    pages = await crawl_site(
        engine, ["https://e.com/"], max_crawl_depth=1, max_crawl_pages=10
    )

    assert len(pages) == 6
    assert engine.peak_total == 1


async def test_a_host_that_pushes_back_gets_half_the_slots() -> None:
    seeds = [f"https://e.com/{i}" for i in range(9)]
    graph = {url: (_SUCCESS, []) for url in seeds}
    # The first fetch answers 429 at once; the other three in flight are slow,
    # so every later fetch starts after the halving.
    engine = _TimedEngine(
        graph,
        delay=lambda u: 0 if u == seeds[0] else 0.03,
        status={seeds[0]: 429},
    )

    pages = await crawl_site(engine, seeds, max_crawl_depth=0, max_crawl_pages=20)

    assert len(pages) == 9
    assert engine.started_with[:4] == [0, 1, 2, 3]
    # 2 slots now: a later fetch starts with at most one other in flight.
    assert max(engine.started_with[4:]) <= 1


async def test_a_dropped_duplicate_frees_its_page_for_the_next_url() -> None:
    """The budget bounds pages kept: a redirect duplicate does not use one up."""
    engine = _RedirectingEngine(
        {
            "https://e.com/a": (_SUCCESS, ["https://e.com/b", "https://e.com/c"]),
            "https://e.com/c": (_SUCCESS, []),
        },
        redirects={"https://e.com/b": "https://e.com/a"},
    )

    pages = await crawl_site(
        engine, ["https://e.com/a"], max_crawl_depth=1, max_crawl_pages=2
    )

    assert [page.url for page in pages] == ["https://e.com/a", "https://e.com/c"]
    assert engine.calls == ["https://e.com/a", "https://e.com/b", "https://e.com/c"]


async def test_a_start_url_is_kept_even_when_it_lands_on_another() -> None:
    """Two pages asked for by name: both come back, though one redirects onto the other."""
    engine = _RedirectingEngine(
        {"https://e.com/b": (_SUCCESS, [])},
        redirects={"https://e.com/a": "https://e.com/b"},
    )

    pages = await crawl_site(
        engine,
        ["https://e.com/a", "https://e.com/b"],
        max_crawl_depth=0,
        max_crawl_pages=10,
    )

    assert [page.url for page in pages] == ["https://e.com/a", "https://e.com/b"]
    assert pages[0].loaded_url == "https://e.com/b"


async def test_a_page_s_links_are_filtered_off_the_loop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A 7 MB changelog has 13,000 links: canonicalizing them held the loop 0.3 s."""
    import threading

    from proprietary.web_crawl import site_crawler

    threads: list[int] = []
    original = site_crawler._followable

    def recording(links, link_extractor):
        threads.append(threading.get_ident())
        return original(links, link_extractor)

    monkeypatch.setattr(site_crawler, "_followable", recording)
    engine = _FakeEngine(
        {
            "https://e.com/": (_SUCCESS, ["https://e.com/a", "https://x.com/"]),
            "https://e.com/a": (_SUCCESS, []),
        }
    )

    pages = await crawl_site(
        engine, ["https://e.com/"], max_crawl_depth=1, max_crawl_pages=10
    )

    assert [page.url for page in pages] == ["https://e.com/", "https://e.com/a"]
    assert threads and threading.get_ident() not in threads


async def test_a_failing_fetch_does_not_end_the_crawl() -> None:
    class _Raising(_FakeEngine):
        async def crawl_url(self, url: str, *_args) -> CrawlOutcome:
            if url.endswith("/bad"):
                raise RuntimeError("socket gone")
            return await super().crawl_url(url)

    engine = _Raising({"https://e.com/ok": (_SUCCESS, [])})

    pages = await crawl_site(
        engine,
        ["https://e.com/bad", "https://e.com/ok"],
        max_crawl_depth=0,
        max_crawl_pages=5,
    )

    assert [(page.url, page.status) for page in pages] == [
        ("https://e.com/bad", _FAILED),
        ("https://e.com/ok", _SUCCESS),
    ]
    assert pages[0].error == "socket gone"


async def test_each_fetch_reports_its_tiers_and_each_page_its_count() -> None:
    class _Tiered(_FakeEngine):
        async def crawl_url(self, url: str, _limits, on_tier) -> CrawlOutcome:
            await on_tier("static fetch")
            return await super().crawl_url(url)

    stages: list[str] = []
    counts: list[int] = []

    async def on_stage(message: str) -> None:
        stages.append(message)

    async def on_item(count: int) -> None:
        counts.append(count)

    await crawl_site(
        _Tiered({"https://e.com/": (_SUCCESS, ["https://e.com/a"])}),
        ["https://e.com/"],
        max_crawl_depth=1,
        max_crawl_pages=5,
        on_item=on_item,
        on_stage=on_stage,
    )

    assert stages == ["https://e.com/: static fetch", "https://e.com/a: static fetch"]
    assert counts == [1, 2]


async def test_stopping_the_crawl_cancels_every_fetch_in_flight() -> None:
    engine = _TimedEngine(_site("e.com", 8), delay=lambda _u: 5)
    task = asyncio.create_task(
        crawl_site(
            engine,
            ["https://e.com/0", "https://e.com/1"],
            max_crawl_depth=0,
            max_crawl_pages=5,
        )
    )
    await asyncio.sleep(0.05)
    assert sum(engine.active.values()) == 2
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert sum(engine.active.values()) == 0
