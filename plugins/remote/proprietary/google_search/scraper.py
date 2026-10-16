"""Orchestrator for the Google Search results scraper (Apify-compatible).

The core is the async generator :func:`iter_serps` (one item per SERP page);
:func:`scrape_serps` collects it under a caller-supplied ``limit``. Each
``queries`` line dispatches to a per-kind flow: a search term or a Google
Search URL. The pages of a call render side by side and are yielded in input
order (:func:`iter_serps`).
"""

from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import AsyncIterator, Awaitable, Callable, Iterator
from contextlib import aclosing
from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qs, urlsplit

from proprietary.scraping.concurrency import ordered_map

from . import fetch, searxng
from .fetch import fetch_serp_html
from .goto import PREFETCH, GotoPrefetch, resolve_item_urls
from .parsers import GOTO_PREFIX, parse_ai_mode, parse_serp
from .query_builder import (
    build_ai_mode_url,
    build_search_url,
    parse_queries,
    term_from_url,
)
from .schemas import GoogleSearchScrapeInput, SearchQuery, SerpItem

logger = logging.getLogger(__name__)

__all__ = ["iter_serps", "scrape_serps"]

# ``focusOnPaidAds``: Google serves ads non-deterministically, so a single
# render of a commercial query can come back with zero ads. When the add-on is
# on we re-render (fresh IP each time) until ads appear, capped here.
# ponytail: caps at 3 tries — each is a full ~10 s render, and beyond a few
# tries an ad-less result is genuinely ad-less, not just unlucky.
_PAID_ADS_MAX_TRIES = 3

# Google sometimes drops a ``site:`` operator and serves the unfiltered page
# (seen on the first render after a /sorry solve; the next render on the same
# IP honored it). Re-renders before falling back to SearXNG; 0 turns it off.
_SITE_RETRIES = int(os.getenv("GOOGLE_SEARCH_SITE_RETRIES", "1"))

# Render a call's pages side by side (GS-4); 0 renders them one after another.
_PARALLEL_PAGES = os.getenv("GOOGLE_SEARCH_PARALLEL_PAGES", "1") != "0"


def _search_query_stamp(
    term: str | None,
    url: str | None,
    page: int,
    input_model: GoogleSearchScrapeInput,
    *,
    domain: str = "google.com",
) -> SearchQuery:
    """The ``searchQuery`` provenance block Apify stamps on every item.

    ``domain`` is overridden when a page came from the fallback provider, so an
    aggregator result never claims to be a google.com SERP. The country and
    language are what the request sent: the Google URL's own ``gl``/``hl``, or
    for a fallback page (no URL) the caller's language and no country.
    """
    if url:
        params = parse_qs(urlsplit(url).query)
        country = (params.get("gl") or [None])[0]
        language = (params.get("hl") or [None])[0]
    else:
        country, language = None, input_model.languageCode or None
    return SearchQuery(
        term=term,
        url=url,
        device="MOBILE" if input_model.mobileResults else "DESKTOP",
        page=page,
        domain=domain,
        countryCode=country.upper() if country else None,
        languageCode=language,
        locationUule=input_model.locationUule,
    )


def _fill_displayed_urls(item: SerpItem) -> None:
    """Give forum and social cards, whose cite is "220+ comments · 4 months
    ago" rather than a URL, their resolved result's ``scheme://host``."""
    for result in item.organicResults:
        url = result.url or ""
        if result.displayedUrl or not url.startswith("http"):
            continue
        if url.startswith(GOTO_PREFIX):
            continue  # unresolved: the host would be google.com's
        parts = urlsplit(url)
        if parts.netloc:
            result.displayedUrl = f"{parts.scheme}://{parts.netloc}"


def _site_host(site: str) -> str:
    """The bare host of a ``site`` input ("https://www.nasa.gov/x" -> "nasa.gov")."""
    site = site.strip().lower()
    if "://" in site:
        site = urlsplit(site).netloc
    return site.split("/", 1)[0].removeprefix("www.")


