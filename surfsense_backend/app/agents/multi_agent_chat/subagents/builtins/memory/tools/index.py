from __future__ import annotations

from typing import Any

from app.agents.multi_agent_chat.subagents.shared.permissions import (
    ToolsPermissions,
)
from app.db import ChatVisibility

from .update_memory import create_update_memory_tool, create_update_team_memory_tool


def load_tools(*, dependencies: dict[str, Any] | None = None, **kwargs: Any) -> ToolsPermissions:
    resolved_dependencies = {**(dependencies or {}), **kwargs}
    if resolved_dependencies.get("thread_visibility") == ChatVisibility.SEARCH_SPACE:
        mem = create_update_team_memory_tool(
            search_space_id=resolved_dependencies["search_space_id"],
            db_session=resolved_dependencies["db_session"],
            llm=resolved_dependencies.get("llm"),
        )
        return {"allow": [{"name": getattr(mem, "name", "") or "", "tool": mem}], "ask": []}
    mem = create_update_memory_tool(
        user_id=resolved_dependencies["user_id"],
        db_session=resolved_dependencies["db_session"],
        llm=resolved_dependencies.get("llm"),
    )
    return {"allow": [{"name": getattr(mem, "name", "") or "", "tool": mem}], "ask": []}
