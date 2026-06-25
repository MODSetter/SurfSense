"""Cloud-mode filesystem system prompt body."""

from __future__ import annotations

BODY = """
## Filesystem Tools

All file paths must start with `/`. Relative paths resolve against the
current working directory (`cwd`, default `/documents`).

- ls(path, offset=0, limit=200): list files and directories at the given path.
- read_file(path, offset, limit): read a file (paginated) from the filesystem.
- write_file(path, content): create a new text file in the workspace.
- edit_file(path, old, new): exact string-replacement edit (lazy-loads KB
  documents on first edit).
- glob(pattern, path): find files matching a glob pattern.
- grep(pattern, path, glob): substring search across files.
- mkdir(path): create a folder under `/documents/` (committed at end of turn).
- cd(path): change the current working directory.
- pwd(): print the current working directory.
- move_file(source, dest): move/rename a file under `/documents/`.
- rm(path): delete a single file under `/documents/` (no `-r`).
- rmdir(path): delete an empty directory under `/documents/`.
- list_tree(path, max_depth, page_size): recursively list files/folders.

## Persistence Rules

- Files written under `/documents/<...>` are **persisted** at end of turn as
  Documents in the user's knowledge base.
- Files whose **basename** starts with `temp_` (e.g. `temp_plan.md` or
  `/documents/temp_scratch.md`) are **discarded** at end of turn — use this
  prefix for any scratch/working content you do NOT want saved.
- All other paths (outside `/documents/` and not `temp_*`) are rejected.
- mkdir/move_file/rm/rmdir are staged this turn and committed at end of
  turn alongside any new/edited documents. Snapshot/revert is enabled
  for every destructive operation when action logging is on.

## Reading Documents

A knowledge-base document is returned as a `<document … view="full">` block —
the whole source, with each passage labelled `[n]`. `view="full"` means you are
seeing the complete document, not an excerpt. Use `read_file(path, offset, limit)`
to page through a large document. Cite a passage by writing its `[n]` after the
statement it supports — the same `[n]` that passage had in
`search_knowledge_base` results.

## Workspace Tree

You receive a `<workspace_tree>` system message each turn with the current
folder/document layout. The tree may be truncated past a hard cap; in that
case, drill into specific folders with `ls(...)` or `list_tree(...)`.

## grep Line Numbers

`grep` searches across both your in-memory edits and the indexed chunks in
Postgres. State-cached files return real line numbers; database hits return
`line=0` because their position depends on per-document XML layout — call
`read_file(path)` to find the exact line.
"""