def _keep_on_site(item: SerpItem, site: str) -> bool:
    """Drop organic results that are not on ``site``; True when Google honored it.

    A result is judged by its resolved URL, or by its displayed URL while the
    link is still a ``/goto`` redirect. One whose host is unknown is kept only
    when other results show the filter was applied. A page with no organic
    results counts as honored: it is a genuinely empty search, not a drop.
    """
    host = _site_host(site)
    if not host or not item.organicResults:
        return True
    verdicts: list[bool | None] = []
    for result in item.organicResults:
        url = result.url or ""
        if url.startswith(GOTO_PREFIX):
            url = result.displayedUrl or ""
        name = (urlsplit(url).hostname or "").lower() if url.startswith("http") else ""
        verdicts.append(name == host or name.endswith("." + host) if name else None)
    honored = any(verdicts)
    item.organicResults = [
        result
        for result, on_site in zip(item.organicResults, verdicts, strict=True)
        if on_site or (on_site is None and honored)
    ]
    return honored


async def _serp_page_flow(
    url: str,
    input_model: GoogleSearchScrapeInput,
    *,
    term: str | None,
    page: int,
    site_retries: int | None = None,
) -> SerpItem | None:
    """Fetch and parse one SERP page into a stamped :class:`SerpItem`.

    Renders ``url`` through the proxy and parses organic/paid/related/PAA blocks.
    When every IP is walled the page falls through to the SearXNG fallback
    (:func:`_searxng_page`); ``None`` means even that yielded nothing, so the
    caller stops paging.

    Under a ``site`` filter, off-site results never leave: when Google ignored
    the operator, the page is re-rendered ``site_retries`` times (default
    :data:`_SITE_RETRIES`), then served by SearXNG (which honors ``site:``),
    else returned without them.

    With ``focusOnPaidAds`` we re-render up to :data:`_PAID_ADS_MAX_TRIES` times
    until ads appear, returning the first ad-bearing SERP. If none surface, we
    return the richest ad-less render seen (a render occasionally comes back
    with the results container but no parsable organic blocks, so "last" is not
    a safe fallback).
    """
    if site_retries is None:
        site_retries = _SITE_RETRIES
    # focusOnPaidAds throws away up to two ad-less renders, and their waves
    # would resolve links for pages never returned: resolve after the parse.
    prefetch = GotoPrefetch() if PREFETCH and not input_model.focusOnPaidAds else None
    token = fetch.link_sink.set(prefetch)
    try:
        return await _serp_page(
            url,
            input_model,
            term=term,
            page=page,
            site_retries=site_retries,
            prefetch=prefetch,
        )
    finally:
        fetch.link_sink.reset(token)
        if prefetch is not None:
            prefetch.close()


async def _serp_page(
    url: str,
    input_model: GoogleSearchScrapeInput,
    *,
    term: str | None,
    page: int,
    site_retries: int,
    prefetch: GotoPrefetch | None,
) -> SerpItem | None:
    """:func:`_serp_page_flow`'s body, the render's links fed to ``prefetch``."""
    tries = _PAID_ADS_MAX_TRIES if input_model.focusOnPaidAds else 1
    best: SerpItem | None = None
    for attempt in range(1, tries + 1):
        html = await fetch_serp_html(url, mobile=input_model.mobileResults)
        if html is None:
            logger.warning("[google_search] no SERP HTML for %s", url)
            break
        # Rendered SERPs are ~1MB; parse off-loop to keep the server responsive.
        item = await asyncio.to_thread(
            parse_serp, html, include_icons=input_model.includeIcons
        )
        if input_model.saveHtml:
            item.html = html
        if not input_model.focusOnPaidAds or item.paidResults or item.paidProducts:
            best = item
            break
        # No ads yet; keep the render with the most organic results as fallback.
        if best is None or len(item.organicResults) > len(best.organicResults):
            best = item
        logger.info(
            "[google_search] focusOnPaidAds: no ads on try %d/%d, re-rendering",
            attempt,
            tries,
        )
    if best is None:
        return await _searxng_page(term, input_model, page=page)
    # Desktop result links are opaque google.com/goto redirects; turn them into
    # the destinations callers expect before the item leaves the scraper.
    await resolve_item_urls(best, prefetch=prefetch)
    _fill_displayed_urls(best)
    if input_model.site and not _keep_on_site(best, input_model.site):
        logger.warning(
            "[google_search] Google ignored site:%s on %s (retries left: %d)",
            input_model.site,
            url,
            site_retries,
        )
        if site_retries > 0:
            return await _serp_page_flow(
                url, input_model, term=term, page=page, site_retries=site_retries - 1
            )
        fallback = await _searxng_page(term, input_model, page=page)
        if fallback is not None:
            return fallback
        # The rest of the page is the unfiltered search's too.
        best.resultsTotal = None
        best.paidResults = []
        best.paidProducts = []
        best.peopleAlsoAsk = []
        best.aiOverview = None
    best.searchQuery = _search_query_stamp(term, url, page, input_model)
    return best


