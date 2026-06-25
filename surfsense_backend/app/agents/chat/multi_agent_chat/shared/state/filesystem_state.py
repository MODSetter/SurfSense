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
* ``kb_anon_doc`` — Redis-loaded anonymous document (if any).
* ``citation_registry`` — per-conversation ``[n]`` -> source map for citations.
* ``tree_version`` — bumped by persistence; invalidates the tree render cache.
* ``workspace_tree_text`` — pre-rendered ``<workspace_tree>`` body for the turn.

Tools mutate these fields ONLY via ``Command(update=...)`` returns; the
reducers in :mod:`app.agents.chat.multi_agent_chat.shared.state.reducers` handle merging.
"""

from __future__ import annotations

from typing import Annotated, Any, NotRequired

from deepagents.middleware.filesystem import FilesystemState
from typing_extensions import TypedDict

from app.agents.chat.multi_agent_chat.shared.citations import CitationRegistry
from app.agents.chat.multi_agent_chat.shared.receipts.receipt import Receipt
from app.agents.chat.multi_agent_chat.shared.state.reducers import (
    _add_unique_reducer,
    _citation_registry_merge_reducer,
    _dict_merge_with_tombstones_reducer,
    _int_counter_merge_reducer,
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

    kb_anon_doc: NotRequired[Annotated[KbAnonDoc | None, _replace_reducer]]
    """Anonymous-session document loaded from Redis (read-only, no DB row)."""

    citation_registry: NotRequired[
        Annotated[CitationRegistry, _citation_registry_merge_reducer]
    ]
    """Per-conversation ``[n]`` -> source map; written by retrieval, read by the
    normalizer. Merges (union, find-or-create) so parallel/subagent registrations
    stay globally consistent instead of clobbering each other."""

    tree_version: NotRequired[Annotated[int, _replace_reducer]]
    """Monotonically increasing counter; bumped when commits change the KB tree."""

    workspace_tree_text: NotRequired[Annotated[str, _replace_reducer]]
    """Pre-rendered ``<workspace_tree>`` body; shared with subagents to skip re-render."""

    billable_calls: NotRequired[Annotated[dict[str, int], _int_counter_merge_reducer]]
    """Per-subagent ``task(...)`` invocation counter, summed across the turn.

    Incremented by ``task_tool.py`` each time a subagent invocation
    completes (single- or batch-mode). The orchestrator can read this map
    to self-limit when a runaway loop sends the same specialist 20 calls
    in a row; the runtime emits a soft warning ToolMessage once the
    cumulative count crosses :data:`DEFAULT_SUBAGENT_BILLABLE_THRESHOLD`.
    Cleared by checkpoint rollover (i.e. per turn).
    """

    receipts: NotRequired[Annotated[list[Receipt], _list_append_reducer]]
    """Structured Receipt handles emitted by mutating subagent tools this turn.

    Each mutating tool (deliverables, every connector, KB writes via the
    persistence middleware) wraps its native return into a
    :class:`~app.agents.chat.multi_agent_chat.shared.receipts.receipt.Receipt`
    and returns it under the ``"receipt"`` key alongside its existing
    payload. The subagent's tool-call middleware folds the receipt into
    this list, and ``_return_command_with_state_update`` in
    ``checkpointed_subagent_middleware/task_tool.py`` carries the list up
    to the parent automatically (``"receipts"`` is not in
    ``EXCLUDED_STATE_KEYS``).

    Append-only across the turn; cleared by checkpoint rollover. The
    orchestrator reads it via the ``<verification>`` teaching to confirm
    side-effecting subagent claims (see ``shared/snippets/verifiable_handle.md``).
    """


__all__ = [
    "KbAnonDoc",
    "KbPriorityEntry",
    "PendingDelete",
    "PendingMove",
    "SurfSenseFilesystemState",
]
