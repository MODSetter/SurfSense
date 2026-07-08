"""TikTok scraper tool."""

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
    """Register the TikTok tool."""

    @mcp.tool(
        name="surfsense_tiktok_scrape",
        title="Search or scrape TikTok",
        annotations=SCRAPE,
        structured_output=False,
    )
    async def tiktok_scrape(
        urls: Annotated[
            list[str] | None,
            Field(
                description="TikTok URLs: a video, a profile "
                "('https://www.tiktok.com/@nasa'), a hashtag "
                "('https://www.tiktok.com/tag/food'), or a search URL. Provide "
                "urls OR profiles/hashtags/search_queries."
            ),
        ] = None,
        profiles: Annotated[
            list[str] | None,
            Field(
                description="Profile usernames to scrape, with or without a "
                "leading '@', e.g. ['nasa']."
            ),
        ] = None,
        hashtags: Annotated[
            list[str] | None,
            Field(
                description="Hashtag names to scrape, without the '#', e.g. "
                "['food']."
            ),
        ] = None,
        search_queries: Annotated[
            list[str] | None,
            Field(description="Terms to search TikTok for, e.g. ['cooking']."),
        ] = None,
        results_per_page: Annotated[
            int,
            Field(ge=1, description="Max videos per profile/hashtag/search target."),
        ] = 10,
        max_items: Annotated[
            int, Field(ge=1, description="Maximum videos to return in total.")
        ] = 10,
        workspace: WorkspaceParam = None,
        response_format: ResponseFormatParam = "markdown",
    ) -> str:
        """Search or scrape public TikTok videos.

        Use this for ANY TikTok research — a creator's videos, a hashtag feed,
        a search, or a specific video URL — instead of a generic web search.
        Returns videos with text, author, stats, music, and the web URL.
        Example: hashtags=['food'], max_items=20.
        """
        return await run_scraper(
            client,
            context,
            platform="tiktok",
            verb="scrape",
            payload={
                "urls": urls,
                "profiles": profiles,
                "hashtags": hashtags,
                "search_queries": search_queries,
                "results_per_page": results_per_page,
                "max_items": max_items,
            },
            workspace=workspace,
            response_format=response_format,
        )
