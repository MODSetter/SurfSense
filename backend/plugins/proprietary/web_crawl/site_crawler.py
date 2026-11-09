"""Depth-bounded site crawl: level by level, each level's pages fetched side by side through ``crawl_url``.

A level's URLs run through ``ordered_map``, so the output and the next level's
frontier keep breadth-first order while the fetches overlap. Only as many URLs
as the page budget has left are sent, so ``max_crawl_pages`` bounds the fetches.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
from collections.abc import AsyncIterator, Awaitable, Callable, Iterable
from contextlib import aclosing, asynccontextmanager
from dataclasses import dataclass

from scrapling.spiders import LinkExtractor

from proprietary.scraping.concurrency import ordered_map
from proprietary.scraping.logged_host import logged_host
from proprietary.web_crawl.classifier import BlockType
from proprietary.web_crawl.connector import (
    CrawlOutcome,
    CrawlOutcomeStatus,
    PageLimits,
    WebCrawlerConnector,
)
from proprietary.web_crawl.url_policy import canonical_url, host_of

logger = logging.getLogger(__name__)


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
    contacts: dict[str, list[str]] | None = None
    links: list[dict[str, str]] | None = None
    # Links on the page before ``links`` was capped.
    links_total: int | None = None
    error: str | None = None
    captcha_attempts: int = 0
    captcha_solved: bool = False


def _concurrency() -> int:
    """Pages fetched at once; ``WEB_CRAWL_CONCURRENCY=1`` fetches one at a time, as before."""
    try:
        return max(1, int(os.environ.get("WEB_CRAWL_CONCURRENCY", "6")))
    except ValueError:
        return 6


# Pages fetched at once on one host: each fetch draws its own exit, so the
# per-IP rate is unchanged, but the site sees more at once.
_PER_HOST = 4
# The site's answer to too many requests: that host gets half the slots.
_PUSHBACK = re.compile(r"\bHTTP (?:429|503)\b")


class _HostGate:
    """At most ``limit`` fetches at once on one host; the limit halves on push-back."""

    def __init__(self, limit: int) -> None:
        self.limit = limit
        self._active = 0
        self._free = asyncio.Condition()

    @asynccontextmanager
    async def slot(self) -> AsyncIterator[None]:
        async with self._free:
            await self._free.wait_for(lambda: self._active < self.limit)
            self._active += 1
        try:
            yield
        finally:
            async with self._free:
                self._active -= 1
                self._free.notify_all()

    def halve(self) -> None:
        self.limit = max(1, self.limit // 2)


def _pushed_back(outcome: CrawlOutcome) -> bool:
    return outcome.block_type is BlockType.RATE_LIMITED or bool(
        outcome.error and _PUSHBACK.search(outcome.error)
    )


@dataclass(frozen=True)
class _Job:
    url: str
    depth: int
    referrer: str | None


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
            contacts=result.get("contacts"),
            links=result.get("link_records"),
            links_total=result.get("links_total"),
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


async def crawl_site(
    engine: WebCrawlerConnector,
    start_urls: list[str],
    *,
    max_crawl_depth: int,
    max_crawl_pages: int,
    include_patterns: Iterable[str] | None = None,
    exclude_patterns: Iterable[str] | None = None,
    on_item: Callable[[int], Awaitable[None]] | None = None,
    on_stage: Callable[[str], Awaitable[None]] | None = None,
    limits: PageLimits | None = None,
) -> list[CrawlPage]:
    """Crawl ``start_urls`` up to ``max_crawl_depth`` hops / ``max_crawl_pages`` pages.

    Depth 0 fetches only the start URLs. Links are followed only from successful
    pages, under the depth cap, on the seeds' sites (subdomains included), and
    matching ``include_patterns`` / not matching ``exclude_patterns`` (regexes).
    Start URLs count toward ``max_crawl_pages``. Order is breadth-first. A
    discovered page that redirects onto one already crawled is dropped; a start
    URL never is. ``on_item`` is awaited
    with the running page count after each page, ``on_stage`` with a line as a
    fetch moves to its next tier; ``limits`` bounds each page.
    """
    link_extractor = LinkExtractor(
        allow=tuple(include_patterns or ()),
        deny=tuple(exclude_patterns or ()),
        allow_domains=tuple(host_of(u) for u in start_urls),
    )
    limits = limits or PageLimits()
    concurrency = _concurrency()
    gates: dict[str, _HostGate] = {}
    # Canonical URLs sent or queued, and of pages crawled as requested and as
    # finally loaded: a redirect to a page already crawled is the same page.
    queued: set[str] = set()
    crawled: set[str] = set()
    pages: list[CrawlPage] = []

    async def fetch(job: _Job) -> CrawlOutcome:
        host = host_of(job.url)
        gate = gates.setdefault(host, _HostGate(min(_PER_HOST, concurrency)))

        async def moved(tier: str) -> None:
            if on_stage is not None:
                await on_stage(f"{job.url}: {tier}")

        async with gate.slot():
            try:
                outcome = await engine.crawl_url(job.url, limits, moved)
            except Exception as exc:  # one bad page must not end the crawl
                logger.warning(
                    "[webcrawler] a page on %s failed: %s", logged_host(job.url), exc
                )
                outcome = CrawlOutcome(status=CrawlOutcomeStatus.FAILED, error=str(exc))
        if _pushed_back(outcome) and gate.limit > 1:
            gate.halve()
            logger.info("[webcrawler] %s pushed back: %d at once", host, gate.limit)
        return outcome

    level: list[_Job] = []
    for url in start_urls:
        key = canonical_url(url)
        if key not in queued:
            queued.add(key)
            level.append(_Job(url, 0, None))

    while level and len(pages) < max_crawl_pages:
        next_level: list[_Job] = []
        while level and len(pages) < max_crawl_pages:
            # Never more fetches than the budget has pages left; a page dropped
            # as a redirect duplicate frees its slot for the next batch.
            room = max_crawl_pages - len(pages)
            batch, level = level[:room], level[room:]
            async with aclosing(
                ordered_map(batch, fetch, concurrency=concurrency)
            ) as outcomes:
                index = 0
                async for outcome in outcomes:
                    job = batch[index]
                    index += 1
                    links = _record(job, outcome, crawled, pages)
                    if links is None:
                        continue
                    if on_item is not None:
                        await on_item(len(pages))
                    if job.depth >= max_crawl_depth:
                        continue
                    # A big page has thousands of links: filter them off the loop.
                    followed = await asyncio.to_thread(
                        _followable, links, link_extractor
                    )
                    for key, link in followed:
                        if key in queued or key in crawled:
                            continue
                        queued.add(key)
                        next_level.append(_Job(link, job.depth + 1, job.url))
        level = next_level
    return pages


def _followable(
    links: list[str], link_extractor: LinkExtractor
) -> list[tuple[str, str]]:
    """``links`` the crawl may follow, each with its canonical URL."""
    return [
        (canonical_url(link), link) for link in links if link_extractor.matches(link)
    ]


def _record(
    job: _Job, outcome: CrawlOutcome, crawled: set[str], pages: list[CrawlPage]
) -> list[str] | None:
    """Add ``job``'s page; its links, or ``None`` when it was dropped as a duplicate."""
    loaded = (outcome.result or {}).get("loaded_url")
    if job.depth > 0 and loaded and canonical_url(loaded) in crawled:
        # A link that redirects onto a page already crawled (a domain root
        # onto its start page): neither output nor frontier gains anything.
        # A start URL was asked for by name, so it is always kept.
        return None
    crawled.update(canonical_url(u) for u in (job.url, loaded) if u)
    pages.append(_to_page(job.url, outcome, job.depth, job.referrer))
    if outcome.status is not CrawlOutcomeStatus.SUCCESS or not outcome.result:
        return []
    return list(outcome.result.get("links", []))
