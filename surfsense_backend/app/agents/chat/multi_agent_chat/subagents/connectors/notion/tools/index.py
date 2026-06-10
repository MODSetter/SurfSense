"""``notion`` native tools and (empty) permission ruleset.

Tools self-gate via :func:`request_approval` in their bodies.
"""

from __future__ import annotations

from typing import Any

from langchain_core.tools import BaseTool

from app.agents.chat.multi_agent_chat.shared.permissions import Ruleset

from .create_page import create_create_notion_page_tool
from .delete_page import create_delete_notion_page_tool
from .update_page import create_update_notion_page_tool

NAME = "notion"

RULESET = Ruleset(origin=NAME, rules=[])


def load_tools(
    *, dependencies: dict[str, Any] | None = None, **kwargs: Any
) -> list[BaseTool]:
    d = {**(dependencies or {}), **kwargs}
    common = {
        "db_session": d["db_session"],
        "search_space_id": d["search_space_id"],
        "user_id": d["user_id"],
    }
    return [
        create_create_notion_page_tool(**common),
        create_update_notion_page_tool(**common),
        create_delete_notion_page_tool(**common),
    ]
