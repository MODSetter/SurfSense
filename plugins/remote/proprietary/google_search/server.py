"""SurfSense's Google Search plugin: Google's results pages, behind the license."""

import asyncio
import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated, Any

from mcp.server.mcpserver import Context, MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp_types import CallToolResult, ToolAnnotations
from pydantic import Field

from mcp_server.progress import stage
from mcp_server.results import ELLIPSIS, tool_result, wants_text_only
from proprietary.google_search import searxng
from proprietary.google_search.fetch import warm_browser
from proprietary.google_search.query_builder import is_page_url
from proprietary.google_search.schemas import GoogleSearchScrapeInput
from proprietary.google_search.scraper import scrape_serps
from proprietary.license_check.license_access import shared_access
from proprietary.scraping import lifecycle

logger = logging.getLogger(__name__)

# Bounds one call's fan-out, as the scraper API's did.
MAX_QUERIES = 20
MAX_PAGES_PER_QUERY = 10
# A page's AI Overview runs to 2-3k characters; keep it about whole.
CLIP_CHARS = 2500
# A page-1 line ran 9-15 KB, its People Also Ask answers alone 4.5-6 KB, so
# the 32 KB text lost a call's third query. Each answer keeps its opening.
PAA_ANSWER_CHARS = 400
# Past this many pages each is listed in about 3 KB (its results in rank
# order, the overview's opening, the questions), so ten or more fit.
FULL_PAGES = 3
COMPACT_OVERVIEW_CHARS = 300

access = shared_access()


@asynccontextmanager
async def lifespan() -> AsyncIterator[None]:
    """Launches the desktop browser in the background (GS-8): about 0.5 s on a
    desktop and 5 s in prod off the first call. It opens no page, so it spends
    no proxy or captcha credit; GOOGLE_SEARCH_WARM_BROWSER=0 skips it."""
    async with lifecycle.lifespan():
        warming = None
        if os.getenv("GOOGLE_SEARCH_WARM_BROWSER", "1") != "0":
            warming = asyncio.create_task(_warm())
        try:
            yield
        finally:
            if warming is not None:
                warming.cancel()


async def _warm() -> None:
    try:
        await warm_browser()
    except Exception:
        # The first call launches it instead.
        logger.warning("[google_search] browser warm-up failed", exc_info=True)


def server() -> MCPServer:
    google_search = MCPServer("google-search")

    @google_search.tool(
        annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True)
    )
    async def scrape(
        ctx: Context,
        queries: Annotated[
            list[str],
            Field(
                min_length=1,
                max_length=MAX_QUERIES,
                description=(
                    "Search terms, such as 'wedding photographers denver', or full "
                    "Google Search URLs, scraped as they are. Not pages to read: "
                    "another site's URL is refused."
                ),
            ),
        ],
        max_pages_per_query: Annotated[
            int,
            Field(
                ge=1,
                le=MAX_PAGES_PER_QUERY,
                description="Results pages per query, about 10 results each.",
            ),
        ] = 1,
        country_code: Annotated[
            str | None,
            Field(
                description=(
                    "Two-letter country to search from, such as 'us'; blank with "
                    "no language_code means US English."
                )
            ),
        ] = None,
        language_code: Annotated[
            str,
            Field(
                description=(
                    "Results language code, such as 'en'; blank with no "
                    "country_code means US English."
                )
            ),
        ] = "",
        site: Annotated[
            str | None,
            Field(description="Only results from this domain, such as 'example.com'."),
        ] = None,
    ) -> CallToolResult:
        """Search Google: organic results, ads, People Also Ask, AI Overview and related searches."""
        pages = [query.strip() for query in queries if is_page_url(query)]
        if pages:
            # Searched as a term, a page's URL costs a render and finds nothing useful.
            raise ToolError(
                f"Google Search only searches; {', '.join(pages)} is a page to "
                "read, not a search. Read it with SurfSense's Web Crawl, if it "
                "is connected, or give search terms or Google Search URLs such as "
                "https://www.google.com/search?q=..."
            )
        total = len(queries) * max_pages_per_query
        await stage(ctx, f"searching {total} results pages", total=total)

        async def heard(count: int) -> None:
            await stage(ctx, f"{count} of {total} pages", done=count, total=total)

        async def attempt(message: str) -> None:
            await stage(ctx, message)

        request = GoogleSearchScrapeInput(
            queries="\n".join(query.strip() for query in queries),
            maxPagesPerQuery=max_pages_per_query,
            countryCode=country_code,
            languageCode=language_code,
            site=site,
        )
        items = await scrape_serps(
            request, limit=total, on_item=heard, on_stage=attempt
        )
        if not items:
            # Every address walled and no fallback answered: not the same as no results.
            raise ToolError(
                "Google refused every address tried, and no fallback answered. "
                "Try again in a few minutes."
            )
        compact = len(items) > FULL_PAGES
        return tool_result(
            _summary(items, compact=compact),
            items,
            project=_projected_compact if compact else _projected,
            clip_chars=CLIP_CHARS,
            text_only=wants_text_only(ctx),
        )

    return google_search


def _summary(items: list[dict[str, Any]], *, compact: bool = False) -> str:
    """The header the agent reads above one JSON line per results page."""
    if compact:
        return (
            f"{len(items)} Google results pages, one per line: the query, its "
            "organic results, People Also Ask questions, the AI Overview's "
            "opening and related searches"
        )
    return (
        f"{len(items)} Google results pages, one per line: the query, its organic "
        "results, People Also Ask answers, AI Overview, ads and related searches"
    )


def _projected(item: dict[str, Any]) -> dict[str, Any]:
    """What an agent needs from a page to answer without another call."""
    query = item.get("searchQuery") or {}
    aio = item.get("aiOverview") or {}
    return {
        "query": query.get("term") or query.get("url"),
        "page": query.get("page"),
        "source": (
            "SearXNG, not Google's ranking"
            if item.get("resultsProvider") == searxng.PROVIDER
            else None
        ),
        "resultsTotal": item.get("resultsTotal"),
        "aiOverview": {
            "text": aio.get("content"),
            "sources": [_pick(s, "title", "url") for s in aio.get("sources") or []],
        },
        "organic": [
            _pick(r, "position", "title", "url", "description", "date")
            for r in item.get("organicResults") or []
        ],
        "peopleAlsoAsk": [
            {
                **_pick(q, "question", "url"),
                "answer": _clip(q.get("answer"), PAA_ANSWER_CHARS),
            }
            for q in item.get("peopleAlsoAsk") or []
        ],
        "ads": [
            _pick(r, "title", "url", "description")
            for r in item.get("paidResults") or []
        ],
        "products": [
            _pick(p, "title", "url", "prices") for p in item.get("paidProducts") or []
        ],
        "related": [r.get("title") for r in item.get("relatedQueries") or []],
    }


def _projected_compact(item: dict[str, Any]) -> dict[str, Any]:
    """A page of a many-page call: what answers most questions in about 3 KB."""
    page = _projected(item)
    return {
        **page,
        "aiOverview": _clip(page["aiOverview"]["text"], COMPACT_OVERVIEW_CHARS),
        "organic": [_pick(r, "title", "url", "description") for r in page["organic"]],
        "peopleAlsoAsk": [q["question"] for q in page["peopleAlsoAsk"]],
        "ads": None,
        "products": None,
    }


def _pick(record: dict[str, Any], *keys: str) -> dict[str, Any]:
    return {key: record.get(key) for key in keys}


def _clip(text: str | None, chars: int) -> str | None:
    if text is None or len(text) <= chars:
        return text
    return text[:chars] + ELLIPSIS
