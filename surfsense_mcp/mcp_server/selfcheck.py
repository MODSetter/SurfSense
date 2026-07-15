"""Offline smoke check: every tool registers with a usable name, doc, and schema.

Runs without a backend or network — it only assembles the server and inspects
the tool manifest the client would see. Fails loudly if a tool is missing, its
description is too thin to route on, or its input schema is malformed.
"""

from __future__ import annotations

import asyncio
import sys

from .config import Settings
from .server import build_server

EXPECTED_TOOLS = {
    # search-space selector
    "surfsense_list_workspaces",
    "surfsense_select_workspace",
    # scrapers (all platforms) + run history
    "surfsense_web_crawl",
    "surfsense_google_search",
    "surfsense_reddit_scrape",
    "surfsense_youtube_scrape",
    "surfsense_youtube_comments",
    "surfsense_tiktok_scrape",
    "surfsense_tiktok_comments",
    "surfsense_tiktok_user_search",
    "surfsense_tiktok_trending",
    "surfsense_google_maps_scrape",
    "surfsense_google_maps_reviews",
    "surfsense_instagram_scrape",
    "surfsense_instagram_details",
    "surfsense_indeed_scrape",
    "surfsense_list_scraper_runs",
    "surfsense_get_scraper_run",
    # knowledge-base management
    "surfsense_search_knowledge_base",
    "surfsense_list_documents",
    "surfsense_get_document",
    "surfsense_add_document",
    "surfsense_upload_file",
    "surfsense_update_document",
    "surfsense_delete_document",
}

_MIN_DESCRIPTION_CHARS = 40


async def _collect_tools() -> dict[str, object]:
    settings = Settings(
        base_url="http://localhost:8000",
        api_key="ss_pat_selfcheck",
        api_prefix="/api/v1",
        timeout=5.0,
        default_workspace=None,
        host="127.0.0.1",
        port=8080,
    )
    mcp, _client = build_server(settings)
    tools = await mcp.list_tools()
    return {tool.name: tool for tool in tools}


def run() -> list[str]:
    """Return a list of problems; empty means the manifest is healthy."""
    tools = asyncio.run(_collect_tools())
    problems: list[str] = []

    missing = EXPECTED_TOOLS - tools.keys()
    if missing:
        problems.append(f"missing tools: {sorted(missing)}")
    unexpected = tools.keys() - EXPECTED_TOOLS
    if unexpected:
        problems.append(f"unexpected tools: {sorted(unexpected)}")

    for name, tool in tools.items():
        description = tool.description or ""
        if len(description) < _MIN_DESCRIPTION_CHARS:
            problems.append(f"{name}: description too short to route on")
        schema = tool.inputSchema
        if not isinstance(schema, dict) or "properties" not in schema:
            problems.append(f"{name}: malformed input schema")
            continue
        for param, spec in schema["properties"].items():
            if not isinstance(spec, dict) or not spec.get("description"):
                problems.append(f"{name}: parameter '{param}' has no description")
    return problems


def main() -> None:
    problems = run()
    if problems:
        print("selfcheck FAILED:", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        sys.exit(1)
    print(f"selfcheck OK: {len(EXPECTED_TOOLS)} tools registered and well-formed")


if __name__ == "__main__":
    main()
