"""``web.crawl`` executor behavior: CrawlPage list → typed CrawlOutput items.

Boundary mocked: the crawler engine (fake ``crawl_url`` + link graph). NOT
mocked: the executor's page→item mapping, truncation, and captcha rollup.
"""

from __future__ import annotations

import pytest

from app.capabilities.web.crawl.executor import build_crawl_executor
from app.capabilities.web.crawl.schemas import CrawlInput, CrawlOutput
from app.proprietary.web_crawler import CrawlOutcome, CrawlOutcomeStatus

pytestmark = pytest.mark.unit

_SUCCESS = CrawlOutcomeStatus.SUCCESS


class _FakeEngine:
    def __init__(self, graph: dict[str, tuple[CrawlOutcomeStatus, list[str]]]):
        self._graph = graph
        self.calls: list[str] = []

    async def crawl_url(self, url: str) -> CrawlOutcome:
        self.calls.append(url)
        status, links = self._graph[url]
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


async def test_single_url_depth_zero_returns_one_item() -> None:
    engine = _FakeEngine({"https://e.com/": (_SUCCESS, ["https://e.com/a"])})
    execute = build_crawl_executor(engine=engine)

    out = await execute(CrawlInput(startUrls=["https://e.com/"]))

    assert isinstance(out, CrawlOutput)
    assert len(out.items) == 1
    item = out.items[0]
    assert item.url == "https://e.com/"
    assert item.status == "success"
    assert item.markdown == "C:https://e.com/"
    assert item.metadata == {"title": "https://e.com/"}
    assert item.crawl is not None
    assert item.crawl.depth == 0
    assert item.crawl.referrerUrl is None


async def test_spider_collects_multiple_pages_with_provenance() -> None:
    engine = _FakeEngine(
        {
            "https://e.com/": (_SUCCESS, ["https://e.com/a"]),
            "https://e.com/a": (_SUCCESS, []),
        }
    )
    execute = build_crawl_executor(engine=engine)

    out = await execute(
        CrawlInput(startUrls=["https://e.com/"], maxCrawlDepth=1, maxCrawlPages=10)
    )

    by_url = {item.url: item for item in out.items}
    assert set(by_url) == {"https://e.com/", "https://e.com/a"}
    assert by_url["https://e.com/a"].crawl.referrerUrl == "https://e.com/"


async def test_content_is_truncated_to_max_length() -> None:
    engine = _FakeEngine({"https://e.com/": (_SUCCESS, [])})
    execute = build_crawl_executor(engine=engine)

    out = await execute(CrawlInput(startUrls=["https://e.com/"], maxLength=3))

    assert out.items[0].markdown == "C:h"


async def test_failed_page_has_no_markdown_but_keeps_error() -> None:
    engine = _FakeEngine({"https://e.com/": (CrawlOutcomeStatus.FAILED, [])})
    execute = build_crawl_executor(engine=engine)

    out = await execute(CrawlInput(startUrls=["https://e.com/"]))

    item = out.items[0]
    assert item.status == "failed"
    assert item.markdown is None
    assert item.error == "boom"


async def test_aggregated_contacts_carry_provenance_and_site_wide_flag() -> None:
    footer = "https://linkedin.com/company/e"
    person = "https://linkedin.com/in/jane"

    class _ContactsEngine:
        async def crawl_url(self, url: str) -> CrawlOutcome:
            socials = [footer] + ([person] if url.endswith("/about") else [])
            links = ["https://e.com/about", "https://e.com/blog"] if url == "https://e.com/" else []
            return CrawlOutcome(
                status=_SUCCESS,
                result={
                    "content": "ok",
                    "metadata": {},
                    "links": links,
                    "contacts": {"emails": [], "phones": [], "socials": socials},
                },
            )

    execute = build_crawl_executor(engine=_ContactsEngine())
    out = await execute(
        CrawlInput(startUrls=["https://e.com/"], maxCrawlDepth=1, maxCrawlPages=10)
    )

    by_value = {ref.value: ref for ref in out.contacts.socials}
    assert by_value[footer].siteWide  # on all 3 pages -> boilerplate
    assert by_value[footer].pageCount == 3
    assert not by_value[person].siteWide  # only on /about -> page-local entity
    assert by_value[person].pages == ["https://e.com/about"]


async def test_single_page_crawl_marks_contacts_site_wide() -> None:
    class _OnePageEngine:
        async def crawl_url(self, url: str) -> CrawlOutcome:
            return CrawlOutcome(
                status=_SUCCESS,
                result={
                    "content": "ok",
                    "metadata": {},
                    "links": [],
                    "contacts": {"emails": ["a@e.com"], "phones": [], "socials": []},
                },
            )

    execute = build_crawl_executor(engine=_OnePageEngine())
    out = await execute(CrawlInput(startUrls=["https://e.com/"]))

    assert out.contacts.emails[0].siteWide  # one page: no signal to split on


async def test_captcha_telemetry_is_rolled_up_for_billing() -> None:
    class _CaptchaEngine:
        async def crawl_url(self, url: str) -> CrawlOutcome:
            return CrawlOutcome(
                status=_SUCCESS,
                result={"content": "ok", "metadata": {}, "links": []},
                captcha_attempts=2,
                captcha_solved=True,
            )

    execute = build_crawl_executor(engine=_CaptchaEngine())

    out = await execute(CrawlInput(startUrls=["https://e.com/"]))

    assert out.captcha_attempts == 2
    assert out.captcha_solved == 1
    assert out.billable_units == 1
