"""Mode-specific description strings for ``edit_file``."""

from __future__ import annotations

from app.agents.new_chat.filesystem_selection import FilesystemMode

_CLOUD_DESCRIPTION = """Performs exact string replacements in files.

IMPORTANT:
- Read the file before editing.
- Preserve exact indentation and formatting.
- Edits to documents under `/documents/` are persisted at end of turn.
- Edits to `temp_*` files are discarded at end of turn.
"""

_DESKTOP_DESCRIPTION = """Performs exact string replacements in files on disk.

IMPORTANT:
- Read the file before editing.
- Preserve exact indentation and formatting.
- Edits hit disk immediately.
"""


def select_description(mode: FilesystemMode) -> str:
    if mode == FilesystemMode.CLOUD:
        return _CLOUD_DESCRIPTION
    return _DESKTOP_DESCRIPTION
