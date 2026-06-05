"""Allowlist consulted by ``SurfSenseFilesystemMiddleware`` when ``read_only=True``."""

from __future__ import annotations

READ_ONLY_TOOL_NAMES = frozenset(
    {"ls", "read_file", "glob", "grep", "list_tree", "pwd", "cd"}
)
