"""Instagram scraper tools: posts/reels and profile details (anonymous-only)."""

from __future__ import annotations

from typing import Annotated, Literal

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from ....core.client import SurfSenseClient
from ....core.rendering import ResponseFormatParam
from ....core.workspace_context import WorkspaceContext, WorkspaceParam
from ..annotations import SCRAPE
from ..capability import run_scraper

ResultType = Literal["posts", "reels", "mentions"]
SearchType = Literal["profile", "user"]


def register(
    mcp: FastMCP, client: SurfSenseClient, context: WorkspaceContext
) -> None:
    """Register the Instagram scrape and details tools (anonymous-only)."""

    @mcp.tool(
        name="surfsense_instagram_scrape",
        title="Scrape Instagram posts or reels",
        annotations=SCRAPE,
        structured_output=False,
    )
    async def instagram_scrape(
        urls: Annotated[
            list[str] | None,
            Field(
                description="Instagram URLs: a profile, post (/p/), or reel "
                "(/reel/). Hashtag/place URLs are unsupported (login-walled). "
                "Provide urls OR search_queries."
            ),
        ] = None,
        search_queries: Annotated[
            list[str] | None,
            Field(
                description="Terms to discover public profiles for (resolved via "
                "Google). Provide search_queries OR urls."
            ),
        ] = None,
        search_type: Annotated[
            SearchType,
            Field(description="Discovery kind (profile-only)."),
        ] = "profile",
        result_type: Annotated[
            ResultType,
            Field(description="Which feed to return. 'mentions' needs profile URLs."),
        ] = "posts",
        max_items: Annotated[
            int, Field(ge=1, description="Maximum items to return across sources.")
        ] = 10,
        workspace: WorkspaceParam = None,
        response_format: ResponseFormatParam = "markdown",
    ) -> str:
        """Scrape public Instagram posts or reels from URLs or search queries.

        Use this for Instagram content research: a creator's recent posts, a
        single post/reel, or discovering public profiles by keyword. For a
        profile's metadata use surfsense_instagram_details. Returns per-item
        caption, likes, comments count, media URLs, and owner. Anonymous-only:
        hashtag/place feeds and comment threads are login-walled and unavailable.
        Example: urls=['https://www.instagram.com/natgeo/'], result_type='reels'.
        """
        return await run_scraper(
            client,
            context,
            platform="instagram",
            verb="scrape",
            payload={
                "urls": urls,
                "search_queries": search_queries,
                "search_type": search_type,
                "result_type": result_type,
                "max_items": max_items,
            },
            workspace=workspace,
            response_format=response_format,
        )

    @mcp.tool(
        name="surfsense_instagram_details",
        title="Fetch Instagram profile details",
        annotations=SCRAPE,
        structured_output=False,
    )
    async def instagram_details(
        urls: Annotated[
            list[str] | None,
            Field(
                description="Profile URLs (or bare profile IDs). Provide urls OR "
                "search_queries."
            ),
        ] = None,
        search_queries: Annotated[
            list[str] | None,
            Field(
                description="Terms to discover public profiles for. Provide "
                "search_queries OR urls."
            ),
        ] = None,
        search_type: Annotated[
            SearchType,
            Field(description="Discovery kind (profile-only)."),
        ] = "profile",
        max_items: Annotated[
            int, Field(ge=1, description="Max detail items to return.")
        ] = 10,
        workspace: WorkspaceParam = None,
        response_format: ResponseFormatParam = "markdown",
    ) -> str:
        """Fetch Instagram profile metadata.

        Use this for entity lookups: a profile's follower/post counts and bio.
        For a feed of posts use surfsense_instagram_scrape instead. Each item
        carries a detailKind field (always "profile"). Anonymous-only: hashtag
        and place details are login-walled and unavailable.
        Example: urls=['https://www.instagram.com/natgeo/'].
        """
        return await run_scraper(
            client,
            context,
            platform="instagram",
            verb="details",
            payload={
                "urls": urls,
                "search_queries": search_queries,
                "search_type": search_type,
                "max_items": max_items,
            },
            workspace=workspace,
            response_format=response_format,
        )
