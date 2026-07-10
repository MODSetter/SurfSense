"""TikTok scraper tools: scrape (videos), comments, user search, and trending."""

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
    """Register the TikTok tools."""

    @mcp.tool(
        name="surfsense_tiktok_scrape",
        title="Scrape TikTok videos",
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
            Field(
                description="Keyword search terms. Returns no videos — use "
                "hashtags/profiles/urls for videos, or the user-search tool for "
                "accounts."
            ),
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
        """Scrape public TikTok videos by hashtag, profile, or URL.

        Use for TikTok video research — a creator's videos, a hashtag feed, or a
        specific video/profile/hashtag URL — instead of a generic web search.
        Returns videos with text, author, stats, music, and the web URL. For
        accounts by keyword use the user-search tool; keyword search returns no
        videos. Example: hashtags=['food'], max_items=20.
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

    @mcp.tool(
        name="surfsense_tiktok_comments",
        title="Scrape TikTok comments",
        annotations=SCRAPE,
        structured_output=False,
    )
    async def tiktok_comments(
        video_urls: Annotated[
            list[str],
            Field(
                description="TikTok video URLs "
                "('https://www.tiktok.com/@user/video/123') to pull comments from."
            ),
        ],
        comments_per_video: Annotated[
            int, Field(ge=1, description="Max comments to return per video.")
        ] = 20,
        max_items: Annotated[
            int, Field(ge=1, description="Maximum comments to return in total.")
        ] = 20,
        workspace: WorkspaceParam = None,
        response_format: ResponseFormatParam = "markdown",
    ) -> str:
        """Scrape the public comments of TikTok videos.

        Returns each comment's text, author, like count, and reply count (replies
        carry the parent comment id). Example: video_urls=['https://www.tiktok.com/
        @nasa/video/123'], max_items=50.
        """
        return await run_scraper(
            client,
            context,
            platform="tiktok",
            verb="comments",
            payload={
                "video_urls": video_urls,
                "comments_per_video": comments_per_video,
                "max_items": max_items,
            },
            workspace=workspace,
            response_format=response_format,
        )

    @mcp.tool(
        name="surfsense_tiktok_user_search",
        title="Search TikTok accounts",
        annotations=SCRAPE,
        structured_output=False,
    )
    async def tiktok_user_search(
        queries: Annotated[
            list[str],
            Field(
                description="Keywords to find TikTok accounts by, e.g. "
                "['nasa', 'cooking']."
            ),
        ],
        results_per_query: Annotated[
            int, Field(ge=1, description="Max accounts to return per query.")
        ] = 10,
        max_items: Annotated[
            int, Field(ge=1, description="Maximum accounts to return in total.")
        ] = 10,
        workspace: WorkspaceParam = None,
        response_format: ResponseFormatParam = "markdown",
    ) -> str:
        """Find public TikTok accounts by keyword.

        Returns matching profiles with name, followers, bio, and verification —
        the reliable account-discovery path (video search is login-walled).
        Example: queries=['space agency'], max_items=20.
        """
        return await run_scraper(
            client,
            context,
            platform="tiktok",
            verb="user_search",
            payload={
                "queries": queries,
                "results_per_query": results_per_query,
                "max_items": max_items,
            },
            workspace=workspace,
            response_format=response_format,
        )

    @mcp.tool(
        name="surfsense_tiktok_trending",
        title="Get trending TikTok videos",
        annotations=SCRAPE,
        structured_output=False,
    )
    async def tiktok_trending(
        max_items: Annotated[
            int,
            Field(ge=1, description="Max trending videos to return from Explore."),
        ] = 20,
        workspace: WorkspaceParam = None,
        response_format: ResponseFormatParam = "markdown",
    ) -> str:
        """Get the current trending TikTok videos from the Explore feed.

        No input needed beyond how many to return; each video comes with caption,
        author, stats, music, and its web URL. Example: max_items=30.
        """
        return await run_scraper(
            client,
            context,
            platform="tiktok",
            verb="trending",
            payload={"max_items": max_items},
            workspace=workspace,
            response_format=response_format,
        )
