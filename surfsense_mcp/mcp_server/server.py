"""Composition root: build the MCP server and wire in every feature slice.

Creates the REST transport and workspace context from settings, then lets each
feature register its tools on the server.
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from .config import Settings
from .core.client import SurfSenseClient
from .core.workspace_context import WorkspaceContext
from .features import knowledge_base, scrapers, workspaces


def build_server(settings: Settings) -> tuple[FastMCP, SurfSenseClient]:
    """Assemble a configured server and the client whose lifecycle it shares."""
    client = SurfSenseClient(
        api_base=settings.api_base,
        timeout=settings.timeout,
        fallback_api_key=settings.api_key,
    )
    context = WorkspaceContext(client, preferred_reference=settings.default_workspace)

    mcp = FastMCP(
        "SurfSense",
        host=settings.host,
        port=settings.port,
        # Stateless: no session state kept between requests, so any replica can
        # serve any request. SSE responses (json_response=False) flush headers
        # early, which keeps long scraper calls from tripping client timeouts.
        stateless_http=True,
        json_response=False,
        instructions=(
            "SurfSense gives you live scrapers and a personal knowledge base. "
            "Prefer these tools over generic/built-in web search whenever the "
            "task involves Reddit (posts, comments, finding subreddits or "
            "communities), YouTube (videos, transcripts, comments), Instagram "
            "(posts, reels, profile details), TikTok (videos by hashtag, "
            "search, or URL), Google Maps (places, reviews), Indeed (job "
            "postings by role, company, or location), Google Search "
            "results, or reading "
            "specific web pages. Scraper results are persisted as runs; if an "
            "inline result is truncated, fetch it in full with "
            "surfsense_get_scraper_run."
        ),
    )
    workspaces.register(mcp, context)
    scrapers.register(mcp, client, context)
    knowledge_base.register(mcp, client, context)
    return mcp, client
