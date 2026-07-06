"""Orchestrator for the Google Search results scraper (Apify-compatible).

Skeleton mirroring the YouTube/Maps scraper layout: the core is the async
generator :func:`iter_serps` (one item per SERP page), :func:`scrape_serps` is
a thin collector with a caller-supplied ``limit`` guard. Each ``queries`` line
dispatches to a per-kind flow (search term / direct Google Search URL) which
is currently a no-op — each will be implemented progressively, exactly like
the YouTube and Maps flows were.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from typing import Any

from .fetch import fetch_serp_html
from .parsers import parse_ai_mode, parse_serp
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


def _search_query_stamp(
    term: str | None, url: str, page: int, input_model: GoogleSearchScrapeInput
) -> SearchQuery:
    """The ``searchQuery`` provenance block Apify stamps on every item."""
    return SearchQuery(
        term=term,
        url=url,
        device="MOBILE" if input_model.mobileResults else "DESKTOP",
        page=page,
        domain="google.com",
        countryCode=(input_model.countryCode or "US").upper(),
        languageCode=input_model.languageCode or None,
        locationUule=input_model.locationUule,
    )


async def _serp_page_flow(
    url: str, input_model: GoogleSearchScrapeInput
) -> SerpItem | None:
    """Fetch and parse one SERP page into a :class:`SerpItem`.

    Renders ``url`` through the proxy and parses organic/paid/related/PAA blocks.
    Returns ``None`` when the page could not be fetched (all IPs walled), so the
    caller stops paging.

    With ``focusOnPaidAds`` we re-render up to :data:`_PAID_ADS_MAX_TRIES` times
    until ads appear, returning the first ad-bearing SERP. If none surface, we
    return the richest ad-less render seen (a render occasionally comes back
    with the results container but no parsable organic blocks, so "last" is not
    a safe fallback).
    """
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
            return item
        # No ads yet; keep the render with the most organic results as fallback.
        if best is None or len(item.organicResults) > len(best.organicResults):
            best = item
        logger.info(
            "[google_search] focusOnPaidAds: no ads on try %d/%d, re-rendering",
            attempt,
            tries,
        )
    return best


async def _term_flow(
    term: str, input_model: GoogleSearchScrapeInput
) -> AsyncIterator[dict[str, Any]]:
    """Search-term discovery: one item per result page, up to
    ``maxPagesPerQuery``, stopping early when a page has no next page."""
    pages = input_model.maxPagesPerQuery or 1
    for page in range(1, pages + 1):
        url = build_search_url(term, input_model, page=page)
        item = await _serp_page_flow(url, input_model)
        if item is None:
            return
        item.searchQuery = _search_query_stamp(term, url, page, input_model)
        yield item.to_output()
        # An empty organic page means we've run past the last result page.
        if not item.organicResults:
            return


async def _url_flow(
    url: str, input_model: GoogleSearchScrapeInput
) -> AsyncIterator[dict[str, Any]]:
    """Direct Google Search URL: scraped as-is (the URL's own parameters win
    over the localization inputs). ``maxPagesPerQuery`` paging (rewriting the
    ``start`` parameter) lands with the fetch implementation."""
    term = term_from_url(url)
    item = await _serp_page_flow(url, input_model)
    if item is None:
        return
    item.searchQuery = _search_query_stamp(term, url, 1, input_model)
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
    if input_model.saveHtml:
        item.html = html
    item.searchQuery = _search_query_stamp(term, url, 1, input_model)
    yield item.to_output()


async def iter_serps(
    input_model: GoogleSearchScrapeInput,
) -> AsyncIterator[dict[str, Any]]:
    """Yield Apify-shaped SERP items for every line of ``queries``.

    Plain terms are searched (with the advanced filters folded in as search
    operators); full Google Search URLs are scraped as-is. When the AI Mode
    add-on is enabled, each term additionally yields an AI Mode item.
    """
    for entry in parse_queries(input_model.queries):
        if entry.kind == "url":
            async for item in _url_flow(entry.value, input_model):
                yield item
            continue
        async for item in _term_flow(entry.value, input_model):
            yield item
        if input_model.aiModeSearch.enableAiMode:
            async for item in _ai_mode_flow(entry.value, input_model):
                yield item


async def scrape_serps(
    input_model: GoogleSearchScrapeInput, *, limit: int | None = None
) -> list[dict[str, Any]]:
    """Collect :func:`iter_serps` into a list, honoring an optional ``limit``.

    ``limit`` is a request-time policy guard (used by the route), NOT a
    ceiling in the streaming core.
    """
    from app.capabilities.core.progress import emit_progress

    results: list[dict[str, Any]] = []
    async for item in iter_serps(input_model):
        results.append(item)
        emit_progress("scraping", current=len(results), total=limit, unit="page")
        if limit is not None and len(results) >= limit:
            break
    return results
