"""Description string for ``glob`` (mode-agnostic)."""

from __future__ import annotations

from app.agents.new_chat.filesystem_selection import FilesystemMode

_DESCRIPTION = """Find files matching a glob pattern.

Supports standard glob patterns: `*`, `**`, `?`.
Returns absolute file paths.
"""


def select_description(mode: FilesystemMode) -> str:
    return _DESCRIPTION
