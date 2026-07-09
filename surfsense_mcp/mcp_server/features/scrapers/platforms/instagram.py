"""Instagram scraper tools: posts/reels, comments, and details."""

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
SearchType = Literal["hashtag", "profile", "place", "user"]
DetailSearchType = Literal["hashtag", "profile", "place"]


def register(
    mcp: FastMCP, client: SurfSenseClient, context: WorkspaceContext
) -> None:
    """Register the Instagram scrape, comments, and details tools."""

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
                description="Instagram URLs: a profile, post (/p/), reel "
                "(/reel/), hashtag (/explore/tags/), or place "
                "(/explore/locations/). Provide urls OR search_queries."
            ),
        ] = None,
        search_queries: Annotated[
            list[str] | None,
            Field(
                description="Terms to discover content for (hashtags as plain "
                "text, no '#'). Provide search_queries OR urls."
            ),
        ] = None,
        search_type: Annotated[
            SearchType, Field(description="What to discover from search_queries.")
        ] = "hashtag",
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
        hashtag or location feed, or discovering posts by keyword. For a post's
        comment section use surfsense_instagram_comments; for profile/hashtag/
        place metadata use surfsense_instagram_details. Returns per-item caption,
        likes, comments count, media URLs, and owner.
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
        name="surfsense_instagram_comments",
        title="Fetch Instagram comments",
        annotations=SCRAPE,
        structured_output=False,
    )
    async def instagram_comments(
        urls: Annotated[
            list[str],
            Field(
                min_length=1,
                description="Instagram post or reel URLs, e.g. "
                "['https://www.instagram.com/p/Cabc123/'].",
            ),
        ],
        max_comments_per_post: Annotated[
            int,
            Field(ge=1, le=50, description="Max comments per post (Instagram caps at 50)."),
        ] = 10,
        include_replies: Annotated[
            bool, Field(description="Include nested replies.")
        ] = False,
        newest_first: Annotated[
            bool, Field(description="Return newest comments first.")
        ] = False,
        max_items: Annotated[
            int, Field(ge=1, description="Max total comments across all posts.")
        ] = 20,
        workspace: WorkspaceParam = None,
        response_format: ResponseFormatParam = "markdown",
    ) -> str:
        """Fetch the comments (and optionally replies) on Instagram posts or reels.

        Use this when the user wants a post's discussion or audience reaction
        rather than the post itself; get post URLs from surfsense_instagram_scrape
        if you only have a topic or profile. Returns comment text, author, likes,
        and replies.
        Example: urls=['https://www.instagram.com/p/Cabc123/'], include_replies=True.
        """
        return await run_scraper(
            client,
            context,
            platform="instagram",
            verb="comments",
            payload={
                "urls": urls,
                "max_comments_per_post": max_comments_per_post,
                "include_replies": include_replies,
                "newest_first": newest_first,
                "max_items": max_items,
            },
            workspace=workspace,
            response_format=response_format,
        )

    @mcp.tool(
        name="surfsense_instagram_details",
        title="Fetch Instagram profile/hashtag/place details",
        annotations=SCRAPE,
        structured_output=False,
    )
    async def instagram_details(
        urls: Annotated[
            list[str] | None,
            Field(
                description="Profile, hashtag, or place URLs (or bare profile "
                "IDs). Provide urls OR search_queries."
            ),
        ] = None,
        search_queries: Annotated[
            list[str] | None,
            Field(
                description="Terms to discover profiles/hashtags/places for. "
                "Provide search_queries OR urls."
            ),
        ] = None,
        search_type: Annotated[
            DetailSearchType,
            Field(description="What to discover from search_queries."),
        ] = "hashtag",
        max_items: Annotated[
            int, Field(ge=1, description="Max detail items to return.")
        ] = 10,
        workspace: WorkspaceParam = None,
        response_format: ResponseFormatParam = "markdown",
    ) -> str:
        """Fetch Instagram profile, hashtag, or place metadata.

        Use this for entity lookups: a profile's follower/post counts and bio, a
        hashtag's post volume and top posts, or a place's coordinates and post
        count. For a feed of posts use surfsense_instagram_scrape instead. Each
        item carries a detailKind field marking whether it is a profile, hashtag,
        or place.
        Example: urls=['https://www.instagram.com/explore/tags/crossfit/'].
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
