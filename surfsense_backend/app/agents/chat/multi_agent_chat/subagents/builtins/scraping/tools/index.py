"""``scraping`` sub-agent tools: scraper capability verbs + chat-watch controls."""

from __future__ import annotations

from typing import Any

from langchain_core.tools import BaseTool

from app.agents.chat.multi_agent_chat.shared.permissions import Ruleset
from app.capabilities.core.access.agent import build_capability_tools
from app.capabilities.web.discover.definition import WEB_DISCOVER
from app.capabilities.web.scrape.definition import WEB_SCRAPE
from app.capabilities.youtube.comments.definition import YOUTUBE_COMMENTS
from app.capabilities.youtube.scrape.definition import YOUTUBE_SCRAPE

from .refresh_watch import create_refresh_watch_tool
from .start_watch import create_start_watch_tool
from .stop_watch import create_stop_watch_tool

NAME = "scraping"

RULESET = Ruleset(origin=NAME, rules=[])

_CI_VERBS = [WEB_DISCOVER, WEB_SCRAPE, YOUTUBE_SCRAPE, YOUTUBE_COMMENTS]


def load_tools(
    *, dependencies: dict[str, Any] | None = None, **kwargs: Any
) -> list[BaseTool]:
    d = {**(dependencies or {}), **kwargs}
    tools: list[BaseTool] = build_capability_tools(
        workspace_id=d.get("workspace_id"),
        capabilities=_CI_VERBS,
    )

    # Watch tools bind a recurring automation to the current chat, so they are
    # only offered when we have a chat to bind to and auth to manage it.
    thread_id = d.get("thread_id")
    auth_context = d.get("auth_context")
    if thread_id is not None and auth_context is not None:
        binding = {
            "workspace_id": d.get("workspace_id"),
            "thread_id": thread_id,
            "auth_context": auth_context,
        }
        tools.append(create_start_watch_tool(**binding))
        tools.append(create_stop_watch_tool(**binding))
        tools.append(create_refresh_watch_tool(**binding))

    return tools
