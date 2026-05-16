"""Mode-specific description strings for ``rm``."""

from __future__ import annotations

from app.agents.new_chat.filesystem_selection import FilesystemMode

_CLOUD_DESCRIPTION = """Deletes a single file under `/documents/`.

Mirrors POSIX `rm path` (no `-r`, no glob expansion). Stages the deletion
for end-of-turn commit; the row is removed only after the agent's turn
finishes successfully.

Args:
- path: absolute or relative file path. Cannot point at a directory — use
  `rmdir` for empty folders. Cannot target the root or `/documents`.

Notes:
- The action is reversible via the per-action revert flow when action
  logging is enabled.
- The anonymous uploaded document is read-only and cannot be deleted.
"""

_DESKTOP_DESCRIPTION = """Deletes a single file from disk.

Mirrors POSIX `rm path` (no `-r`, no glob expansion). The deletion hits
disk immediately. Desktop deletes are NOT reversible via the agent's
revert flow.

Args:
- path: absolute mount-prefixed file path. Cannot point at a directory —
  use `rmdir` for empty folders.
"""


def select_description(mode: FilesystemMode) -> str:
    if mode == FilesystemMode.CLOUD:
        return _CLOUD_DESCRIPTION
    return _DESKTOP_DESCRIPTION
