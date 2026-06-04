"""Backward-compatible shim.

Moved to ``app.agents.shared.tools.registry``. Re-exported here for the frozen
single-agent stack (``chat_deepagent``) until that stack is retired.
"""

from app.agents.shared.tools.registry import (
    BUILTIN_TOOLS,
    ToolDefinition,
    build_tools_async,
    get_connector_gated_tools,
)

__all__ = [
    "BUILTIN_TOOLS",
    "ToolDefinition",
    "build_tools_async",
    "get_connector_gated_tools",
]
