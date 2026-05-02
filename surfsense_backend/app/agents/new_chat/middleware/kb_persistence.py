"""End-of-turn persistence for the cloud-mode SurfSense filesystem.

This middleware runs ``aafter_agent`` once per turn (cloud only). It commits
all staged folder creations, file moves, content writes/edits, file deletes
(``rm``), and directory deletes (``rmdir``) to Postgres in a single ordered
pass:

1. Materialize ``staged_dirs`` into ``Folder`` rows.
2. Apply ``pending_moves`` in order (chained moves resolved via
   ``doc_id_by_path``).
3. Normalize ``dirty_paths`` through ``pending_moves`` so write-then-move
   sequences commit at the final path. Paths queued for ``rm`` this turn
   are dropped here so a write+rm sequence doesn't recreate the doc.
4. Commit content writes / edits for ``/documents/*`` paths, skipping
   ``temp_*`` basenames.
5. Apply ``pending_deletes`` (``rm``) — file deletes run BEFORE directory
   deletes so a same-turn ``rm /a/x.md`` + ``rmdir /a`` sequence works.
6. Apply ``pending_dir_deletes`` (``rmdir``); re-verifies emptiness against
   the post-step-5 DB state.

When ``flags.enable_action_log`` is on every destructive op also writes a
``DocumentRevision`` / ``FolderRevision`` snapshot bound to the
originating ``AgentActionLog`` row via ``tool_call_id``. ``rm``/``rmdir``
share a single ``SAVEPOINT`` with their snapshot — if the snapshot fails
the DELETE rolls back and we surface the error rather than silently
making the data irreversible.

The commit body is exposed as a free function ``commit_staged_filesystem_state``
so the optional stream-task fallback (``stream_new_chat.py``) can call the
exact same routine when ``aafter_agent`` was skipped (e.g. client disconnect).
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from fractional_indexing import generate_key_between
from langchain.agents.middleware import AgentMiddleware, AgentState
from langchain_core.callbacks import adispatch_custom_event, dispatch_custom_event
from langgraph.runtime import Runtime
from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.new_chat.feature_flags import get_flags
from app.agents.new_chat.filesystem_selection import FilesystemMode
from app.agents.new_chat.filesystem_state import SurfSenseFilesystemState
from app.agents.new_chat.path_resolver import (
    DOCUMENTS_ROOT,
    parse_documents_path,
    safe_folder_segment,
    virtual_path_to_doc,
)
from app.agents.new_chat.state_reducers import _CLEAR
from app.db import (
    AgentActionLog,
    Chunk,
    Document,
    DocumentRevision,
    DocumentType,
    Folder,
    FolderRevision,
    shielded_async_session,
)
from app.indexing_pipeline.document_chunker import chunk_text
from app.utils.document_converters import (
    embed_texts,
    generate_content_hash,
    generate_unique_identifier_hash,
)

logger = logging.getLogger(__name__)


_TEMP_PREFIX = "temp_"


def _basename(path: str) -> str:
    return path.rsplit("/", 1)[-1]


# ---------------------------------------------------------------------------
# Folder helpers
# ---------------------------------------------------------------------------


async def _ensure_folder_hierarchy(
    session: AsyncSession,
    *,
    search_space_id: int,
    created_by_id: str | None,
    folder_parts: list[str],
) -> int | None:
    """Ensure a chain of folder names exists under the search space.

    Returns the leaf folder id, or ``None`` if ``folder_parts`` is empty
    (i.e. a document directly under ``/documents/``).
    """
    if not folder_parts:
        return None
    parent_id: int | None = None
    for raw in folder_parts:
        name = safe_folder_segment(str(raw))
        query = select(Folder).where(
            Folder.search_space_id == search_space_id,
            Folder.name == name,
        )
        if parent_id is None:
            query = query.where(Folder.parent_id.is_(None))
        else:
            query = query.where(Folder.parent_id == parent_id)
        result = await session.execute(query)
        folder = result.scalar_one_or_none()
        if folder is None:
            sibling_query = (
                select(Folder.position).order_by(Folder.position.desc()).limit(1)
            )
            sibling_query = sibling_query.where(
                Folder.search_space_id == search_space_id
            )
            if parent_id is None:
                sibling_query = sibling_query.where(Folder.parent_id.is_(None))
            else:
                sibling_query = sibling_query.where(Folder.parent_id == parent_id)
            sibling_result = await session.execute(sibling_query)
            last_position = sibling_result.scalar_one_or_none()
            folder = Folder(
                name=name,
                position=generate_key_between(last_position, None),
                parent_id=parent_id,
                search_space_id=search_space_id,
                created_by_id=created_by_id,
                updated_at=datetime.now(UTC),
            )
            session.add(folder)
            await session.flush()
        parent_id = folder.id
    return parent_id


async def _resolve_folder_id(
    session: AsyncSession,
    *,
    search_space_id: int,
    folder_parts: list[str],
) -> int | None:
    """Look up an existing folder chain without creating anything.

    Returns ``None`` if any segment is missing. Used by ``rmdir`` snapshot
    capture and by parent-folder lookup at ``rmdir`` commit time.
    """
    if not folder_parts:
        return None
    parent_id: int | None = None
    for raw in folder_parts:
        name = safe_folder_segment(str(raw))
        query = select(Folder).where(
            Folder.search_space_id == search_space_id,
            Folder.name == name,
        )
        query = (
            query.where(Folder.parent_id.is_(None))
            if parent_id is None
            else query.where(Folder.parent_id == parent_id)
        )
        result = await session.execute(query)
        folder = result.scalar_one_or_none()
        if folder is None:
            return None
        parent_id = folder.id
    return parent_id


def _split_folder_path(folder_path: str) -> list[str]:
    """Return the folder segments under ``/documents/`` for a path."""
    if not folder_path.startswith(DOCUMENTS_ROOT):
        return []
    rel = folder_path[len(DOCUMENTS_ROOT) :].strip("/")
    return [p for p in rel.split("/") if p]


# ---------------------------------------------------------------------------
# Document helpers
# ---------------------------------------------------------------------------


async def _create_document(
    session: AsyncSession,
    *,
    virtual_path: str,
    content: str,
    search_space_id: int,
    created_by_id: str | None,
) -> Document:
    """Create a NOTE Document + Chunks for ``virtual_path``."""
    folder_parts, title = parse_documents_path(virtual_path)
    if not title:
        raise ValueError(f"invalid /documents path '{virtual_path}'")
    folder_id = await _ensure_folder_hierarchy(
        session,
        search_space_id=search_space_id,
        created_by_id=created_by_id,
        folder_parts=folder_parts,
    )
    unique_identifier_hash = generate_unique_identifier_hash(
        DocumentType.NOTE,
        virtual_path,
        search_space_id,
    )
    # Filesystem-parity invariant: the only thing that *must* be unique is
    # the path. Two notes can legitimately share content (e.g. ``cp a b``).
    # Guard against the path-derived ``unique_identifier_hash`` constraint
    # so we surface a clean ValueError instead of letting the INSERT poison
    # the session with an IntegrityError.
    path_collision = await session.execute(
        select(Document.id).where(
            Document.search_space_id == search_space_id,
            Document.unique_identifier_hash == unique_identifier_hash,
        )
    )
    if path_collision.scalar_one_or_none() is not None:
        raise ValueError(
            f"a document already exists at path '{virtual_path}' "
            "(unique_identifier_hash collision)"
        )
    # ``content_hash`` is intentionally NOT checked for uniqueness here.
    # In a real filesystem two files at different paths can hold identical
    # bytes, and the agent's ``write_file`` path needs that semantic to
    # support copy/duplicate operations. The hash remains useful as a
    # change-detection hint for connector indexers, which still consult it
    # via :func:`check_duplicate_document` but do so with a non-unique
    # lookup (``.first()``).
    content_hash = generate_content_hash(content, search_space_id)
    doc = Document(
        title=title,
        document_type=DocumentType.NOTE,
        document_metadata={"virtual_path": virtual_path},
        content=content,
        content_hash=content_hash,
        unique_identifier_hash=unique_identifier_hash,
        source_markdown=content,
        search_space_id=search_space_id,
        folder_id=folder_id,
        created_by_id=created_by_id,
        updated_at=datetime.now(UTC),
    )
    session.add(doc)
    await session.flush()

    summary_embedding = embed_texts([content])[0]
    doc.embedding = summary_embedding
    chunks = chunk_text(content)
    if chunks:
        chunk_embeddings = embed_texts(chunks)
        session.add_all(
            [
                Chunk(document_id=doc.id, content=text, embedding=embedding)
                for text, embedding in zip(chunks, chunk_embeddings, strict=True)
            ]
        )
    return doc


async def _update_document(
    session: AsyncSession,
    *,
    doc_id: int,
    content: str,
    virtual_path: str,
    search_space_id: int,
) -> Document | None:
    """Update an existing Document's content + chunks."""
    result = await session.execute(
        select(Document).where(
            Document.id == doc_id,
            Document.search_space_id == search_space_id,
        )
    )
    document = result.scalar_one_or_none()
    if document is None:
        return None

    document.content = content
    document.source_markdown = content
    document.content_hash = generate_content_hash(content, search_space_id)
    document.updated_at = datetime.now(UTC)
    metadata = dict(document.document_metadata or {})
    metadata["virtual_path"] = virtual_path
    document.document_metadata = metadata
    document.unique_identifier_hash = generate_unique_identifier_hash(
        DocumentType.NOTE,
        virtual_path,
        search_space_id,
    )

    summary_embedding = embed_texts([content])[0]
    document.embedding = summary_embedding

    await session.execute(delete(Chunk).where(Chunk.document_id == document.id))
    chunks = chunk_text(content)
    if chunks:
        chunk_embeddings = embed_texts(chunks)
        session.add_all(
            [
                Chunk(document_id=document.id, content=text, embedding=embedding)
                for text, embedding in zip(chunks, chunk_embeddings, strict=True)
            ]
        )
    return document


