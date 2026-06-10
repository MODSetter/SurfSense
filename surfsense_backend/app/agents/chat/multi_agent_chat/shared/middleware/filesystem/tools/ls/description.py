"""Mode-specific description strings for ``ls``."""

from __future__ import annotations

from app.agents.chat.multi_agent_chat.shared.filesystem_selection import FilesystemMode

_CLOUD_DESCRIPTION = """Lists files and directories at the given path.

Usage:
- Provide an absolute path under `/documents` (relative paths resolve under
  the current cwd, which defaults to `/documents`).
- For very large folders, use `offset` and `limit` to paginate the listing.
- Returns one entry per line; directories end with a trailing `/`.
"""

_DESKTOP_DESCRIPTION = """Lists files and directories at the given path.

Usage:
- Provide an absolute path using a mount prefix (e.g. `/<mount>/sub/dir`).
  Use `ls('/')` to discover available mounts.
- For very large folders, use `offset` and `limit` to paginate the listing.
- Returns one entry per line; directories end with a trailing `/`.
"""


def select_description(mode: FilesystemMode) -> str:
    if mode == FilesystemMode.CLOUD:
        return _CLOUD_DESCRIPTION
    return _DESKTOP_DESCRIPTION
