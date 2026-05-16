"""Mode-specific description strings for ``list_tree``."""

from __future__ import annotations

from app.agents.new_chat.filesystem_selection import FilesystemMode

_CLOUD_DESCRIPTION = """Lists files/folders recursively in a single bounded call.

Args:
- path: absolute path to start from. Defaults to `/documents`.
- max_depth: recursion depth limit (default 8).
- page_size: maximum number of entries returned (max 1000).
- include_files / include_dirs: filter returned entry types.

Returns JSON with:
- entries: [{path, is_dir, size, modified_at, depth}]
- truncated: true when additional entries were omitted due to page_size.
"""

_DESKTOP_DESCRIPTION = """Lists files/folders recursively in a single bounded call.

Args:
- path: absolute path to start from. Defaults to `/`.
- max_depth: recursion depth limit (default 8).
- page_size: maximum number of entries returned (max 1000).
- include_files / include_dirs: filter returned entry types.

Returns JSON with:
- entries: [{path, is_dir, size, modified_at, depth}]
- truncated: true when additional entries were omitted due to page_size.
"""


def select_description(mode: FilesystemMode) -> str:
    if mode == FilesystemMode.CLOUD:
        return _CLOUD_DESCRIPTION
    return _DESKTOP_DESCRIPTION
