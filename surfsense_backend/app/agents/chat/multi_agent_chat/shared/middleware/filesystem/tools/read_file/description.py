"""Description strings for ``read_file``, split by whether reads are citable.

The split is **not** cloud vs desktop like its sibling tools: it is whether the
read returns a citation envelope. Only cloud-on-Postgres does, because only
``KBPostgresBackend`` renders documents through ``render_full_document``; the
desktop mounts and the git-native working copy both return raw file text. A
single description promising ``[n]``-labelled passages therefore misinstructs
two of the three modes, and the failure is worse than a missing citation: told
to cite "the same ``[n]`` you would use from ``search_knowledge_base``" while
seeing no labels, a model can attach a search result's ordinal to text it read
from a file, producing a confident citation pointing at the wrong source.
"""

from __future__ import annotations

from app.agents.chat.multi_agent_chat.shared.filesystem_selection import FilesystemMode

_USAGE = """Reads a file from the filesystem.

Usage:
- By default, reads up to 100 lines from the beginning.
- Use `offset` and `limit` for pagination when files are large.
- Results include line numbers.
"""

_ENVELOPE_DESCRIPTION = (
    _USAGE
    + """- A knowledge-base document is returned as a `<document … view="full">` block:
  the whole source, with each passage labelled `[n]`. `view="full"` means you are
  seeing the complete document, not an excerpt.
- Cite a passage by writing its `[n]` after the statement it supports — the same
  `[n]` you would use for that passage from `search_knowledge_base`.
"""
)

_RAW_DESCRIPTION = (
    _USAGE
    + """- The result is the file's own text, with no `[n]` labels, so there is nothing
  here to cite. Never attach an `[n]` to a statement taken from a read: the
  ordinals you have seen belong to `search_knowledge_base` excerpts, and reusing
  one here would credit the wrong source. Cite the same content from
  `search_knowledge_base`, which does label what it returns, or state it without
  a citation.
"""
)


def select_description(mode: FilesystemMode, *, git_native: bool = False) -> str:
    """Pick the description matching what this mode's reads actually return."""
    if mode == FilesystemMode.CLOUD and not git_native:
        return _ENVELOPE_DESCRIPTION
    return _RAW_DESCRIPTION
