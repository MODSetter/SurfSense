"""SurfSense's Google Search plugin: Google's results pages, behind the license."""

from typing import Annotated, Any

from mcp.server.mcpserver import Context, MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp_types import CallToolResult, TextContent, ToolAnnotations
from pydantic import Field

from proprietary.google_search import searxng
from proprietary.google_search.schemas import GoogleSearchScrapeInput
from proprietary.google_search.scraper import scrape_serps
from proprietary.license_check.license_access import LicenseAccess

# Bounds one call's fan-out, as the scraper API's did.
MAX_QUERIES = 20
MAX_PAGES_PER_QUERY = 10
# Organic results the summary lists per page; every one is in the structured result.
SUMMARY_RESULTS = 10

access = LicenseAccess()


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
                    "Google Search URLs. Each term is searched; each URL is "
                    "scraped as it is."
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
            Field(description="Two-letter country to search from, such as 'us'."),
        ] = None,
        language_code: Annotated[
            str,
            Field(
                description="Results language code, such as 'en'; blank for Google's."
            ),
        ] = "",
        site: Annotated[
            str | None,
            Field(description="Only results from this domain, such as 'example.com'."),
        ] = None,
    ) -> CallToolResult:
        """Search Google: organic results, ads, People Also Ask, AI Overview and related searches."""
        total = len(queries) * max_pages_per_query

        async def heard(count: int) -> None:
            await ctx.report_progress(count, total)

        request = GoogleSearchScrapeInput(
            queries="\n".join(query.strip() for query in queries),
            maxPagesPerQuery=max_pages_per_query,
            countryCode=country_code,
            languageCode=language_code,
            site=site,
        )
        items = await scrape_serps(request, limit=total, on_item=heard)
        if not items:
            # Every address walled and no fallback answered: not the same as no results.
            raise ToolError(
                "Google refused every address tried, and no fallback answered. "
                "Try again in a few minutes."
            )
        return CallToolResult(
            content=[TextContent(type="text", text=_summary(items))],
            structured_content={"items": items},
        )

    return google_search


def _summary(items: list[dict[str, Any]]) -> str:
    """What the agent reads first; each page whole is in the structured result."""
    lines = [f"{len(items)} Google results pages"]
    for item in items:
        query = item.get("searchQuery") or {}
        where = query.get("term") or query.get("url") or ""
        source = (
            ", from SearXNG, not Google's ranking"
            if item.get("resultsProvider") == searxng.PROVIDER
            else ""
        )
        organic = item.get("organicResults") or []
        lines.append(
            f"{where}, page {query.get('page', 1)}{source}: {len(organic)} results"
        )
        for result in organic[:SUMMARY_RESULTS]:
            lines.append(
                f"  {result.get('position') or ''}. {result.get('title')} "
                f"{result.get('url') or ''}"
            )
    return "\n".join(lines)
