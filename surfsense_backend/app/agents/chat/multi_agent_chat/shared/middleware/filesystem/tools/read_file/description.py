"""Description string for ``read_file`` (mode-agnostic)."""

from __future__ import annotations

from app.agents.chat.multi_agent_chat.shared.filesystem_selection import FilesystemMode

_DESCRIPTION = """Reads a file from the filesystem.

Usage:
- By default, reads up to 100 lines from the beginning.
- Use `offset` and `limit` for pagination when files are large.
- Results include line numbers.
- A knowledge-base document is returned as a `<document … view="full">` block:
  the whole source, with each passage labelled `[n]`. `view="full"` means you are
  seeing the complete document, not an excerpt.
- Cite a passage by writing its `[n]` after the statement it supports — the same
  `[n]` you would use for that passage from `search_knowledge_base`.
"""


def select_description(mode: FilesystemMode) -> str:
    return _DESCRIPTION
