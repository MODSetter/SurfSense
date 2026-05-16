"""Description string for ``pwd`` (mode-agnostic)."""

from __future__ import annotations

from app.agents.new_chat.filesystem_selection import FilesystemMode

_DESCRIPTION = """Prints the current working directory."""


def select_description(mode: FilesystemMode) -> str:
    return _DESCRIPTION
