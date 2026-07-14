"""YouTube scraper tools: videos and comments."""

from __future__ import annotations

from typing import Annotated, Literal

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from ....core.client import SurfSenseClient
from ....core.rendering import ResponseFormatParam
from ....core.workspace_context import WorkspaceContext, WorkspaceParam
from ..annotations import SCRAPE
from ..capability import run_scraper

CommentSort = Literal["TOP_COMMENTS", "NEWEST_FIRST"]


def register(mcp: FastMCP, client: SurfSenseClient, context: WorkspaceContext) -> None:
    """Register the YouTube video and comment tools."""

    @mcp.tool(
        name="surfsense_youtube_scrape",
        title="Search or scrape YouTube",
        annotations=SCRAPE,
        structured_output=False,
    )
    async def youtube_scrape(
        urls: Annotated[
            list[str] | None,
            Field(
                description="YouTube URLs: video, channel, playlist, shorts, "
                "or hashtag pages. Provide urls OR search_queries."
            ),
        ] = None,
        search_queries: Annotated[
            list[str] | None,
            Field(
                description="Terms to search YouTube for, e.g. "
                "['NotebookLM tutorial']. Provide search_queries OR urls."
            ),
        ] = None,
        max_results: Annotated[
            int, Field(ge=1, description="Maximum videos to return.")
        ] = 10,
        download_subtitles: Annotated[
            bool,
            Field(description="True also fetches each video's transcript."),
        ] = False,
        subtitles_language: Annotated[
            str, Field(description="Transcript language code, e.g. 'en'.")
        ] = "en",
        workspace: WorkspaceParam = None,
        response_format: ResponseFormatParam = "markdown",
    ) -> str:
        """Search or scrape YouTube videos, optionally with transcripts.

        Use this for YouTube research: finding videos on a topic, or reading a
        video's details or transcript. For a video's comment section use
        surfsense_youtube_comments instead. Returns per-video metadata (title,
        channel, views, description, url) and, if requested, the transcript.
        Example: search_queries=['NotebookLM tutorial'], download_subtitles=True.
        """
        return await run_scraper(
            client,
            context,
            platform="youtube",
            verb="scrape",
            payload={
                "urls": urls,
                "search_queries": search_queries,
                "max_results": max_results,
                "download_subtitles": download_subtitles,
                "subtitles_language": subtitles_language,
            },
            workspace=workspace,
            response_format=response_format,
        )

    @mcp.tool(
        name="surfsense_youtube_comments",
        title="Fetch YouTube comments",
        annotations=SCRAPE,
        structured_output=False,
    )
    async def youtube_comments(
        urls: Annotated[
            list[str],
            Field(
                min_length=1,
                description="YouTube video URLs, e.g. "
                "['https://www.youtube.com/watch?v=abc123'].",
            ),
        ],
        max_comments: Annotated[
            int,
            Field(
                ge=1,
                description="Maximum comments per video, counting top-level "
                "comments and replies together.",
            ),
        ] = 20,
        sort_by: Annotated[
            CommentSort, Field(description="Comment ordering.")
        ] = "NEWEST_FIRST",
        workspace: WorkspaceParam = None,
        response_format: ResponseFormatParam = "markdown",
    ) -> str:
        """Fetch the comments (and replies) on one or more YouTube videos.

        Use this when the user wants a video's discussion or audience reaction
        rather than the video itself; get video URLs from
        surfsense_youtube_scrape if you only have a topic. Returns comment
        text, author, likes, and replies.
        Example: urls=['https://www.youtube.com/watch?v=abc123'], max_comments=50.
        """
        return await run_scraper(
            client,
            context,
            platform="youtube",
            verb="comments",
            payload={
                "urls": urls,
                "max_comments": max_comments,
                "sort_by": sort_by,
            },
            workspace=workspace,
            response_format=response_format,
        )