# ---------------------------------------------------------------------------
# Move helpers
# ---------------------------------------------------------------------------


async def _apply_move(
    session: AsyncSession,
    *,
    search_space_id: int,
    created_by_id: str | None,
    move: dict[str, Any],
    doc_id_by_path: dict[str, int],
    doc_id_path_tombstones: dict[str, int | None],
) -> dict[str, Any] | None:
    """Apply a single staged move; updates the in-memory mapping for chain resolution."""
    source = str(move.get("source") or "")
    dest = str(move.get("dest") or "")
    if not source or not dest or source == dest:
        return None

    if not source.startswith(DOCUMENTS_ROOT + "/") or not dest.startswith(
        DOCUMENTS_ROOT + "/"
    ):
        return None

    doc_id: int | None = doc_id_by_path.get(source)
    document: Document | None = None
    if doc_id is not None:
        result = await session.execute(
            select(Document).where(
                Document.id == doc_id,
                Document.search_space_id == search_space_id,
            )
        )
        document = result.scalar_one_or_none()
    if document is None:
        document = await virtual_path_to_doc(
            session,
            search_space_id=search_space_id,
            virtual_path=source,
        )
    if document is None:
        logger.info(
            "kb_persistence: skipping move %s -> %s (source not found)",
            source,
            dest,
        )
        return None

    folder_parts, new_title = parse_documents_path(dest)
    if not new_title:
        return None
    folder_id = await _ensure_folder_hierarchy(
        session,
        search_space_id=search_space_id,
        created_by_id=created_by_id,
        folder_parts=folder_parts,
    )

    document.title = new_title
    document.folder_id = folder_id
    metadata = dict(document.document_metadata or {})
    metadata["virtual_path"] = dest
    document.document_metadata = metadata
    document.unique_identifier_hash = generate_unique_identifier_hash(
        DocumentType.NOTE,
        dest,
        search_space_id,
    )
    document.updated_at = datetime.now(UTC)

    doc_id_by_path.pop(source, None)
    doc_id_by_path[dest] = document.id
    doc_id_path_tombstones[source] = None
    doc_id_path_tombstones[dest] = document.id
    return {"id": document.id, "source": source, "dest": dest, "title": new_title}


