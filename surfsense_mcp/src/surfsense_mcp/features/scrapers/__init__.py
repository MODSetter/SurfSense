"""Scraper tools: one MCP surface per SurfSense platform capability.

Web crawl, Google Search, Reddit, YouTube, and Google Maps each get a tool that
maps a natural-language request to the workspace's scraper door. Two more tools
list and fetch past runs, so a large result truncated inline can be retrieved in
full later.
"""

from __future__ import annotations

from typing import Annotated, Literal

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import Field

from ...core.client import SurfSenseClient
from ...core.rendering import ResponseFormatParam, clip, to_json
from ...core.workspace_context import WorkspaceContext, WorkspaceParam
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

    @mcp.tool(
        name="surfsense_web_crawl",
        title="Crawl web pages",
        annotations=_SCRAPE,
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

    @mcp.tool(
        name="surfsense_google_search",
        title="Scrape Google Search",
        annotations=_SCRAPE,
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

    @mcp.tool(
        name="surfsense_reddit_scrape",
        title="Search or scrape Reddit",
        annotations=_SCRAPE,
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

    @mcp.tool(
        name="surfsense_youtube_scrape",
        title="Search or scrape YouTube",
        annotations=_SCRAPE,
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
        annotations=_SCRAPE,
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

    @mcp.tool(
        name="surfsense_google_maps_scrape",
        title="Find places on Google Maps",
        annotations=_SCRAPE,
        structured_output=False,
    )
    async def google_maps_scrape(
        search_queries: Annotated[
            list[str] | None,
            Field(
                description="Place searches, e.g. ['coffee shops']. Provide "
                "search_queries OR urls OR place_ids."
            ),
        ] = None,
        urls: Annotated[
            list[str] | None,
            Field(description="Google Maps URLs of specific places."),
        ] = None,
        place_ids: Annotated[
            list[str] | None,
            Field(description="Google place ids, e.g. ['ChIJj61dQgK6j4AR...']."),
        ] = None,
        location: Annotated[
            str | None,
            Field(
                description="Geographic scope for a search, e.g. "
                "'Seattle, USA'."
            ),
        ] = None,
        max_places: Annotated[
            int, Field(ge=1, description="Maximum places to return.")
        ] = 10,
        include_details: Annotated[
            bool,
            Field(
                description="True adds opening hours and extra contact info "
                "(slower)."
            ),
        ] = False,
        workspace: WorkspaceParam = None,
        response_format: ResponseFormatParam = "markdown",
    ) -> str:
        """Find places on Google Maps by search, URL, or place id.

        Use this for local-business and location research: names, addresses,
        ratings, categories, coordinates, place ids. For a place's customer
        reviews use surfsense_google_maps_reviews instead.
        Example: search_queries=['ramen'], location='Osaka, Japan', max_places=5.
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
        title="Fetch Google Maps reviews",
        annotations=_SCRAPE,
        structured_output=False,
    )
    async def google_maps_reviews(
        urls: Annotated[
            list[str] | None,
            Field(
                description="Google Maps URLs of places. Provide urls OR "
                "place_ids."
            ),
        ] = None,
        place_ids: Annotated[
            list[str] | None,
            Field(
                description="Google place ids from surfsense_google_maps_scrape."
            ),
        ] = None,
        max_reviews: Annotated[
            int, Field(ge=1, description="Maximum reviews per place.")
        ] = 20,
        sort_by: Annotated[
            ReviewSort, Field(description="Review ordering.")
        ] = "newest",
        language: Annotated[
            str, Field(description="Reviews language code, e.g. 'en'.")
        ] = "en",
        start_date: Annotated[
            str | None,
            Field(
                description="ISO date like '2026-01-01'; keeps only reviews on "
                "or after that day."
            ),
        ] = None,
        workspace: WorkspaceParam = None,
        response_format: ResponseFormatParam = "markdown",
    ) -> str:
        """Fetch customer reviews for Google Maps places by URL or place id.

        Use this to read feedback on specific places; get urls or place_ids
        from surfsense_google_maps_scrape first if you only have a name.
        Returns review text, rating, author, and date per review.
        Example: place_ids=['ChIJj61dQgK6j4AR...'], sort_by='newest'.
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
        title="List past scraper runs",
        annotations=_READ_RUNS,
        structured_output=False,
    )
    async def list_scraper_runs(
        limit: Annotated[
            int, Field(ge=1, description="Maximum runs to list.")
        ] = 20,
        capability: Annotated[
            str | None,
            Field(
                description="Filter by capability slug, e.g. 'web.crawl' or "
                "'reddit.scrape'."
            ),
        ] = None,
        status: Annotated[
            str | None,
            Field(description="Filter by run status: 'success' or 'error'."),
        ] = None,
        workspace: WorkspaceParam = None,
        response_format: ResponseFormatParam = "markdown",
    ) -> str:
        """List recent scraper runs in the workspace, newest first.

        Use this to find the run_id of an earlier scrape — for example when an
        inline result was truncated — then fetch it in full with
        surfsense_get_scraper_run. Returns each run's id, capability, status,
        item count, and creation time.
        Example: capability='reddit.scrape', status='success'.
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
        title="Fetch one scraper run in full",
        annotations=_READ_RUNS,
        structured_output=False,
    )
    async def get_scraper_run(
        run_id: Annotated[
            str,
            Field(
                description="Run id from surfsense_list_scraper_runs or a "
                "prior scrape's output."
            ),
        ],
        workspace: WorkspaceParam = None,
        response_format: ResponseFormatParam = "markdown",
    ) -> str:
        """Fetch a single scraper run in full, including its stored output.

        Use this to retrieve the complete, untruncated result of an earlier
        scrape. Do NOT re-run a scraper just to recover a truncated result —
        fetch the stored run instead.
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
