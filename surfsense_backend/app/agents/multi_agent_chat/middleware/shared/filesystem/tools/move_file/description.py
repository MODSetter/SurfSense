"""Mode-specific description strings for ``move_file``."""

from __future__ import annotations

from app.agents.shared.filesystem_selection import FilesystemMode

_CLOUD_DESCRIPTION = """Moves or renames a file or folder.

Use absolute paths for both source and destination.

Notes:
- `move_file` is staged this turn and committed at end of turn.
- The agent cannot overwrite an existing destination — pass a fresh dest
  path or move the existing destination away first.
- The anonymous uploaded document is read-only and cannot be moved.
- Rename is a special case of move (same folder, different filename).
"""

_DESKTOP_DESCRIPTION = """Moves or renames a file or folder on disk.

Use mount-prefixed absolute paths for both source and destination
(e.g. `/<mount>/old.txt` -> `/<mount>/new.txt`).

Notes:
- Cross-mount moves are not supported.
- Rename is a special case of move (same folder, different filename).
"""


def select_description(mode: FilesystemMode) -> str:
    if mode == FilesystemMode.CLOUD:
        return _CLOUD_DESCRIPTION
    return _DESKTOP_DESCRIPTION