async def _searxng_page(
    term: str | None, input_model: GoogleSearchScrapeInput, *, page: int
) -> SerpItem | None:
    """Last-resort aggregator page when Google walled every IP.

    Skipped when the caller specifically wants ads (an aggregator serves none,
    so a result here would be a guaranteed miss dressed up as data) or when
    there is no plain term — a Google URL whose ``q`` we could not read has
    nothing to re-search.
    """
    if input_model.focusOnPaidAds or not term or not searxng.enabled():
        return None
    item = await searxng.search_serp(term, input_model, page=page)
    if item is None:
        return None
    item.searchQuery = _search_query_stamp(
        term, None, page, input_model, domain=searxng.domain()
    )
    return item


@dataclass(frozen=True)
class _Job:
    """One page of a call: a term's results page, a Google URL, or AI Mode."""

    kind: str  # "page", "url" or "ai"
    entry: int  # the queries line it belongs to
    value: str  # the term, or the URL
    page: int = 1


def _jobs(input_model: GoogleSearchScrapeInput) -> Iterator[_Job]:
    """Every page the call may render, in output order."""
    pages = input_model.maxPagesPerQuery or 1
    for index, entry in enumerate(parse_queries(input_model.queries)):
        if entry.kind == "url":
            yield _Job("url", index, entry.value)
            continue
        for page in range(1, pages + 1):
            yield _Job("page", index, entry.value, page)
        if input_model.aiModeSearch.enableAiMode:
            yield _Job("ai", index, entry.value)


async def _term_page(
    job: _Job, input_model: GoogleSearchScrapeInput, last_page: dict[int, int]
) -> list[dict[str, Any]]:
    """One results page of a term; ``last_page`` records where a term ended.

    A page with no item, or with no organic results, is past the term's last
    page, and so is every page after it: a later page not yet started is
    skipped, and one already rendered is dropped by :func:`iter_serps`.
    """
    if job.page > last_page.get(job.entry, job.page):
        return []
    url = build_search_url(job.value, input_model, page=job.page)
    item = await _serp_page_flow(url, input_model, term=job.value, page=job.page)
    if item is None or not item.organicResults:
        last_page[job.entry] = min(last_page.get(job.entry, job.page), job.page)
    if item is None:
        return []
    # An empty organic page is still yielded: it is the last one.
    return [item.to_output()]


async def _url_flow(
    url: str, input_model: GoogleSearchScrapeInput
) -> AsyncIterator[dict[str, Any]]:
    """Direct Google Search URL: scraped as-is (the URL's own parameters win
    over the localization inputs). ``maxPagesPerQuery`` paging (rewriting the
    ``start`` parameter) lands with the fetch implementation."""
    term = term_from_url(url)
    item = await _serp_page_flow(url, input_model, term=term, page=1)
    if item is None:
        return
    yield item.to_output()


