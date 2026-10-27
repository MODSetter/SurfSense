"""SurfSense's scraper plugins stood in on one local plugin host, answering with recorded items."""

import inspect
from collections.abc import AsyncIterator, Callable
from contextlib import AsyncExitStack, asynccontextmanager
from dataclasses import dataclass
from typing import Any

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp_types import CallToolResult, TextContent
from starlette.applications import Starlette
from starlette.routing import Mount
from starlette.types import ASGIApp

# Each call a stand-in got: (plugin id, tool, arguments).
Calls = list[tuple[str, str, dict[str, Any]]]
# A tool's answer to its arguments: items, or a ToolError raised.
Answer = Callable[[dict[str, Any]], list[dict[str, Any]]]


@dataclass(frozen=True)
class Tool:
    """The arguments a real tool takes, all optional here, and what the stand-in answers."""

    params: tuple[str, ...]
    answer: Answer


def stand_in(plugin_id: str, tools: dict[str, Tool], calls: Calls) -> MCPServer:
    """A plugin whose tools record each call and answer as `tools` says."""
    server = MCPServer(plugin_id)
    for name, tool in tools.items():
        server.add_tool(_tool(plugin_id, name, tool, calls), name=name)
    return server


def plugin_host(
    servers: dict[str, MCPServer], around: Callable[[ASGIApp], ASGIApp]
) -> Starlette:
    """Every plugin at `/<id>/mcp`, each behind `around`, as the host's license check."""

    @asynccontextmanager
    async def lifespan(_: Starlette) -> AsyncIterator[None]:
        async with AsyncExitStack() as stack:
            for server in servers.values():
                await stack.enter_async_context(server.session_manager.run())
            yield

    return Starlette(
        routes=[
            Mount(f"/{plugin_id}", app=around(server.streamable_http_app()))
            for plugin_id, server in servers.items()
        ],
        lifespan=lifespan,
    )


def refusing(message: str) -> Answer:
    """A tool that ran and failed, as Web Crawl does when no page could be read."""

    def answer(_: dict[str, Any]) -> list[dict[str, Any]]:
        raise ToolError(message)

    return answer


def _tool(
    plugin_id: str, name: str, tool: Tool, calls: Calls
) -> Callable[..., CallToolResult]:
    def tool_function(**arguments: Any) -> CallToolResult:
        sent = {key: value for key, value in arguments.items() if value is not None}
        calls.append((plugin_id, name, sent))
        return CallToolResult(
            content=[TextContent(type="text", text="done")],
            structured_content={"items": tool.answer(sent)},
        )

    # The SDK reads a tool's schema off its signature, so the stand-in names each argument.
    tool_function.__name__ = name
    tool_function.__signature__ = inspect.Signature(  # type: ignore[attr-defined]
        [
            inspect.Parameter(param, inspect.Parameter.KEYWORD_ONLY, default=None)
            for param in tool.params
        ],
        return_annotation=CallToolResult,
    )
    tool_function.__annotations__ = {"return": CallToolResult} | dict.fromkeys(
        tool.params, Any
    )
    return tool_function


# The arguments each real tool takes, read off backend/plugins/proprietary/*/server.py:
# a puller that sends one the real tool does not take fails here too.
REAL_PARAMS: dict[tuple[str, str], tuple[str, ...]] = {
    ("google-search", "scrape"): (
        "queries",
        "max_pages_per_query",
        "country_code",
        "language_code",
        "site",
    ),
    ("web-crawl", "crawl"): (
        "start_urls",
        "max_crawl_depth",
        "max_crawl_pages",
        "max_length",
        "max_links",
        "include_url_patterns",
        "exclude_url_patterns",
    ),
    ("youtube", "scrape"): (
        "urls",
        "search_queries",
        "max_results",
        "download_subtitles",
        "subtitles_language",
    ),
    ("youtube", "comments"): ("urls", "max_comments", "sort_by"),
    ("tiktok", "scrape"): (
        "urls",
        "profiles",
        "hashtags",
        "results_per_page",
        "max_items",
    ),
    ("tiktok", "comments"): ("video_urls", "comments_per_video", "max_items"),
    ("google-maps", "scrape"): (
        "search_queries",
        "urls",
        "place_ids",
        "location",
        "max_places",
        "language",
        "include_details",
        "max_reviews",
        "max_images",
    ),
    ("google-maps", "reviews"): (
        "urls",
        "place_ids",
        "max_reviews",
        "sort_by",
        "language",
        "start_date",
    ),
    ("amazon", "scrape"): (
        "urls",
        "search_terms",
        "max_items",
        "domain",
        "language",
        "country_code",
        "zip_code",
        "include_details",
        "max_offers",
        "include_sellers",
        "max_variants",
        "include_variant_prices",
    ),
    ("walmart", "scrape"): (
        "urls",
        "search_terms",
        "max_items",
        "include_details",
        "include_reviews_sample",
    ),
    ("walmart", "reviews"): ("urls", "item_ids", "max_reviews", "sort_by"),
    ("indeed", "scrape"): (
        "urls",
        "search_queries",
        "country",
        "location",
        "radius",
        "job_type",
        "level",
        "remote",
        "from_days",
        "sort",
        "scrape_job_details",
        "max_items",
        "max_items_per_query",
    ),
    ("reddit", "scrape"): (
        "urls",
        "search_queries",
        "community",
        "sort",
        "time_filter",
        "include_nsfw",
        "skip_comments",
        "max_items",
        "max_posts",
        "max_comments",
        "post_date_limit",
        "comment_date_limit",
    ),
    ("instagram", "scrape"): (
        "urls",
        "search_queries",
        "search_type",
        "result_type",
        "newer_than",
        "skip_pinned_posts",
        "max_per_target",
        "max_items",
    ),
    ("instagram", "details"): (
        "urls",
        "search_queries",
        "search_type",
        "search_limit",
        "max_items",
    ),
}


def every_plugin(
    answers: dict[tuple[str, str], Answer], calls: Calls
) -> dict[str, MCPServer]:
    """Each real tool, answering as `answers` says, or with no items."""
    tools: dict[str, dict[str, Tool]] = {}
    for (plugin_id, name), params in REAL_PARAMS.items():
        answer = answers.get((plugin_id, name), lambda _: [])
        tools.setdefault(plugin_id, {})[name] = Tool(params, answer)
    return {
        plugin_id: stand_in(plugin_id, named, calls)
        for plugin_id, named in tools.items()
    }