# ---------------------------------------------------------------------------
# Action log binding helpers
# ---------------------------------------------------------------------------


async def _find_action_ids_batch(
    session: AsyncSession,
    *,
    thread_id: int | None,
    tool_call_ids: set[str],
) -> dict[str, int]:
    """Resolve ``tool_call_id -> AgentActionLog.id`` in a single query.

    Returns an empty dict when ``thread_id`` or ``tool_call_ids`` are
    missing — callers treat that as "no binding available" and write the
    revision with ``agent_action_id = NULL``.
    """
    if thread_id is None or not tool_call_ids:
        return {}
    rows = await session.execute(
        select(AgentActionLog.id, AgentActionLog.tool_call_id).where(
            AgentActionLog.thread_id == thread_id,
            AgentActionLog.tool_call_id.in_(list(tool_call_ids)),
        )
    )
    mapping: dict[str, int] = {}
    for row in rows.all():
        if row.tool_call_id and row.id:
            mapping[str(row.tool_call_id)] = int(row.id)
    return mapping


async def _mark_action_reversible(
    session: AsyncSession,
    *,
    action_id: int | None,
) -> None:
    """Flip ``agent_action_log.reversible = TRUE`` for ``action_id``.

    Best-effort: caller may invoke from inside a SAVEPOINT and treat
    failure as a soft demotion (snapshot persists, just no Revert button).

    Callers should also call ``_dispatch_reversibility_update`` (defined
    below) AFTER the enclosing SAVEPOINT block exits successfully so the
    chat tool card can light up its Revert button without
    re-fetching ``GET /threads/.../actions``. Dispatching from inside the
    SAVEPOINT would risk emitting "reversible=true" for rows whose
    update gets rolled back if the surrounding destructive op fails.
    """
    if action_id is None:
        return
    await session.execute(
        update(AgentActionLog)
        .where(AgentActionLog.id == action_id)
        .values(reversible=True)
    )


async def _dispatch_reversibility_update(action_id: int | None) -> None:
    """Best-effort dispatch of an ``action_log_updated`` custom event.

    Surfaces the post-SAVEPOINT reversibility flip to the SSE layer so
    the chat tool card can flip its Revert button live. Defensive:
    failures are logged at debug level and swallowed; the
    REST endpoint ``GET /threads/.../actions`` is still authoritative.

    .. warning::
        Inside :func:`commit_staged_filesystem_state` we DEFER all
        dispatches until the outer ``session.commit()`` succeeds — see
        the ``deferred_dispatches`` queue in that function. Dispatching
        from inside a SAVEPOINT block while the outer transaction is
        still pending would emit ``reversible=true`` for rows whose
        snapshots get rolled back if the outer commit fails. Direct
        callers (e.g. the optional stream-task fallback) that own the
        full session lifetime can still call this helper inline.
    """
    if action_id is None:
        return
    try:
        await adispatch_custom_event(
            "action_log_updated",
            {"id": int(action_id), "reversible": True},
        )
    except Exception:
        logger.debug(
            "kb_persistence.aafter_agent failed to dispatch action_log_updated",
            exc_info=True,
        )


# ---------------------------------------------------------------------------
# Snapshot helpers
# ---------------------------------------------------------------------------
#
# Best-effort helpers swallow + log so a snapshot failure can never break
# the destructive op for non-destructive tools (write/edit/move/mkdir).
# Strict helpers run inside the SAME ``begin_nested()`` SAVEPOINT as the
# destructive DELETE — failure aborts the savepoint and leaves the doc /
# folder intact, so revertable ops never become irreversible silently.


