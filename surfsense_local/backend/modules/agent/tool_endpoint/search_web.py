"""The web search tool: a SearXNG server's results, as Add from the web searches."""

import asyncio
from typing import Any
from urllib.parse import urlsplit

from sqlalchemy.orm import Session

from modules.agent.tool_endpoint.tool import Tool, ToolCallError
from modules.agent.tool_endpoint.turn_scope import TurnScope
from modules.agent.tool_endpoint.web_reach import require_hosts
from modules.documents.web_sources.link_consent import WEB_SEARCH
from modules.documents.web_sources.web_search.search_rows import MAX_PAGES
from modules.documents.web_sources.web_search.search_server import search_server
from modules.documents.web_sources.web_search.searxng import (
    SearchFailedError,
    SearchUnreachableError,
    searxng_page,
)

TOOL_NAME = "search_web"
# As long as the dialog's box takes.
MAX_QUERY = 500

LISTING: dict[str, Any] = {
    "name": TOOL_NAME,
    "description": (
        "Search the web through a SearXNG server, for what the user's sources do "
        "not hold, such as recent facts. Returns each result's title, link and "
        "snippet. Read a result with surfsense_read_web_page, or a YouTube video's "
        "words with surfsense_read_youtube_transcript, before relying on it."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "What to search for, as typed into a search engine.",
            },
            "page": {
                "type": "integer",
                "description": f"The page of results, 1 to {MAX_PAGES}. Leave out for 1.",
            },
        },
        "required": ["query"],
    },
}


def _search(session: Session, scope: TurnScope, arguments: dict[str, Any]) -> str:
    query = str(arguments.get("query") or "").strip()[:MAX_QUERY]
    if not query:
        raise ToolCallError("Give a query to search for.")
    page = arguments.get("page")
    page = 1 if page is None else page
    if (
        not isinstance(page, int)
        or isinstance(page, bool)
        or not 1 <= page <= MAX_PAGES
    ):
        raise ToolCallError(f"page is a number from 1 to {MAX_PAGES}.")
    server = search_server(session)
    host = urlsplit(server).hostname or server
    require_hosts(session, [host], WEB_SEARCH)
    try:
        found = asyncio.run(searxng_page(server, query, page - 1))
    except SearchUnreachableError as error:
        raise ToolCallError(
            f"The search server at {host} could not be reached. Answer without the "
            "web, or try again later."
        ) from error
    except SearchFailedError as error:
        raise ToolCallError(
            f"The search server at {host} answered without searching. Answer "
            "without the web, or try again later."
        ) from error
    if not found:
        return f"No results for {query!r}."
    lines = [f"Page {page} of the results for {query!r}:"]
    for number, result in enumerate(found, start=1):
        lines.append(f"{number}. {result.title or result.url}\n   {result.url}")
        if result.description:
            lines.append(f"   {result.description}")
    if page < MAX_PAGES:
        lines.append(f"Call surfsense_{TOOL_NAME} again with page {page + 1} for more.")
    return "\n".join(lines)


# It waits on the network, holding no transaction meanwhile.
SEARCH_WEB = Tool(listing=LISTING, run=_search, waits=True)
