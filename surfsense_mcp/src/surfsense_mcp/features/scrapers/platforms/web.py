"""Web crawl scraper tool."""

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
    """Register the web crawl tool."""

    @mcp.tool(
        name="surfsense_web_crawl",
        title="Crawl web pages",
        annotations=SCRAPE,
        structured_output=False,
    )
    async def web_crawl(
        start_urls: Annotated[
            list[str],
            Field(
                min_length=1,
                description="Full URLs to fetch, e.g. "
                "['https://example.com/blog/post'].",
            ),
        ],
        max_crawl_depth: Annotated[
            int,
            Field(
                ge=0,
                description="Link-hops to follow from start_urls within the "
                "same site. 0 fetches only start_urls.",
            ),
        ] = 0,
        max_crawl_pages: Annotated[
            int, Field(ge=1, description="Stop after this many pages in total.")
        ] = 10,
        max_length: Annotated[
            int, Field(ge=1, description="Max characters kept per page.")
        ] = 50_000,
        include_url_patterns: Annotated[
            list[str] | None,
            Field(
                description="Regexes; only discovered links matching one are "
                "followed, e.g. ['/docs/.*']."
            ),
        ] = None,
        exclude_url_patterns: Annotated[
            list[str] | None,
            Field(description="Regexes; discovered links matching one are skipped."),
        ] = None,
        workspace: WorkspaceParam = None,
        response_format: ResponseFormatParam = "markdown",
    ) -> str:
        """Fetch specific web pages and return their cleaned content as markdown.

        Use this to read a page the user names, or to spider a site from a
        starting URL. Do NOT use it to find pages on a topic — use
        surfsense_google_search for discovery. Returns one item per crawled
        page: url, title, and the page text as markdown.
        Example: start_urls=['https://blog.example.com'], max_crawl_depth=1,
        include_url_patterns=['/2026/'].
        """
        return await run_scraper(
            client,
            context,
            platform="web",
            verb="crawl",
            payload={
                "startUrls": start_urls,
                "maxCrawlDepth": max_crawl_depth,
                "maxCrawlPages": max_crawl_pages,
                "maxLength": max_length,
                "includeUrlPatterns": include_url_patterns,
                "excludeUrlPatterns": exclude_url_patterns,
            },
            workspace=workspace,
            response_format=response_format,
        )
