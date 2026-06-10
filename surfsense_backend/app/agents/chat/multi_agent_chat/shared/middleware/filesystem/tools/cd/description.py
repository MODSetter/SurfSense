"""Description string for ``cd`` (mode-agnostic)."""

from __future__ import annotations

from app.agents.chat.multi_agent_chat.shared.filesystem_selection import FilesystemMode

_DESCRIPTION = """Changes the current working directory (cwd).

Args:
- path: absolute or relative directory path. Relative paths resolve against
  the current cwd.

The new cwd is used by other filesystem tools whenever a relative path is
given. Returns the resolved cwd.
"""


def select_description(mode: FilesystemMode) -> str:
    return _DESCRIPTION
