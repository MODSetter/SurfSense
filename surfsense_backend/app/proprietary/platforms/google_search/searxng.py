"""Last-resort SearXNG fallback for the Google Search scraper.

When Google walls every vetted IP (``fetch_serp_html`` returns ``None`` after
its pool/deadline budget), this returns the same ``SerpItem`` shape from a
SearXNG instance's JSON API, so a search yields organic results instead of
nothing. Keyed on ``SEARXNG_FALLBACK_URL``, which the Docker stack points at
its bundled ``searxng`` service; unset elsewhere means off.

SearXNG is a metasearch aggregator, not Google: only organic results (title,
url, snippet) and query suggestions exist. Ads, People-Also-Ask, AI Overview,
sitelinks, icons, and result totals are Google-only and stay empty, and every
item carries ``resultsProvider="searxng"`` so no consumer reports aggregator
hits as Google rankings.

``ponytail:`` best-effort — any error/timeout returns ``None`` and the caller
behaves exactly as it does today. The instance must serve JSON
(``search.formats`` including ``json`` in its ``settings.yml``); a stock
self-hosted install answers 403 until it does.
"""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx

from .schemas import (
    GoogleSearchScrapeInput,
    OrganicResult,
    RelatedQuery,
    SerpItem,
    SuggestedResult,
)

logger = logging.getLogger(__name__)

PROVIDER = "searxng"

# Read here rather than in app.config to match the sibling fetch seam, which
# takes its own knobs straight from the environment.
_HOST = os.getenv("SEARXNG_FALLBACK_URL", "").strip()
_TIMEOUT_S = float(os.getenv("SEARXNG_FALLBACK_TIMEOUT_S", "10"))
# A Google SERP page is 10 results; cap the aggregator to the same so a
# fallback page never looks anomalously large to a caller that is paging.
_MAX_RESULTS = 10

# ``quickDateRange`` (Google ``tbs=qdr:``) -> SearXNG ``time_range``. Only the
# plain units map; compound codes like "m6" have no equivalent and are dropped
# rather than approximated.
_TIME_RANGE = {"d": "day", "w": "week", "m": "month", "y": "year"}


def enabled() -> bool:
    """True when a fallback instance is configured."""
    return bool(_HOST)


def domain() -> str:
    """Provider label for ``searchQuery.domain`` — not the configured host,
    which is often a private address that should not reach API output."""
    return PROVIDER


def _query(term: str, input_model: GoogleSearchScrapeInput) -> str:
    """The term with only the operators SearXNG actually honors.

    ``site:`` and exact-match quoting are supported across its engines;
    ``intitle:``/``intext:``/``inurl:``/``filetype:``/``before:``/``after:``
    are not, and folding them in returns zero results instead of degrading.
    """
    query = f'"{term}"' if input_model.forceExactMatch else term
    if input_model.site:
        query = f"{query} site:{input_model.site}"
    return query


async def _fetch_json(params: dict[str, Any]) -> dict[str, Any] | None:
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT_S) as client:
            response = await client.get(f"{_HOST.rstrip('/')}/search", params=params)
        if response.status_code == 403:
            logger.warning(
                "[google_search][searxng] instance refused the JSON API (403); "
                "add 'json' to search.formats in its settings.yml"
            )
            return None
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.warning("[google_search][searxng] fallback request failed: %s", e)
        return None


async def search_serp(
    term: str, input_model: GoogleSearchScrapeInput, *, page: int = 1
) -> SerpItem | None:
    """One SearXNG results page as a ``SerpItem``, or ``None`` if unusable."""
    if not enabled():
        return None

    params: dict[str, Any] = {
        "q": _query(term, input_model),
        "format": "json",
        "pageno": page,
        "categories": "general",
    }
    if input_model.languageCode:
        params["language"] = input_model.languageCode
    time_range = _TIME_RANGE.get((input_model.quickDateRange or "").lower())
    if time_range:
        params["time_range"] = time_range

    payload = await _fetch_json(params)
    if payload is None:
        return None

    usable = [r for r in (payload.get("results") or []) if r.get("url")][:_MAX_RESULTS]
    if not usable:
        logger.info("[google_search][searxng] no results for %r", term)
        return None

    suggestions = [s for s in (payload.get("suggestions") or []) if s][:_MAX_RESULTS]
    logger.info(
        "[google_search][searxng] fallback served %d result(s) for %r page=%d",
        len(usable),
        term,
        page,
    )
    return SerpItem(
        organicResults=[
            OrganicResult(
                title=r.get("title"),
                url=r.get("url"),
                description=r.get("content"),
                position=i,
            )
            for i, r in enumerate(usable, start=1)
        ],
        relatedQueries=[RelatedQuery(title=s) for s in suggestions],
        suggestedResults=[
            SuggestedResult(title=s, position=i)
            for i, s in enumerate(suggestions, start=1)
        ],
        # Extra field (SerpItem is extra="allow"), so it flows untouched through
        # to_output() into REST, MCP, playground, and the chat subagent.
        resultsProvider=PROVIDER,
    )
