"""Scraper tools: one MCP surface per SurfSense platform capability.

Web crawl, Google Search, Reddit, YouTube, and Google Maps each get a tool that
maps a natural-language request to the workspace's scraper door. Two more tools
list and fetch past runs, so a large result truncated inline can be retrieved in
full later.
"""

from __future__ import annotations

from typing import Literal

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from ...core.client import SurfSenseClient
from ...core.rendering import ResponseFormat, clip, to_json
from ...core.workspace_context import WorkspaceContext
from .capability import run_scraper

# Scrapers reach the open web and record a billable run; they are neither
# read-only nor idempotent, but they do not mutate the knowledge base.
_SCRAPE = ToolAnnotations(
    readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=True
)
_READ_RUNS = ToolAnnotations(
    readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False
)

RedditSort = Literal["relevance", "hot", "top", "new", "rising", "comments"]
RedditTime = Literal["hour", "day", "week", "month", "year", "all"]
CommentSort = Literal["TOP_COMMENTS", "NEWEST_FIRST"]
ReviewSort = Literal["newest", "mostRelevant", "highestRanking", "lowestRanking"]


def register(
    mcp: FastMCP, client: SurfSenseClient, context: WorkspaceContext
) -> None:
    """Register the scraper and run-history tools on the server."""

    @mcp.tool(name="surfsense_web_crawl", annotations=_SCRAPE, structured_output=False)
    async def web_crawl(
        start_urls: list[str],
        max_crawl_depth: int = 0,
        max_crawl_pages: int = 10,
        max_length: int = 50_000,
        include_url_patterns: list[str] | None = None,
        exclude_url_patterns: list[str] | None = None,
        workspace: str | None = None,
        response_format: ResponseFormat = "markdown",
    ) -> str:
        """Crawl web pages and return their cleaned content as markdown.

        Use this to read one page or spider a site. With max_crawl_depth=0 only
        start_urls are fetched; a higher depth follows same-site links up to
        max_crawl_pages. include/exclude_url_patterns are regexes that narrow
        which discovered links are followed.
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

    @mcp.tool(
        name="surfsense_google_search", annotations=_SCRAPE, structured_output=False
    )
    async def google_search(
        queries: list[str],
        max_pages_per_query: int = 1,
        country_code: str | None = None,
        language_code: str = "",
        site: str | None = None,
        workspace: str | None = None,
        response_format: ResponseFormat = "markdown",
    ) -> str:
        """Scrape Google Search results for one or more queries.

        Use this to find pages on the web. Each item is a query's fetched result
        page. Pass full Google Search URLs to scrape them as-is, or plain terms
        to search. Optionally scope to a country, language, or single domain.
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

    @mcp.tool(
        name="surfsense_reddit_scrape", annotations=_SCRAPE, structured_output=False
    )
    async def reddit_scrape(
        urls: list[str] | None = None,
        search_queries: list[str] | None = None,
        community: str | None = None,
        sort: RedditSort = "new",
        time_filter: RedditTime | None = None,
        max_items: int = 10,
        skip_comments: bool = False,
        workspace: str | None = None,
        response_format: ResponseFormat = "markdown",
    ) -> str:
        """Scrape Reddit posts and comments from URLs or a search.

        Provide urls (a post, /r/subreddit, /user/name, or search URL) OR
        search_queries; scope a search to one subreddit with community. Use
        time_filter only with sort='top'. Set skip_comments to fetch posts only.
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

    @mcp.tool(
        name="surfsense_youtube_scrape", annotations=_SCRAPE, structured_output=False
    )
    async def youtube_scrape(
        urls: list[str] | None = None,
        search_queries: list[str] | None = None,
        max_results: int = 10,
        download_subtitles: bool = False,
        subtitles_language: str = "en",
        workspace: str | None = None,
        response_format: ResponseFormat = "markdown",
    ) -> str:
        """Scrape YouTube videos from URLs or a search.

        Provide urls (video, channel, playlist, shorts, or hashtag pages) OR
        search_queries. Set download_subtitles to also fetch each video's
        transcript in subtitles_language.
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
        name="surfsense_youtube_comments", annotations=_SCRAPE, structured_output=False
    )
    async def youtube_comments(
        urls: list[str],
        max_comments: int = 20,
        sort_by: CommentSort = "NEWEST_FIRST",
        workspace: str | None = None,
        response_format: ResponseFormat = "markdown",
    ) -> str:
        """Fetch comments (and replies) for one or more YouTube videos.

        Use this when the user wants a video's discussion rather than the video
        itself. max_comments counts top-level comments and replies together.
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

    @mcp.tool(
        name="surfsense_google_maps_scrape",
        annotations=_SCRAPE,
        structured_output=False,
    )
    async def google_maps_scrape(
        search_queries: list[str] | None = None,
        urls: list[str] | None = None,
        place_ids: list[str] | None = None,
        location: str | None = None,
        max_places: int = 10,
        include_details: bool = False,
        workspace: str | None = None,
        response_format: ResponseFormat = "markdown",
    ) -> str:
        """Scrape places from Google Maps by search, URL, or place id.

        Provide search_queries OR urls OR place_ids. Scope a search with
        location (e.g. 'New York, USA'). Set include_details for opening hours
        and extra contact info (slower).
        """
        return await run_scraper(
            client,
            context,
            platform="google_maps",
            verb="scrape",
            payload={
                "search_queries": search_queries,
                "urls": urls,
                "place_ids": place_ids,
                "location": location,
                "max_places": max_places,
                "include_details": include_details,
            },
            workspace=workspace,
            response_format=response_format,
        )

    @mcp.tool(
        name="surfsense_google_maps_reviews",
        annotations=_SCRAPE,
        structured_output=False,
    )
    async def google_maps_reviews(
        urls: list[str] | None = None,
        place_ids: list[str] | None = None,
        max_reviews: int = 20,
        sort_by: ReviewSort = "newest",
        language: str = "en",
        start_date: str | None = None,
        workspace: str | None = None,
        response_format: ResponseFormat = "markdown",
    ) -> str:
        """Fetch reviews for Google Maps places by URL or place id.

        Provide urls OR place_ids. start_date (ISO, e.g. '2024-01-01') keeps only
        reviews on or after that day.
        """
        return await run_scraper(
            client,
            context,
            platform="google_maps",
            verb="reviews",
            payload={
                "urls": urls,
                "place_ids": place_ids,
                "max_reviews": max_reviews,
                "sort_by": sort_by,
                "language": language,
                "start_date": start_date,
            },
            workspace=workspace,
            response_format=response_format,
        )

    @mcp.tool(
        name="surfsense_list_scraper_runs",
        annotations=_READ_RUNS,
        structured_output=False,
    )
    async def list_scraper_runs(
        limit: int = 20,
        capability: str | None = None,
        status: str | None = None,
        workspace: str | None = None,
        response_format: ResponseFormat = "markdown",
    ) -> str:
        """List recent scraper runs for the workspace, newest first.

        Use this to find a run_id to fetch in full with surfsense_get_scraper_run,
        e.g. when an inline result was truncated. Optionally filter by capability
        (like 'web.crawl') or status ('success' / 'error').
        """
        resolved = await context.resolve(workspace)
        runs = await client.request(
            "GET",
            f"/workspaces/{resolved.id}/scrapers/runs",
            params={
                "limit": limit,
                "capability": capability,
                "status": status,
            },
        )
        if response_format == "json":
            return to_json(runs)
        return _render_runs(runs)

    @mcp.tool(
        name="surfsense_get_scraper_run",
        annotations=_READ_RUNS,
        structured_output=False,
    )
    async def get_scraper_run(
        run_id: str,
        workspace: str | None = None,
        response_format: ResponseFormat = "markdown",
    ) -> str:
        """Fetch a single scraper run in full, including its stored output.

        Use this to retrieve the complete result of an earlier scrape (its
        run_id comes from surfsense_list_scraper_runs or a prior scrape).
        """
        resolved = await context.resolve(workspace)
        run = await client.request(
            "GET", f"/workspaces/{resolved.id}/scrapers/runs/{run_id}"
        )
        if response_format == "json":
            return clip(to_json(run))
        return f"# Run {run.get('id', run_id)}\n\n```json\n{clip(to_json(run))}\n```"


def _render_runs(runs: list[dict] | None) -> str:
    if not runs:
        return "No scraper runs found."
    lines = ["# Scraper runs", ""]
    for run in runs:
        lines.append(
            f"- **{run.get('id')}** — {run.get('capability')} · {run.get('status')} · "
            f"{run.get('item_count', 0)} item(s) · {run.get('created_at')}"
        )
    return "\n".join(lines)
