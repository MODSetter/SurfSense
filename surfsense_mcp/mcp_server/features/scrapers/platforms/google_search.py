"""Google Search scraper tool."""

from __future__ import annotations

from typing import Annotated

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from ....core.client import SurfSenseClient
from ....core.rendering import ResponseFormatParam
from ....core.workspace_context import WorkspaceContext, WorkspaceParam
from ..annotations import SCRAPE
from ..capability import run_scraper


def register(
    mcp: FastMCP, client: SurfSenseClient, context: WorkspaceContext
) -> None:
    """Register the Google Search tool."""

    @mcp.tool(
        name="surfsense_google_search",
        title="Scrape Google Search",
        annotations=SCRAPE,
        structured_output=False,
    )
    async def google_search(
        queries: Annotated[
            list[str],
            Field(
                min_length=1,
                description="Search terms or full Google Search URLs, e.g. "
                "['best rss readers 2026'].",
            ),
        ],
        max_pages_per_query: Annotated[
            int, Field(ge=1, description="Result pages to fetch per query.")
        ] = 1,
        country_code: Annotated[
            str | None,
            Field(description="Two-letter country to search from, e.g. 'us'."),
        ] = None,
        language_code: Annotated[
            str, Field(description="Results language, e.g. 'en'. Empty for default.")
        ] = "",
        site: Annotated[
            str | None,
            Field(
                description="Restrict results to one domain, e.g. 'example.com'."
            ),
        ] = None,
        workspace: WorkspaceParam = None,
        response_format: ResponseFormatParam = "markdown",
    ) -> str:
        """Scrape Google Search result pages for one or more queries.

        Use this to discover pages on the open web by topic; follow up with
        surfsense_web_crawl to read a result in full. Do NOT use it for
        Reddit, YouTube, or Google Maps research — the dedicated tools return
        richer data. Returns each query's parsed results: title, url, and
        snippet per organic result.
        Example: queries=['notebooklm review'], site='news.ycombinator.com'.
        """
        return await run_scraper(
            client,
            context,
            platform="google_search",
            verb="scrape",
            payload={
                "queries": queries,
                "max_pages_per_query": max_pages_per_query,
                "country_code": country_code,
                "language_code": language_code,
                "site": site,
            },
            workspace=workspace,
            response_format=response_format,
        )