async def _ai_mode_flow(
    term: str, input_model: GoogleSearchScrapeInput
) -> AsyncIterator[dict[str, Any]]:
    """Google AI Mode add-on: one conversational AI answer (+ cited sources)
    per query, emitted as its own item under ``aiModeResult``.

    Renders ``google.com/search?udm=50`` (the answer streams into
    ``[data-subtree='aimc']`` before network-idle). A page whose answer
    failed to generate parses to ``None`` and emits nothing.
    """
    url = build_ai_mode_url(term, input_model)
    html = await fetch_serp_html(url, mobile=input_model.mobileResults)
    if html is None:
        logger.warning("[google_search] no AI Mode HTML for %r", term)
        return
    result = await asyncio.to_thread(parse_ai_mode, html, query=term, url=url)
    if result is None:
        logger.info("[google_search] AI Mode answer missing for %r", term)
        return
    item = SerpItem(aiModeResult=result)
    await resolve_item_urls(item)
    if input_model.saveHtml:
        item.html = html
    item.searchQuery = _search_query_stamp(term, url, 1, input_model)
    yield item.to_output()


def _concurrency(jobs: int) -> int:
    """Pages rendered at once: the warm pool's slots (:func:`fetch.render_slots`)."""
    if not _PARALLEL_PAGES:
        return 1
    return max(1, min(jobs, fetch.render_slots()))


async def iter_serps(
    input_model: GoogleSearchScrapeInput,
) -> AsyncIterator[dict[str, Any]]:
    """Yield Apify-shaped SERP items for every line of ``queries``.

    Plain terms are searched (with the advanced filters folded in as search
    operators); full Google Search URLs are scraped as-is. When the AI Mode
    add-on is enabled, each term additionally yields an AI Mode item.

    The pages render side by side, as many as the warm pool has slots, and
    come out in input order. With no warm IP yet, the first page renders alone
    and warms one, so the rest share it instead of each vetting (and often
    solving) a fresh IP. A term's later pages are rendered ahead at most the
    concurrency's worth; the ones past its last page are dropped.
    """
    jobs = list(_jobs(input_model))
    if not jobs:
        return
    last_page: dict[int, int] = {}

    async def run(job: _Job) -> list[dict[str, Any]]:
        if job.kind == "page":
            return await _term_page(job, input_model, last_page)
        flow = _url_flow if job.kind == "url" else _ai_mode_flow
        return [item async for item in flow(job.value, input_model)]

    head = 0
    if _PARALLEL_PAGES and len(jobs) > 1 and _concurrency(len(jobs)) == 1:
        for item in await run(jobs[0]):
            yield item
        head = 1
    rest = jobs[head:]
    if not rest:
        return
    concurrency = _concurrency(len(rest))
    pages = ordered_map(rest, run, concurrency=concurrency, max_ahead=concurrency)
    async with aclosing(pages) as results:
        index = 0
        async for items in results:
            job = rest[index]
            index += 1
            if job.kind == "page" and job.page > last_page.get(job.entry, job.page):
                continue  # rendered ahead, past the term's last page
            for item in items:
                yield item


async def scrape_serps(
    input_model: GoogleSearchScrapeInput,
    *,
    limit: int | None = None,
    on_item: Callable[[int], Awaitable[None]] | None = None,
    on_stage: Callable[[str], Awaitable[None]] | None = None,
) -> list[dict[str, Any]]:
    """Collect :func:`iter_serps` into a list, honoring an optional ``limit``.

    ``limit`` is a request-time policy guard (used by the route), NOT a
    ceiling in the streaming core; reaching it cancels the pages still
    rendering. ``on_item`` hears the count after each item, and ``on_stage``
    each render attempt's stage, for the caller's progress.
    """
    results: list[dict[str, Any]] = []
    token = fetch.stage_hook.set(on_stage)
    try:
        async with aclosing(iter_serps(input_model)) as items:
            async for item in items:
                results.append(item)
                if on_item is not None:
                    await on_item(len(results))
                if limit is not None and len(results) >= limit:
                    break
    finally:
        fetch.stage_hook.reset(token)
    return results