def _doc_revision_payload(
    doc: Document,
    *,
    chunks_before: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """Pre-mutation field map for ``DocumentRevision``."""
    metadata = dict(doc.document_metadata or {})
    return {
        "content_before": doc.content,
        "title_before": doc.title,
        "folder_id_before": doc.folder_id,
        "chunks_before": chunks_before,
        "metadata_before": metadata or None,
    }


async def _load_chunks_for_snapshot(
    session: AsyncSession, *, doc_id: int
) -> list[dict[str, str]]:
    rows = await session.execute(
        select(Chunk.content).where(Chunk.document_id == doc_id).order_by(Chunk.id)
    )
    return [{"content": row.content} for row in rows.all() if row.content is not None]


async def _snapshot_document_pre_write(
    session: AsyncSession,
    *,
    doc: Document,
    action_id: int | None,
    search_space_id: int,
    turn_id: str | None = None,
    deferred_dispatches: list[int] | None = None,
) -> int | None:
    """Best-effort snapshot ahead of an in-place ``write_file``/``edit_file``.

    When ``deferred_dispatches`` is provided, on success the action id
    is APPENDED to it and the SSE dispatch is left to the caller (so it
    can be flushed only after the outer ``session.commit()`` succeeds).
    """
    try:
        async with session.begin_nested():
            chunks = await _load_chunks_for_snapshot(session, doc_id=doc.id)
            payload = _doc_revision_payload(doc, chunks_before=chunks)
            rev = DocumentRevision(
                document_id=doc.id,
                search_space_id=search_space_id,
                created_by_turn_id=turn_id,
                agent_action_id=action_id,
                **payload,
            )
            session.add(rev)
            await session.flush()
            await _mark_action_reversible(session, action_id=action_id)
            rev_id = rev.id
        if deferred_dispatches is None:
            await _dispatch_reversibility_update(action_id)
        elif action_id is not None:
            deferred_dispatches.append(int(action_id))
        return rev_id
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning(
            "kb_persistence: pre-write snapshot for doc=%s failed: %s",
            doc.id,
            exc,
        )
        return None


async def _snapshot_document_pre_create(
    session: AsyncSession,
    *,
    action_id: int | None,
    search_space_id: int,
    turn_id: str | None = None,
    deferred_dispatches: list[int] | None = None,
) -> int | None:
    """Best-effort placeholder revision for a fresh ``write_file`` create.

    ``document_id`` is patched in by the caller after the new doc is
    flushed and gets an ID; the placeholder lets us bind the action_id
    even though no parent row exists yet.
    """
    try:
        async with session.begin_nested():
            rev = DocumentRevision(
                document_id=None,
                search_space_id=search_space_id,
                content_before=None,
                title_before=None,
                folder_id_before=None,
                chunks_before=None,
                metadata_before=None,
                created_by_turn_id=turn_id,
                agent_action_id=action_id,
            )
            session.add(rev)
            await session.flush()
            await _mark_action_reversible(session, action_id=action_id)
            rev_id = rev.id
        if deferred_dispatches is None:
            await _dispatch_reversibility_update(action_id)
        elif action_id is not None:
            deferred_dispatches.append(int(action_id))
        return rev_id
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("kb_persistence: pre-create snapshot failed: %s", exc)
        return None


async def _snapshot_document_pre_move(
    session: AsyncSession,
    *,
    doc: Document,
    action_id: int | None,
    search_space_id: int,
    turn_id: str | None = None,
    deferred_dispatches: list[int] | None = None,
) -> int | None:
    """Best-effort snapshot ahead of a ``move_file``."""
    try:
        async with session.begin_nested():
            payload = _doc_revision_payload(doc, chunks_before=None)
            rev = DocumentRevision(
                document_id=doc.id,
                search_space_id=search_space_id,
                created_by_turn_id=turn_id,
                agent_action_id=action_id,
                **payload,
            )
            session.add(rev)
            await session.flush()
            await _mark_action_reversible(session, action_id=action_id)
            rev_id = rev.id
        if deferred_dispatches is None:
            await _dispatch_reversibility_update(action_id)
        elif action_id is not None:
            deferred_dispatches.append(int(action_id))
        return rev_id
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning(
            "kb_persistence: pre-move snapshot for doc=%s failed: %s",
            doc.id,
            exc,
        )
        return None


async def _snapshot_folder_pre_mkdir(
    session: AsyncSession,
    *,
    folder: Folder,
    action_id: int | None,
    search_space_id: int,
    turn_id: str | None = None,
    deferred_dispatches: list[int] | None = None,
) -> int | None:
    """Best-effort placeholder for an ``mkdir`` (revert deletes the folder).

    The "before" state is "did not exist", so all ``*_before`` fields are
    NULL — revert routes by ``tool_name == "mkdir"`` and DELETEs.
    """
    try:
        async with session.begin_nested():
            rev = FolderRevision(
                folder_id=folder.id,
                search_space_id=search_space_id,
                name_before=None,
                parent_id_before=None,
                position_before=None,
                created_by_turn_id=turn_id,
                agent_action_id=action_id,
            )
            session.add(rev)
            await session.flush()
            await _mark_action_reversible(session, action_id=action_id)
            rev_id = rev.id
        if deferred_dispatches is None:
            await _dispatch_reversibility_update(action_id)
        elif action_id is not None:
            deferred_dispatches.append(int(action_id))
        return rev_id
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning(
            "kb_persistence: pre-mkdir snapshot for folder=%s failed: %s",
            folder.id,
            exc,
        )
        return None


# ---------------------------------------------------------------------------
# Commit body
# ---------------------------------------------------------------------------


async def commit_staged_filesystem_state(
    state: dict[str, Any] | AgentState,
    *,
    search_space_id: int,
    created_by_id: str | None,
    filesystem_mode: FilesystemMode = FilesystemMode.CLOUD,
    thread_id: int | None = None,
    dispatch_events: bool = True,
) -> dict[str, Any] | None:
    """Commit all staged filesystem changes; return the state delta for reducers.

    Shared between :class:`KnowledgeBasePersistenceMiddleware.aafter_agent`
    and the optional stream-task fallback.

    When ``flags.enable_action_log`` is on every destructive op also writes
    a ``DocumentRevision`` / ``FolderRevision`` snapshot bound to the
    originating ``AgentActionLog`` row via ``tool_call_id``. Snapshot
    durability is best-effort for non-destructive ops and STRICT for
    ``rm``/``rmdir`` (snapshot + DELETE share a SAVEPOINT — snapshot
    failure aborts the delete).
    """
    if filesystem_mode != FilesystemMode.CLOUD:
        return None

    state_dict: dict[str, Any] = (
        dict(state)
        if isinstance(state, dict)
        else dict(getattr(state, "values", {}) or {})
    )

    files: dict[str, Any] = state_dict.get("files") or {}
    staged_dirs: list[str] = list(state_dict.get("staged_dirs") or [])
    staged_dir_tool_calls: dict[str, str] = dict(
        state_dict.get("staged_dir_tool_calls") or {}
    )
    pending_moves: list[dict[str, Any]] = list(state_dict.get("pending_moves") or [])
    pending_deletes: list[dict[str, Any]] = list(
        state_dict.get("pending_deletes") or []
    )
    pending_dir_deletes: list[dict[str, Any]] = list(
        state_dict.get("pending_dir_deletes") or []
    )
    dirty_paths: list[str] = list(state_dict.get("dirty_paths") or [])
    dirty_path_tool_calls: dict[str, str] = dict(
        state_dict.get("dirty_path_tool_calls") or {}
    )
    doc_id_by_path: dict[str, int] = dict(state_dict.get("doc_id_by_path") or {})
    kb_anon_doc = state_dict.get("kb_anon_doc")

    if kb_anon_doc:
        temp_paths = [
            p
            for p in files
            if isinstance(p, str) and _basename(p).startswith(_TEMP_PREFIX)
        ]
        return {
            "dirty_paths": [_CLEAR],
            "staged_dirs": [_CLEAR],
            "staged_dir_tool_calls": {_CLEAR: True},
            "pending_moves": [_CLEAR],
            "pending_deletes": [_CLEAR],
            "pending_dir_deletes": [_CLEAR],
            "dirty_path_tool_calls": {_CLEAR: True},
            "files": dict.fromkeys(temp_paths),
        }

    if not (
        staged_dirs
        or pending_moves
        or dirty_paths
        or pending_deletes
        or pending_dir_deletes
    ):
        return None

    flags = get_flags()
    snapshot_enabled = flags.enable_action_log

    # De-duplicate pending deletes per-path while preserving the latest
    # tool_call_id (the one the user is most likely to revert via the UI).
    file_delete_paths: dict[str, str] = {}
    for entry in pending_deletes:
        if not isinstance(entry, dict):
            continue
        path = str(entry.get("path") or "")
        if path:
            file_delete_paths[path] = str(entry.get("tool_call_id") or "")
    dir_delete_paths: dict[str, str] = {}
    for entry in pending_dir_deletes:
        if not isinstance(entry, dict):
            continue
        path = str(entry.get("path") or "")
        if path:
            dir_delete_paths[path] = str(entry.get("tool_call_id") or "")

    committed_creates: list[dict[str, Any]] = []
    committed_updates: list[dict[str, Any]] = []
    committed_deletes: list[dict[str, Any]] = []
    committed_folder_deletes: list[dict[str, Any]] = []
    discarded: list[str] = []
    applied_moves: list[dict[str, Any]] = []
    doc_id_path_tombstones: dict[str, int | None] = {}
    tree_changed = False
    # Reversibility-flip dispatches are deferred until AFTER the outer
    # ``session.commit()`` succeeds. Dispatching from inside the
    # SAVEPOINT chain while the outer transaction is still pending
    # would emit ``reversible=true`` for rows whose snapshots get rolled
    # back if the final commit raises. Snapshot helpers append on
    # success; we drain this list after commit and silently abandon it
    # on rollback so the UI stays consistent with durable state.
    deferred_dispatches: list[int] = []

    try:
        async with shielded_async_session() as session:
            # ------------------------------------------------------------------
            # Resolve action-id bindings up front. One SELECT per turn for all
            # tool_call_ids, NOT one per op — important because a turn that
            # touches 50 paths would otherwise issue 50 lookups.
            # ------------------------------------------------------------------
            action_id_by_call: dict[str, int] = {}
            if snapshot_enabled and thread_id is not None:
                tool_call_ids: set[str] = set()
                tool_call_ids.update(
                    tcid for tcid in staged_dir_tool_calls.values() if tcid
                )
                for move in pending_moves:
                    tcid = str(move.get("tool_call_id") or "")
                    if tcid:
                        tool_call_ids.add(tcid)
                tool_call_ids.update(
                    tcid for tcid in dirty_path_tool_calls.values() if tcid
                )
                tool_call_ids.update(
                    tcid for tcid in file_delete_paths.values() if tcid
                )
                tool_call_ids.update(tcid for tcid in dir_delete_paths.values() if tcid)
                action_id_by_call = await _find_action_ids_batch(
                    session,
                    thread_id=thread_id,
                    tool_call_ids=tool_call_ids,
                )

            def _action_id_for(tool_call_id: str | None) -> int | None:
                if not snapshot_enabled or not tool_call_id:
                    return None
                return action_id_by_call.get(str(tool_call_id))

            turn_id_for_revision = (
                next(iter(action_id_by_call), None) if action_id_by_call else None
            )

            # ------------------------------------------------------------------
            # 1. staged_dirs -> Folder rows. Snapshot post-flush so the new
            # folder_id is available for the FK.
            # ------------------------------------------------------------------
            for folder_path in staged_dirs:
                if not isinstance(folder_path, str):
                    continue
                if not folder_path.startswith(DOCUMENTS_ROOT):
                    continue
                folder_parts_full = _split_folder_path(folder_path)
                if not folder_parts_full:
                    continue
                folder_id = await _ensure_folder_hierarchy(
                    session,
                    search_space_id=search_space_id,
                    created_by_id=created_by_id,
                    folder_parts=folder_parts_full,
                )
                tree_changed = True

                if snapshot_enabled and folder_id is not None:
                    tcid = staged_dir_tool_calls.get(folder_path)
                    action_id = _action_id_for(tcid)
                    if action_id is not None:
                        # Re-read the folder for the snapshot.
                        result = await session.execute(
                            select(Folder).where(Folder.id == folder_id)
                        )
                        folder_row = result.scalar_one_or_none()
                        if folder_row is not None:
                            await _snapshot_folder_pre_mkdir(
                                session,
                                folder=folder_row,
                                action_id=action_id,
                                search_space_id=search_space_id,
                                turn_id=tcid,
                                deferred_dispatches=deferred_dispatches,
                            )

            # ------------------------------------------------------------------
            # 2. pending_moves. Snapshot pre-move (in-place restore on revert).
            # ------------------------------------------------------------------
            for move in pending_moves:
                source = str(move.get("source") or "")
                if snapshot_enabled and source:
                    tcid = str(move.get("tool_call_id") or "")
                    action_id = _action_id_for(tcid)
                    if action_id is not None:
                        # Resolve the doc to snapshot BEFORE we mutate it.
                        doc_id_pre = doc_id_by_path.get(source)
                        document_pre: Document | None = None
                        if doc_id_pre is not None:
                            res_pre = await session.execute(
                                select(Document).where(
                                    Document.id == doc_id_pre,
                                    Document.search_space_id == search_space_id,
                                )
                            )
                            document_pre = res_pre.scalar_one_or_none()
                        if document_pre is None:
                            document_pre = await virtual_path_to_doc(
                                session,
                                search_space_id=search_space_id,
                                virtual_path=source,
                            )
                        if document_pre is not None:
                            await _snapshot_document_pre_move(
                                session,
                                doc=document_pre,
                                action_id=action_id,
                                search_space_id=search_space_id,
                                turn_id=tcid,
                                deferred_dispatches=deferred_dispatches,
                            )

                applied = await _apply_move(
                    session,
                    search_space_id=search_space_id,
                    created_by_id=created_by_id,
                    move=move,
                    doc_id_by_path=doc_id_by_path,
                    doc_id_path_tombstones=doc_id_path_tombstones,
                )
                if applied:
                    applied_moves.append(applied)
                    tree_changed = True

            move_alias = {
                m["source"]: m["dest"] for m in pending_moves if m.get("source")
            }

            def _final_path(path: str) -> str:
                seen: set[str] = set()
                while path in move_alias and path not in seen:
                    seen.add(path)
                    path = move_alias[path]
                return path

            # ------------------------------------------------------------------
            # 3. dirty_paths -> writes/edits. Skip any path queued for ``rm``
            # this turn so a write+rm sequence doesn't recreate the doc.
            # ------------------------------------------------------------------
            kb_dirty_seen: set[str] = set()
            kb_dirty: list[str] = []
            kb_dirty_origin: dict[str, str] = {}
            for raw in dirty_paths:
                if not isinstance(raw, str):
                    continue
                final = _final_path(raw)
                if not final.startswith(DOCUMENTS_ROOT + "/"):
                    continue
                if final in kb_dirty_seen:
                    continue
                if final in file_delete_paths:
                    discarded.append(final)
                    continue
                kb_dirty_seen.add(final)
                kb_dirty.append(final)
                kb_dirty_origin[final] = raw

            for path in kb_dirty:
                basename = _basename(path)
                if basename.startswith(_TEMP_PREFIX):
                    discarded.append(path)
                    continue
                file_data = files.get(path)
                if not isinstance(file_data, dict):
                    continue
                content = "\n".join(file_data.get("content") or [])
                doc_id = doc_id_by_path.get(path)
                # Path ↔ tool_call_id binding: the dirty_paths list dedupes via
                # _add_unique_reducer, so we look up the latest tool_call_id by
                # path (or by the un-renamed origin).
                origin = kb_dirty_origin.get(path, path)
                tcid = dirty_path_tool_calls.get(path) or dirty_path_tool_calls.get(
                    origin
                )
                action_id = _action_id_for(tcid)

                if doc_id is None:
                    # The in-memory ``doc_id_by_path`` is per-thread and starts
                    # empty in every new chat. If the agent writes to a path
                    # that already exists in the DB (e.g. a previous chat's
                    # ``notes.md``), we must NOT try to INSERT — it would hit
                    # ``unique_identifier_hash`` (path-derived). Look up the
                    # existing doc and update it in place instead.
                    existing = await virtual_path_to_doc(
                        session,
                        search_space_id=search_space_id,
                        virtual_path=path,
                    )
                    if existing is not None:
                        doc_id = existing.id
                        doc_id_by_path[path] = existing.id
                if doc_id is not None:
                    if snapshot_enabled and action_id is not None:
                        result_doc = await session.execute(
                            select(Document).where(
                                Document.id == doc_id,
                                Document.search_space_id == search_space_id,
                            )
                        )
                        existing_doc = result_doc.scalar_one_or_none()
                        if existing_doc is not None:
                            await _snapshot_document_pre_write(
                                session,
                                doc=existing_doc,
                                action_id=action_id,
                                search_space_id=search_space_id,
                                turn_id=tcid,
                                deferred_dispatches=deferred_dispatches,
                            )
                    updated = await _update_document(
                        session,
                        doc_id=doc_id,
                        content=content,
                        virtual_path=path,
                        search_space_id=search_space_id,
                    )
                    if updated is not None:
                        committed_updates.append(
                            {
                                "id": updated.id,
                                "title": updated.title,
                                "documentType": DocumentType.NOTE.value,
                                "searchSpaceId": search_space_id,
                                "folderId": updated.folder_id,
                                "createdById": str(created_by_id)
                                if created_by_id
                                else None,
                                "virtualPath": path,
                            }
                        )
                else:
                    # Fresh create. Wrap each create in a SAVEPOINT so a
                    # residual ``IntegrityError`` (e.g. a deployment that
                    # hasn't run migration 133 yet, where
                    # ``documents.content_hash`` still carries its legacy
                    # global UNIQUE constraint) rolls back only this one
                    # create instead of poisoning the whole turn.
                    placeholder_revision_id: int | None = None
                    if snapshot_enabled and action_id is not None:
                        placeholder_revision_id = await _snapshot_document_pre_create(
                            session,
                            action_id=action_id,
                            search_space_id=search_space_id,
                            turn_id=tcid,
                            deferred_dispatches=deferred_dispatches,
                        )
                    try:
                        async with session.begin_nested():
                            new_doc = await _create_document(
                                session,
                                virtual_path=path,
                                content=content,
                                search_space_id=search_space_id,
                                created_by_id=created_by_id,
                            )
                    except ValueError as exc:
                        logger.warning(
                            "kb_persistence: skipping %s create: %s", path, exc
                        )
                        # Roll back the placeholder revision since the create
                        # never happened.
                        if placeholder_revision_id is not None:
                            await session.execute(
                                delete(DocumentRevision).where(
                                    DocumentRevision.id == placeholder_revision_id
                                )
                            )
                        continue
                    except IntegrityError as exc:
                        msg = str(exc.orig) if exc.orig is not None else str(exc)
                        logger.error(
                            "kb_persistence: IntegrityError creating %s: %s. "
                            "If this mentions content_hash, run alembic "
                            "upgrade to apply migration 133 which drops the "
                            "global UNIQUE constraint on documents.content_hash.",
                            path,
                            msg,
                        )
                        if placeholder_revision_id is not None:
                            await session.execute(
                                delete(DocumentRevision).where(
                                    DocumentRevision.id == placeholder_revision_id
                                )
                            )
                        continue
                    doc_id_by_path[path] = new_doc.id
                    if placeholder_revision_id is not None:
                        await session.execute(
                            update(DocumentRevision)
                            .where(DocumentRevision.id == placeholder_revision_id)
                            .values(document_id=new_doc.id)
                        )
                    committed_creates.append(
                        {
                            "id": new_doc.id,
                            "title": new_doc.title,
                            "documentType": DocumentType.NOTE.value,
                            "searchSpaceId": search_space_id,
                            "folderId": new_doc.folder_id,
                            "createdById": str(created_by_id)
                            if created_by_id
                            else None,
                            "virtualPath": path,
                        }
                    )
                    tree_changed = True

            # ------------------------------------------------------------------
            # 4. pending_deletes -> ``rm``. STRICT durability: snapshot + DELETE
            # share a SAVEPOINT. If the snapshot insert fails, the DELETE
            # rolls back too and we surface the error rather than silently
            # making the data irreversible.
            # ------------------------------------------------------------------
            for raw_path, tcid in file_delete_paths.items():
                final = _final_path(raw_path)
                if not final.startswith(DOCUMENTS_ROOT + "/"):
                    continue
                action_id = _action_id_for(tcid)

                # Resolve the doc.
                doc_id_for_delete = doc_id_by_path.get(final)
                document_to_delete: Document | None = None
                if doc_id_for_delete is not None:
                    result = await session.execute(
                        select(Document).where(
                            Document.id == doc_id_for_delete,
                            Document.search_space_id == search_space_id,
                        )
                    )
                    document_to_delete = result.scalar_one_or_none()
                if document_to_delete is None:
                    document_to_delete = await virtual_path_to_doc(
                        session,
                        search_space_id=search_space_id,
                        virtual_path=final,
                    )
                if document_to_delete is None:
                    logger.info(
                        "kb_persistence: skipping rm %s (target not found)", final
                    )
                    continue

                doc_pk = document_to_delete.id
                doc_title = document_to_delete.title
                doc_folder_id = document_to_delete.folder_id

                try:
                    async with session.begin_nested():
                        # Strict: snapshot first; failure aborts the delete.
                        if snapshot_enabled and action_id is not None:
                            chunks = await _load_chunks_for_snapshot(
                                session, doc_id=doc_pk
                            )
                            payload = _doc_revision_payload(
                                document_to_delete, chunks_before=chunks
                            )
                            rev = DocumentRevision(
                                document_id=doc_pk,
                                search_space_id=search_space_id,
                                created_by_turn_id=tcid,
                                agent_action_id=action_id,
                                **payload,
                            )
                            session.add(rev)
                            await session.flush()
                            await _mark_action_reversible(session, action_id=action_id)
                        await session.execute(
                            delete(Document).where(Document.id == doc_pk)
                        )
                except Exception as exc:
                    logger.exception(
                        "kb_persistence: strict rm SAVEPOINT for path=%s failed: %s",
                        final,
                        exc,
                    )
                    continue

                # B1 — SAVEPOINT released. Defer the reversibility-flip
                # dispatch until AFTER the outer commit succeeds so we
                # never tell the UI a row is reversible if its snapshot
                # gets rolled back.
                if snapshot_enabled and action_id is not None:
                    deferred_dispatches.append(int(action_id))

                doc_id_by_path.pop(final, None)
                doc_id_path_tombstones[final] = None
                committed_deletes.append(
                    {
                        "id": doc_pk,
                        "title": doc_title,
                        "documentType": DocumentType.NOTE.value,
                        "searchSpaceId": search_space_id,
                        "folderId": doc_folder_id,
                        "createdById": str(created_by_id) if created_by_id else None,
                        "virtualPath": final,
                    }
                )
                tree_changed = True

            # ------------------------------------------------------------------
            # 5. pending_dir_deletes -> ``rmdir``. STRICT durability + final
            # emptiness check (after step 4's deletes have run, an "empty
            # mid-turn" directory really IS empty in DB now).
            # ------------------------------------------------------------------
            for raw_path, tcid in dir_delete_paths.items():
                final = _final_path(raw_path)
                if not final.startswith(DOCUMENTS_ROOT + "/"):
                    continue
                action_id = _action_id_for(tcid)

                folder_parts = _split_folder_path(final)
                if not folder_parts:
                    continue
                folder_id = await _resolve_folder_id(
                    session,
                    search_space_id=search_space_id,
                    folder_parts=folder_parts,
                )
                if folder_id is None:
                    logger.info(
                        "kb_persistence: skipping rmdir %s (folder not found)", final
                    )
                    continue

                # Re-check emptiness against in-DB state.
                docs_in_folder = await session.execute(
                    select(Document.id)
                    .where(Document.folder_id == folder_id)
                    .where(Document.search_space_id == search_space_id)
                    .limit(1)
                )
                if docs_in_folder.scalar_one_or_none() is not None:
                    logger.warning(
                        "kb_persistence: refusing rmdir %s — non-empty at commit time",
                        final,
                    )
                    continue
                child_folders = await session.execute(
                    select(Folder.id)
                    .where(Folder.parent_id == folder_id)
                    .where(Folder.search_space_id == search_space_id)
                    .limit(1)
                )
                if child_folders.scalar_one_or_none() is not None:
                    logger.warning(
                        "kb_persistence: refusing rmdir %s — has child folders "
                        "at commit time",
                        final,
                    )
                    continue

                folder_to_delete_res = await session.execute(
                    select(Folder).where(Folder.id == folder_id)
                )
                folder_to_delete = folder_to_delete_res.scalar_one_or_none()
                if folder_to_delete is None:
                    continue

                folder_pk = folder_to_delete.id
                folder_name = folder_to_delete.name
                folder_parent_id = folder_to_delete.parent_id
                folder_position = folder_to_delete.position

                try:
                    async with session.begin_nested():
                        if snapshot_enabled and action_id is not None:
                            rev = FolderRevision(
                                folder_id=folder_pk,
                                search_space_id=search_space_id,
                                name_before=folder_name,
                                parent_id_before=folder_parent_id,
                                position_before=folder_position,
                                created_by_turn_id=tcid,
                                agent_action_id=action_id,
                            )
                            session.add(rev)
                            await session.flush()
                            await _mark_action_reversible(session, action_id=action_id)
                        await session.execute(
                            delete(Folder).where(Folder.id == folder_pk)
                        )
                except Exception as exc:
                    logger.exception(
                        "kb_persistence: strict rmdir SAVEPOINT for path=%s failed: %s",
                        final,
                        exc,
                    )
                    continue

                # B1 — SAVEPOINT released. Defer the reversibility-flip
                # dispatch until AFTER the outer commit succeeds so we
                # never tell the UI a row is reversible if its snapshot
                # gets rolled back.
                if snapshot_enabled and action_id is not None:
                    deferred_dispatches.append(int(action_id))

                committed_folder_deletes.append(
                    {
                        "id": folder_pk,
                        "name": folder_name,
                        "searchSpaceId": search_space_id,
                        "parentId": folder_parent_id,
                        "virtualPath": final,
                    }
                )
                tree_changed = True

            await session.commit()
    except Exception:  # pragma: no cover - rollback safety net
        logger.exception(
            "kb_persistence: commit failed (search_space=%s)", search_space_id
        )
        # Outer commit raised — every SAVEPOINT-released change above
        # (snapshots + reversibility flips) is now rolled back. Drop
        # the deferred SSE dispatches so the UI stays consistent with
        # durable state.
        deferred_dispatches.clear()
        return None

    # Outer commit succeeded; flush deferred reversibility-flip
    # dispatches now so the chat tool card can light up its Revert
    # button without re-fetching ``GET /threads/.../actions``. De-dup
    # to avoid emitting the same id twice (e.g. write-then-rm in the
    # same turn dispatches once for each snapshot site).
    if deferred_dispatches and dispatch_events:
        for action_id in dict.fromkeys(deferred_dispatches):
            try:
                await _dispatch_reversibility_update(action_id)
            except Exception:
                logger.debug(
                    "kb_persistence: deferred reversibility dispatch failed for action_id=%s",
                    action_id,
                    exc_info=True,
                )

    if dispatch_events:
        for payload in committed_creates:
            try:
                dispatch_custom_event("document_created", payload)
            except Exception:
                logger.exception(
                    "kb_persistence: failed to dispatch document_created event"
                )
        for payload in committed_updates:
            try:
                dispatch_custom_event("document_updated", payload)
            except Exception:
                logger.exception(
                    "kb_persistence: failed to dispatch document_updated event"
                )
        for payload in committed_deletes:
            try:
                dispatch_custom_event("document_deleted", payload)
            except Exception:
                logger.exception(
                    "kb_persistence: failed to dispatch document_deleted event"
                )
        for payload in committed_folder_deletes:
            try:
                dispatch_custom_event("folder_deleted", payload)
            except Exception:
                logger.exception(
                    "kb_persistence: failed to dispatch folder_deleted event"
                )

    temp_paths = [
        p for p in files if isinstance(p, str) and _basename(p).startswith(_TEMP_PREFIX)
    ]

    # Tombstone every committed-delete path so a stale ``state["files"]`` entry
    # (which als_info would otherwise interpret as content) cannot survive into
    # the next turn and make a now-empty folder look non-empty.
    deleted_file_paths = [
        str(payload.get("virtualPath") or "")
        for payload in committed_deletes
        if payload.get("virtualPath")
    ]

    doc_id_update: dict[str, int | None] = {**doc_id_path_tombstones}
    for payload in committed_creates:
        doc_id_update[str(payload.get("virtualPath") or "")] = int(payload["id"])

    delta: dict[str, Any] = {
        "dirty_paths": [_CLEAR],
        "staged_dirs": [_CLEAR],
        "staged_dir_tool_calls": {_CLEAR: True},
        "pending_moves": [_CLEAR],
        "pending_deletes": [_CLEAR],
        "pending_dir_deletes": [_CLEAR],
        "dirty_path_tool_calls": {_CLEAR: True},
    }
    files_delta: dict[str, Any] = {}
    if temp_paths:
        files_delta.update(dict.fromkeys(temp_paths))
    for path in deleted_file_paths:
        files_delta[path] = None
    if files_delta:
        delta["files"] = files_delta
    if doc_id_update:
        delta["doc_id_by_path"] = doc_id_update
    if tree_changed:
        delta["tree_version"] = int(state_dict.get("tree_version") or 0) + 1

    # Avoid 'unused' lint when turn_id_for_revision was only useful for
    # diagnostic purposes inside the SAVEPOINT chain above.
    _ = turn_id_for_revision

    logger.info(
        "kb_persistence: commit (search_space=%s) creates=%d updates=%d "
        "moves=%d staged_dirs=%d deletes=%d folder_deletes=%d discarded=%d",
        search_space_id,
        len(committed_creates),
        len(committed_updates),
        len(applied_moves),
        len(staged_dirs),
        len(committed_deletes),
        len(committed_folder_deletes),
        len(discarded),
    )
    return delta


# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------


class KnowledgeBasePersistenceMiddleware(AgentMiddleware):  # type: ignore[type-arg]
    """End-of-turn cloud persistence for the SurfSense filesystem agent."""

    tools = ()
    state_schema = SurfSenseFilesystemState

    def __init__(
        self,
        *,
        search_space_id: int,
        created_by_id: str | None,
        filesystem_mode: FilesystemMode,
        thread_id: int | None = None,
    ) -> None:
        self.search_space_id = search_space_id
        self.created_by_id = created_by_id
        self.filesystem_mode = filesystem_mode
        self.thread_id = thread_id

    async def aafter_agent(  # type: ignore[override]
        self,
        state: AgentState,
        runtime: Runtime[Any],
    ) -> dict[str, Any] | None:
        del runtime
        if self.filesystem_mode != FilesystemMode.CLOUD:
            return None
        return await commit_staged_filesystem_state(
            state,
            search_space_id=self.search_space_id,
            created_by_id=self.created_by_id,
            filesystem_mode=self.filesystem_mode,
            thread_id=self.thread_id,
        )


__all__ = [
    "KnowledgeBasePersistenceMiddleware",
    "commit_staged_filesystem_state",
]
