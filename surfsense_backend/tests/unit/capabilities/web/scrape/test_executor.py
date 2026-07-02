"""`web.scrape` executor behavior: URLs in → cleaned rows out.

Boundary mocked: the crawler (injected fake). NOT mocked: the executor's own
CrawlOutcome → ScrapeRow mapping.
"""

from __future__ import annotations

import pytest

from app.capabilities.web.scrape.executor import build_scrape_executor
from app.capabilities.web.scrape.schemas import ScrapeInput, ScrapeOutput
from app.proprietary.web_crawler import CrawlOutcome, CrawlOutcomeStatus

pytestmark = pytest.mark.unit


class _FakeCrawler:
    """Stand-in for WebCrawlerConnector: serves a canned outcome per URL."""

    def __init__(self, outcomes: dict[str, CrawlOutcome]):
        self._outcomes = outcomes
        self.calls: list[str] = []

    async def crawl_url(self, url: str) -> CrawlOutcome:
        self.calls.append(url)
        return self._outcomes[url]


def _success(content: str, metadata: dict[str, str]) -> CrawlOutcome:
    return CrawlOutcome(
        status=CrawlOutcomeStatus.SUCCESS,
        result={
            "content": content,
            "metadata": metadata,
            "crawler_type": "scrapling-static",
        },
    )


async def test_scrape_returns_one_cleaned_row_for_a_successful_url():
    url = "https://example.com"
    crawler = _FakeCrawler({url: _success("# Hello", {"title": "Hello"})})
    execute = build_scrape_executor(engine=crawler)

    out = await execute(ScrapeInput(urls=[url]))

    assert isinstance(out, ScrapeOutput)
    assert len(out.rows) == 1
    row = out.rows[0]
    assert row.url == url
    assert row.status == "success"
    assert row.content == "# Hello"
    assert row.metadata == {"title": "Hello"}


async def test_scrape_returns_one_row_per_url_in_input_order():
    a, b, c = "https://a.com", "https://b.com", "https://c.com"
    crawler = _FakeCrawler(
        {
            a: _success("A", {"title": "A"}),
            b: _success("B", {"title": "B"}),
            c: _success("C", {"title": "C"}),
        }
    )
    execute = build_scrape_executor(engine=crawler)

    out = await execute(ScrapeInput(urls=[a, b, c]))

    assert [row.url for row in out.rows] == [a, b, c]
    assert [row.content for row in out.rows] == ["A", "B", "C"]


async def test_content_longer_than_max_length_is_truncated():
    url = "https://long.com"
    crawler = _FakeCrawler({url: _success("A" * 100, {"title": "Long"})})
    execute = build_scrape_executor(engine=crawler)

    out = await execute(ScrapeInput(urls=[url], max_length=10))

    assert out.rows[0].content == "A" * 10


async def test_content_within_max_length_is_untouched():
    url = "https://short.com"
    crawler = _FakeCrawler({url: _success("hello", {"title": "Short"})})
    execute = build_scrape_executor(engine=crawler)

    out = await execute(ScrapeInput(urls=[url], max_length=10))

    assert out.rows[0].content == "hello"


async def test_scrape_surfaces_total_captcha_attempts_for_billing():
    ok, blocked = "https://ok.com", "https://blocked.com"
    crawler = _FakeCrawler(
        {
            ok: CrawlOutcome(
                status=CrawlOutcomeStatus.SUCCESS,
                result={"content": "OK", "metadata": {}},
                captcha_attempts=2,
                captcha_solved=True,
            ),
            blocked: CrawlOutcome(
                status=CrawlOutcomeStatus.FAILED,
                error="blocked",
                captcha_attempts=1,
                captcha_solved=False,
            ),
        }
    )
    execute = build_scrape_executor(engine=crawler)

    out = await execute(ScrapeInput(urls=[ok, blocked]))

    # Attempts bill even when the crawl ultimately failed (Phase 3d).
    assert out.captcha_attempts == 3
    assert out.captcha_solved == 1


async def test_partial_failure_keeps_the_batch_and_labels_each_url():
    ok, empty, failed = "https://ok.com", "https://empty.com", "https://failed.com"
    crawler = _FakeCrawler(
        {
            ok: _success("OK", {"title": "OK"}),
            empty: CrawlOutcome(status=CrawlOutcomeStatus.EMPTY, error="no content"),
            failed: CrawlOutcome(status=CrawlOutcomeStatus.FAILED, error="blocked"),
        }
    )
    execute = build_scrape_executor(engine=crawler)

    out = await execute(ScrapeInput(urls=[ok, empty, failed]))

    by_url = {row.url: row for row in out.rows}
    assert {u: r.status for u, r in by_url.items()} == {
        ok: "success",
        empty: "empty",
        failed: "failed",
    }
    assert by_url[failed].content is None
    assert by_url[failed].error == "blocked"
