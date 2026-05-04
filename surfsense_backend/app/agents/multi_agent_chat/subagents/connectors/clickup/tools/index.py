from __future__ import annotations

from typing import Any

from app.agents.multi_agent_chat.subagents.shared.permissions import (
    ToolsPermissions,
)


def load_tools(*, dependencies: dict[str, Any] | None = None, **kwargs: Any) -> ToolsPermissions:
    _ = {**(dependencies or {}), **kwargs}
    return {"allow": [], "ask": []}
