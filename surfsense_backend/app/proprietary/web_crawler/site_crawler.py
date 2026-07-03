# SurfSense proprietary crawler engine.
#
# Part of the ``app.proprietary`` package; licensed separately from the
# Apache-2.0 project root (see ``app/proprietary/LICENSE``).
"""Depth-bounded site crawl built on the single-URL engine (``crawl_url``).

Breadth-first frontier: fetch a page, follow its same-site links one hop deeper,
dedupe by canonical URL, stop at ``max_crawl_pages``. Every fetch runs through
``crawl_url`` so tiered fetch, proxy, and captcha handling are reused.

Sequential today; ``_fetch_page`` isolates one unit of work so a bounded worker
pool can replace the loop later without changing the traversal.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass

from app.proprietary.web_crawler.connector import (
    CrawlOutcome,
    CrawlOutcomeStatus,
    WebCrawlerConnector,
)
from app.proprietary.web_crawler.url_policy import canonicalize_url, host_of, same_site


@dataclass(frozen=True)
class CrawlPage:
    """A fetched page plus its crawl provenance (depth and referrer)."""

    url: str
    status: CrawlOutcomeStatus
    depth: int
    referrer: str | None = None
    loaded_url: str | None = None
    content: str | None = None
    metadata: dict[str, str] | None = None
    error: str | None = None
    captcha_attempts: int = 0
    captcha_solved: bool = False


async def crawl_site(
    engine: WebCrawlerConnector,
    start_urls: list[str],
    *,
    max_crawl_depth: int,
    max_crawl_pages: int,
) -> list[CrawlPage]:
    """Crawl ``start_urls`` up to ``max_crawl_depth`` hops / ``max_crawl_pages`` pages.

    Depth 0 fetches only the start URLs. Links are followed only from successful
    pages, under the depth cap, and only on a start URL's site. Start URLs count
    toward ``max_crawl_pages``. Order is BFS from the seeds.
    """
    allowed_hosts = {host_of(url) for url in start_urls}
    visited: set[str] = set()
    frontier: deque[tuple[str, int, str | None]] = deque()
    for seed in start_urls:
        key = canonicalize_url(seed)
        if key not in visited:
            visited.add(key)
            frontier.append((seed, 0, None))

    pages: list[CrawlPage] = []
    while frontier and len(pages) < max_crawl_pages:
        url, depth, referrer = frontier.popleft()
        page, outcome = await _fetch_page(engine, url, depth, referrer)
        pages.append(page)

        if depth >= max_crawl_depth:
            continue
        if outcome.status is not CrawlOutcomeStatus.SUCCESS or not outcome.result:
            continue
        for link in outcome.result.get("links", []):
            key = canonicalize_url(link)
            if key in visited or not same_site(link, allowed_hosts):
                continue
            visited.add(key)
            frontier.append((link, depth + 1, url))
    return pages


async def _fetch_page(
    engine: WebCrawlerConnector,
    url: str,
    depth: int,
    referrer: str | None,
) -> tuple[CrawlPage, CrawlOutcome]:
    """Fetch one URL and map it to a ``CrawlPage`` (the future concurrency unit)."""
    outcome = await engine.crawl_url(url)
    return _to_page(url, outcome, depth, referrer), outcome


def _to_page(
    url: str,
    outcome: CrawlOutcome,
    depth: int,
    referrer: str | None,
) -> CrawlPage:
    result = outcome.result or {}
    if outcome.status is CrawlOutcomeStatus.SUCCESS and result:
        return CrawlPage(
            url=url,
            status=outcome.status,
            depth=depth,
            referrer=referrer,
            loaded_url=result.get("loaded_url") or url,
            content=result.get("content"),
            metadata=result.get("metadata"),
            captcha_attempts=outcome.captcha_attempts,
            captcha_solved=outcome.captcha_solved,
        )
    return CrawlPage(
        url=url,
        status=outcome.status,
        depth=depth,
        referrer=referrer,
        error=outcome.error,
        captcha_attempts=outcome.captcha_attempts,
        captcha_solved=outcome.captcha_solved,
    )
