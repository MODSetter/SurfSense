"""``memory`` native tools and (empty) permission ruleset."""

from __future__ import annotations

from typing import Any

from langchain_core.tools import BaseTool

from app.agents.chat.multi_agent_chat.shared.permissions import Ruleset
from app.db import ChatVisibility

from .update_memory import create_update_memory_tool, create_update_team_memory_tool

NAME = "memory"

RULESET = Ruleset(origin=NAME, rules=[])


def load_tools(
    *, dependencies: dict[str, Any] | None = None, **kwargs: Any
) -> list[BaseTool]:
    d = {**(dependencies or {}), **kwargs}
    if d.get("thread_visibility") == ChatVisibility.SEARCH_SPACE:
        return [
            create_update_team_memory_tool(
                search_space_id=d["search_space_id"],
                db_session=d["db_session"],
                llm=d.get("llm"),
            )
        ]
    return [
        create_update_memory_tool(
            user_id=d["user_id"],
            db_session=d["db_session"],
            llm=d.get("llm"),
        )
    ]
