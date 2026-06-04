"""Backward-compatible shim.

Moved to ``app.agents.shared.tools.invalid_tool``. Re-exported here for the
frozen single-agent stack (``chat_deepagent``) until that stack is retired.
"""

from app.agents.shared.tools.invalid_tool import (
    INVALID_TOOL_DESCRIPTION,
    INVALID_TOOL_NAME,
    invalid_tool,
)

__all__ = [
    "INVALID_TOOL_DESCRIPTION",
    "INVALID_TOOL_NAME",
    "invalid_tool",
]
