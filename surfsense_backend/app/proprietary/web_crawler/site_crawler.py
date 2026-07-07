# SurfSense proprietary crawler engine.
#
# Part of the ``app.proprietary`` package; licensed separately from the
# Apache-2.0 project root (see ``app/proprietary/LICENSE``).
"""Depth-bounded site crawl driven by Scrapling's spider engine.

The traversal (frontier, dedupe, link filtering, same-site scope) is Scrapling's
``CrawlerEngine`` + ``LinkExtractor``; every *fetch* still goes through our
``WebCrawlerConnector.crawl_url`` so the tiered fetch ladder, proxy rotation, and
captcha handling are reused unchanged.

The bridge is ``_ConnectorSession``: a duck-typed Scrapling "session" whose
``fetch`` calls ``crawl_url`` and wraps the ``CrawlOutcome`` in a Scrapling
``Response`` (the outcome is stashed on the response so ``parse`` can rebuild a
``CrawlPage``). The engine is awaited directly on the caller's event loop —
``Spider.start()`` is avoided because it spins up its own loop via ``anyio.run``.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from scrapling.spiders import CrawlerEngine, LinkExtractor, Response, Spider

from app.capabilities.core.progress import emit_progress
from app.proprietary.web_crawler.connector import (
    CrawlOutcome,
    CrawlOutcomeStatus,
    WebCrawlerConnector,
)
from app.proprietary.web_crawler.url_policy import host_of

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from scrapling.spiders import Request


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
    error: str | None = None
    captcha_attempts: int = 0
    captcha_solved: bool = False


# HTTP status the fake Response reports per outcome. Only used for Scrapling's
# stats/logging; block detection is disabled (our connector owns that), so the
# exact codes never gate a retry.
_HTTP_STATUS: dict[CrawlOutcomeStatus, int] = {
    CrawlOutcomeStatus.SUCCESS: 200,
    CrawlOutcomeStatus.EMPTY: 204,
    CrawlOutcomeStatus.FAILED: 502,
}


class _ConnectorSession:
    """Scrapling-compatible session that fetches via ``WebCrawlerConnector``.

    ``SessionManager`` treats any non-``FetcherSession`` object as a browser-style
    session and calls ``await session.fetch(url=..., **kwargs)``. We satisfy that
    contract, run the real crawl, and translate the ``CrawlOutcome`` into a
    ``Response`` — attaching the outcome as ``response._outcome`` (not ``meta``,
    which ``response.follow`` would copy onto every child request).
    """

    def __init__(self, connector: WebCrawlerConnector):
        self._connector = connector
        self._is_alive = False

    async def __aenter__(self) -> _ConnectorSession:
        self._is_alive = True
        return self

    async def __aexit__(self, *_exc: object) -> None:
        self._is_alive = False

    async def fetch(self, url: str, **_kwargs: Any) -> Response:
        emit_progress("fetching", f"Fetching {url}", unit="page", url=url)
        outcome = await self._connector.crawl_url(url)
        if outcome.captcha_attempts:
            emit_progress(
                "captcha",
                f"Captcha {'solved' if outcome.captcha_solved else 'attempted'} on {url}",
                url=url,
                attempts=outcome.captcha_attempts,
                solved=outcome.captcha_solved,
            )
        result = outcome.result or {}
        content = result.get("content")
        # Selector chokes on empty content; a fetch that raises would be counted
        # as a failed request (no parse), dropping the page from the output. Feed
        # a harmless placeholder so failed/empty pages still reach ``parse``.
        response = Response(
            url=result.get("loaded_url") or url,
            content=content or "<html></html>",
            status=_HTTP_STATUS[outcome.status],
            reason=outcome.status.value,
            cookies={},
            headers={},
            request_headers={},
        )
        response._outcome = outcome  # type: ignore[attr-defined]
        return response


class _SiteSpider(Spider):
    """Depth/page-bounded spider whose fetching is delegated to the connector.

    Concurrency is pinned to 1 so the page cap — and the per-page billing derived
    from it — stays exact and the output preserves breadth-first order.
    ponytail: raising ``concurrent_requests`` needs an atomic page-budget guard to
    avoid overshooting ``max_pages`` (and thus over-fetching / over-billing).
    """

    name = "surfsense_site"
    concurrent_requests = 1
    max_blocked_retries = 0
    logging_level = logging.WARNING

    def __init__(
        self,
        connector: WebCrawlerConnector,
        start_urls: list[str],
        *,
        max_depth: int,
        max_pages: int,
        link_extractor: LinkExtractor,
    ):
        self._connector = connector
        self._max_depth = max_depth
        self._max_pages = max_pages
        self._link_extractor = link_extractor
        self.pages: list[CrawlPage] = []
        super().__init__()
        self.start_urls = list(start_urls)

    def configure_sessions(self, manager: Any) -> None:
        manager.add("default", _ConnectorSession(self._connector))

    async def is_blocked(self, response: Response) -> bool:
        # The connector already classifies blocks and exhausts its own fallback
        # ladder + proxy rotation; never let the spider re-fetch on top of that.
        return False

    async def parse(self, response: Response) -> AsyncGenerator[Request | None, None]:
        outcome: CrawlOutcome = response._outcome  # type: ignore[attr-defined]
        depth: int = response.meta.get("_depth", 0)
        referrer: str | None = response.meta.get("_referrer")
        req_url = response.request.url if response.request else str(response.url)

        if len(self.pages) < self._max_pages:
            self.pages.append(_to_page(req_url, outcome, depth, referrer))
            emit_progress(
                "crawled",
                f"Crawled {req_url}",
                current=len(self.pages),
                total=self._max_pages,
                unit="page",
                url=req_url,
                depth=depth,
                status=outcome.status.value,
            )

        # Cap reached: stop the engine so queued-but-unfetched links are abandoned
        # (never fetched, never billed), matching the old BFS's per-fetch guard.
        if len(self.pages) >= self._max_pages:
            self.pause()
            return
        if depth >= self._max_depth:
            return
        if outcome.status is not CrawlOutcomeStatus.SUCCESS or not outcome.result:
            return

        for link in outcome.result.get("links", []):
            if not self._link_extractor.matches(link):
                continue
            yield response.follow(
                link, meta={"_depth": depth + 1, "_referrer": req_url}
            )


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
) -> list[CrawlPage]:
    """Crawl ``start_urls`` up to ``max_crawl_depth`` hops / ``max_crawl_pages`` pages.

    Depth 0 fetches only the start URLs. Links are followed only from successful
    pages, under the depth cap, on the seeds' sites (subdomains included), and
    matching ``include_patterns`` / not matching ``exclude_patterns`` (regexes).
    Start URLs count toward ``max_crawl_pages``. Order is breadth-first.
    """
    link_extractor = LinkExtractor(
        allow=tuple(include_patterns or ()),
        deny=tuple(exclude_patterns or ()),
        allow_domains=tuple(host_of(u) for u in start_urls),
    )
    spider = _SiteSpider(
        engine,
        start_urls,
        max_depth=max_crawl_depth,
        max_pages=max_crawl_pages,
        link_extractor=link_extractor,
    )
    crawler = CrawlerEngine(spider, spider._session_manager)
    spider._engine = crawler  # enable spider.pause() to stop at the page cap
    await crawler.crawl()
    return spider.pages
