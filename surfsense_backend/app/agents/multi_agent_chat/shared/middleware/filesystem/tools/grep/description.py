"""Mode-specific description strings for ``grep``."""

from __future__ import annotations

from app.agents.multi_agent_chat.shared.filesystem_selection import FilesystemMode

_CLOUD_DESCRIPTION = """Search for a literal text pattern across files.

Searches both your in-memory edits and the indexed chunks in Postgres.
State-cached file matches include real line numbers; database hits return
`line=0` because their position depends on per-document XML layout — call
`read_file(path)` afterwards to find the exact line.
"""

_DESKTOP_DESCRIPTION = """Search for a literal text pattern across files.

Searches files on disk and any in-memory edits. Returns real line numbers.
"""


def select_description(mode: FilesystemMode) -> str:
    if mode == FilesystemMode.CLOUD:
        return _CLOUD_DESCRIPTION
    return _DESKTOP_DESCRIPTION
