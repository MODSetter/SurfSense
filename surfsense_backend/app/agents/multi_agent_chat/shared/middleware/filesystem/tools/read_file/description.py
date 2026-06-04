"""Description string for ``read_file`` (mode-agnostic)."""

from __future__ import annotations

from app.agents.shared.filesystem_selection import FilesystemMode

_DESCRIPTION = """Reads a file from the filesystem.

Usage:
- By default, reads up to 100 lines from the beginning.
- Use `offset` and `limit` for pagination when files are large.
- Results include line numbers.
- Documents contain a `<chunk_index>` near the top listing every chunk with
  its line range and a `matched="true"` flag for search-relevant chunks.
  Read the index first, then jump to matched chunks with
  `read_file(path, offset=<start_line>, limit=<num_lines>)`.
- Use chunk IDs (`<chunk id='...'>`) as citations in answers.
"""


def select_description(mode: FilesystemMode) -> str:
    return _DESCRIPTION
