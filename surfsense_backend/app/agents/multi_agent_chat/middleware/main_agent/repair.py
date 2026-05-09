"""Repair miscased / unknown tool names to the registered set or invalid_tool."""

from __future__ import annotations

from collections.abc import Sequence

from langchain_core.tools import BaseTool

from app.agents.new_chat.feature_flags import AgentFeatureFlags
from app.agents.new_chat.middleware import ToolCallNameRepairMiddleware

from ..shared.flags import enabled

# deepagents-built-in tool names the repair pass treats as known.
_DEEPAGENT_BUILTIN_TOOL_NAMES: frozenset[str] = frozenset(
    {
        "write_todos",
        "ls",
        "read_file",
        "write_file",
        "edit_file",
        "glob",
        "grep",
        "execute",
        "task",
        "mkdir",
        "cd",
        "pwd",
        "move_file",
        "rm",
        "rmdir",
        "list_tree",
        "execute_code",
    }
)


def build_repair_mw(
    *,
    flags: AgentFeatureFlags,
    tools: Sequence[BaseTool],
) -> ToolCallNameRepairMiddleware | None:
    if not enabled(flags, "enable_tool_call_repair"):
        return None
    registered_names: set[str] = {t.name for t in tools}
    registered_names |= _DEEPAGENT_BUILTIN_TOOL_NAMES
    return ToolCallNameRepairMiddleware(
        registered_tool_names=registered_names,
        fuzzy_match_threshold=None,
    )
