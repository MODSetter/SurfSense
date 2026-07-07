"""Reddit scraper tool."""

from __future__ import annotations

from typing import Annotated, Literal

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from ....core.client import SurfSenseClient
from ....core.rendering import ResponseFormatParam
from ....core.workspace_context import WorkspaceContext, WorkspaceParam
from ..annotations import SCRAPE
from ..capability import run_scraper

RedditSort = Literal["relevance", "hot", "top", "new", "rising", "comments"]
RedditTime = Literal["hour", "day", "week", "month", "year", "all"]


def register(
    mcp: FastMCP, client: SurfSenseClient, context: WorkspaceContext
) -> None:
    """Register the Reddit tool."""

    @mcp.tool(
        name="surfsense_reddit_scrape",
        title="Search or scrape Reddit",
        annotations=SCRAPE,
        structured_output=False,
    )
    async def reddit_scrape(
        urls: Annotated[
            list[str] | None,
            Field(
                description="Reddit URLs: a post, a subreddit like "
                "'https://reddit.com/r/LocalLLaMA', a user page, or a search "
                "URL. Provide urls OR search_queries."
            ),
        ] = None,
        search_queries: Annotated[
            list[str] | None,
            Field(
                description="Terms to search Reddit for, e.g. "
                "['NotebookLM alternatives']. Provide search_queries OR urls."
            ),
        ] = None,
        community: Annotated[
            str | None,
            Field(
                description="Restrict a search to one subreddit, name without "
                "'r/', e.g. 'ArtificialInteligence'."
            ),
        ] = None,
        sort: Annotated[RedditSort, Field(description="Post ordering.")] = "new",
        time_filter: Annotated[
            RedditTime | None,
            Field(description="Time window; only valid with sort='top'."),
        ] = None,
        max_items: Annotated[
            int, Field(ge=1, description="Maximum posts to return.")
        ] = 10,
        skip_comments: Annotated[
            bool,
            Field(
                description="True fetches posts only (faster); False also "
                "fetches each post's comment thread."
            ),
        ] = False,
        workspace: WorkspaceParam = None,
        response_format: ResponseFormatParam = "markdown",
    ) -> str:
        """Search or scrape Reddit: posts, comments, subreddits, and users.

        Use this for ANY Reddit research — finding relevant subreddits or
        communities for a topic, top posts, or discussions — instead of a
        generic web search. Returns posts (title, text, score, subreddit, url)
        with comment threads unless skip_comments is set. Every post carries
        its subreddit, so to find communities for a topic, search posts and
        aggregate their subreddits.
        Example: search_queries=['NotebookLM'], sort='top', time_filter='month'.
        """
        return await run_scraper(
            client,
            context,
            platform="reddit",
            verb="scrape",
            payload={
                "urls": urls,
                "search_queries": search_queries,
                "community": community,
                "sort": sort,
                "time_filter": time_filter,
                "max_items": max_items,
                "skip_comments": skip_comments,
            },
            workspace=workspace,
            response_format=response_format,
        )
