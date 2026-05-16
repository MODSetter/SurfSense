"""Mode-specific description strings for ``rmdir``."""

from __future__ import annotations

from app.agents.new_chat.filesystem_selection import FilesystemMode

_CLOUD_DESCRIPTION = """Deletes an empty directory under `/documents/`.

Mirrors POSIX `rmdir path`: refuses non-empty directories. Recursive
deletion (`rm -r`) is intentionally NOT supported — clear contents with
`rm` first.

Args:
- path: absolute or relative directory path. Cannot target the root,
  `/documents`, the current cwd, or any ancestor of cwd (use `cd` to
  move out first).

Notes:
- Emptiness is evaluated against the post-staged view, so a same-turn
  `rm /a/x.md` followed by `rmdir /a` is fine.
- If the directory was added in this same turn via `mkdir` and never
  committed, the staged mkdir is dropped instead of issuing a delete.
- The action is reversible via the per-action revert flow when action
  logging is enabled.
"""

_DESKTOP_DESCRIPTION = """Deletes an empty directory from disk.

Mirrors POSIX `rmdir path`: refuses non-empty directories. Recursive
deletion is NOT supported. The deletion hits disk immediately and is
NOT reversible via the agent's revert flow.

Args:
- path: absolute mount-prefixed directory path. Cannot target the mount
  root or any directory containing files/subfolders.
"""


def select_description(mode: FilesystemMode) -> str:
    if mode == FilesystemMode.CLOUD:
        return _CLOUD_DESCRIPTION
    return _DESKTOP_DESCRIPTION
