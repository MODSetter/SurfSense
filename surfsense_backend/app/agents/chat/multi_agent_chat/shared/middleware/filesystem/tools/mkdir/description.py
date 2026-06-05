"""Mode-specific description strings for ``mkdir``."""

from __future__ import annotations

from app.agents.chat.multi_agent_chat.shared.filesystem_selection import FilesystemMode

_CLOUD_DESCRIPTION = """Creates a directory under `/documents/`.

Stages the folder for end-of-turn commit; the Folder row is inserted only
after the agent's turn finishes successfully.

Args:
- path: absolute path of the new directory (must start with
  `/documents/`).

Notes:
- Parent folders are created as needed.
"""

_DESKTOP_DESCRIPTION = """Creates a directory on disk.

Args:
- path: absolute mount-prefixed path of the new directory.

Notes:
- Parent folders are created as needed.
"""


def select_description(mode: FilesystemMode) -> str:
    if mode == FilesystemMode.CLOUD:
        return _CLOUD_DESCRIPTION
    return _DESKTOP_DESCRIPTION
