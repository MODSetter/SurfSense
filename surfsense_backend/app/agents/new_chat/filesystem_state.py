"""LangGraph state schema additions used by the SurfSense filesystem agent.

This schema extends deepagents' upstream :class:`FilesystemState` with the
extra fields needed to implement Postgres-backed virtual filesystem semantics:

* ``cwd`` — current working directory (per-thread checkpointed).
* ``staged_dirs`` — pending mkdir requests (cloud only).
* ``staged_dir_tool_calls`` — sidecar map ``path -> tool_call_id`` for staged dirs.
* ``pending_moves`` — pending move_file requests (cloud only).
* ``pending_deletes`` — pending ``rm`` requests (cloud only).
* ``pending_dir_deletes`` — pending ``rmdir`` requests (cloud only).
* ``doc_id_by_path`` — virtual_path -> Document.id, populated by lazy reads.
* ``dirty_paths`` — paths whose state file content differs from DB.
* ``dirty_path_tool_calls`` — sidecar map ``path -> latest tool_call_id`` for
  dirty paths; used to bind the per-path snapshot to an action_id.
* ``kb_priority`` — top-K priority hints rendered into a system message.
* ``kb_matched_chunk_ids`` — internal hand-off for matched-chunk highlighting.
* ``kb_anon_doc`` — Redis-loaded anonymous document (if any).
* ``tree_version`` — bumped by persistence; invalidates the tree render cache.

Tools mutate these fields ONLY via ``Command(update=...)`` returns; the
reducers in :mod:`app.agents.new_chat.state_reducers` handle merging.
"""

from __future__ import annotations

from typing import Annotated, Any, NotRequired

from deepagents.middleware.filesystem import FilesystemState
from typing_extensions import TypedDict

from app.agents.new_chat.state_reducers import (
    _add_unique_reducer,
    _dict_merge_with_tombstones_reducer,
    _list_append_reducer,
    _replace_reducer,
)


class PendingMove(TypedDict, total=False):
    """A staged move_file operation pending end-of-turn commit.

    ``tool_call_id`` is optional for backward compatibility with checkpoints
    written before the snapshot/revert pipeline was wired up; new entries
    always include it so the persistence body can resolve an action_id.
    """

    source: str
    dest: str
    overwrite: bool
    tool_call_id: str


class PendingDelete(TypedDict, total=False):
    """A staged ``rm`` or ``rmdir`` operation pending end-of-turn commit.

    ``tool_call_id`` is required for new entries (it's the binding key used
    by :class:`KnowledgeBasePersistenceMiddleware` to find the matching
    :class:`AgentActionLog` row and bind the snapshot to it). Marked
    ``total=False`` only to tolerate older checkpoint payloads.
    """

    path: str
    tool_call_id: str


class KbPriorityEntry(TypedDict, total=False):
    path: str
    score: float
    document_id: int | None
    title: str
    mentioned: bool


class KbAnonDoc(TypedDict, total=False):
    """In-memory anonymous-session document loaded from Redis."""

    path: str
    title: str
    content: str
    chunks: list[dict[str, Any]]


class SurfSenseFilesystemState(FilesystemState):
    """Filesystem state used by the SurfSense agent (cloud + desktop).

    Extends deepagents' :class:`FilesystemState` (which provides ``files``)
    with cloud-mode staging fields and search-priority hints. All extra fields
    are reducer-backed so that ``Command(update=...)`` payloads merge cleanly
    across agent steps and across checkpoints.
    """

    cwd: NotRequired[Annotated[str, _replace_reducer]]
    """Current working directory.

    Defaults to ``"/documents"`` in cloud mode and ``"/"`` (or first mount) in
    desktop mode. Initialized once per thread by ``KnowledgeTreeMiddleware``.
    """

    staged_dirs: NotRequired[Annotated[list[str], _add_unique_reducer]]
    """mkdir paths staged for end-of-turn folder creation (cloud only)."""

    staged_dir_tool_calls: NotRequired[
        Annotated[dict[str, str], _dict_merge_with_tombstones_reducer]
    ]
    """``path -> tool_call_id`` sidecar for ``staged_dirs``.

    Used by :class:`KnowledgeBasePersistenceMiddleware` to bind the
    :class:`FolderRevision` snapshot to the originating ``mkdir`` action.
    Kept separate from ``staged_dirs`` (which stays a unique-string list)
    to avoid breaking ``_add_unique_reducer`` semantics.
    """

    pending_moves: NotRequired[Annotated[list[PendingMove], _list_append_reducer]]
    """move_file ops staged for end-of-turn commit (cloud only)."""

    pending_deletes: NotRequired[Annotated[list[PendingDelete], _list_append_reducer]]
    """``rm`` ops staged for end-of-turn ``DELETE FROM documents`` (cloud only).

    Each entry is a dict ``{"path": ..., "tool_call_id": ...}``. Per-path
    uniqueness is enforced inside the commit body, not the reducer (we keep
    ``tool_call_id`` per occurrence so snapshot binding works).
    """

    pending_dir_deletes: NotRequired[
        Annotated[list[PendingDelete], _list_append_reducer]
    ]
    """``rmdir`` ops staged for end-of-turn ``DELETE FROM folders`` (cloud only).

    Same shape as :data:`pending_deletes`. Commit body re-verifies the
    folder is empty (in-DB AND with this turn's pending changes accounted
    for) before issuing the DELETE.
    """

    doc_id_by_path: NotRequired[
        Annotated[dict[str, int], _dict_merge_with_tombstones_reducer]
    ]
    """virtual_path -> ``Document.id`` for lazily loaded files.

    Populated on first read of a KB document. Used by edit_file/move_file/
    aafter_agent to map paths back to a real DB row. ``None`` values delete
    the key (tombstones).
    """

    dirty_paths: NotRequired[Annotated[list[str], _add_unique_reducer]]
    """Paths whose ``state["files"]`` content has been modified this turn."""

    dirty_path_tool_calls: NotRequired[
        Annotated[dict[str, str], _dict_merge_with_tombstones_reducer]
    ]
    """``path -> latest tool_call_id`` sidecar for ``dirty_paths``.

    The persistence body coalesces multiple writes/edits to the same path
    into one snapshot per turn. This map captures the most-recent
    ``tool_call_id`` so the resulting :class:`DocumentRevision` is bound
    to the latest action_id (the one the user is most likely to revert).
    """

    kb_priority: NotRequired[Annotated[list[KbPriorityEntry], _replace_reducer]]
    """Top-K priority hints rendered as a system message before the user turn."""

    kb_matched_chunk_ids: NotRequired[Annotated[dict[int, list[int]], _replace_reducer]]
    """Internal: ``Document.id`` -> list of matched chunk IDs from hybrid search."""

    kb_anon_doc: NotRequired[Annotated[KbAnonDoc | None, _replace_reducer]]
    """Anonymous-session document loaded from Redis (read-only, no DB row)."""

    tree_version: NotRequired[Annotated[int, _replace_reducer]]
    """Monotonically increasing counter; bumped when commits change the KB tree."""


__all__ = [
    "KbAnonDoc",
    "KbPriorityEntry",
    "PendingDelete",
    "PendingMove",
    "SurfSenseFilesystemState",
]
