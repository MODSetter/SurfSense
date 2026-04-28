"""End-of-turn persistence for the cloud-mode SurfSense filesystem.

This middleware runs ``aafter_agent`` once per turn (cloud only). It commits
all staged folder creations, file moves, and content writes/edits to
Postgres in a single ordered pass:

1. Materialize ``staged_dirs`` into ``Folder`` rows.
2. Apply ``pending_moves`` in order (chained moves resolved via
   ``doc_id_by_path``).
3. Normalize ``dirty_paths`` through ``pending_moves`` so write-then-move
   sequences commit at the final path.
4. Commit content writes / edits for ``/documents/*`` paths, skipping
   ``temp_*`` basenames.

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
from langchain_core.callbacks import dispatch_custom_event
from langgraph.runtime import Runtime
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

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
    Chunk,
    Document,
    DocumentType,
    Folder,
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
    # Guard against the unique_identifier_hash constraint: another row at the
    # same virtual_path (this search space) already owns the hash. Callers are
    # expected to upsert via the wrapper, but this defends against bypasses
    # and gives a clean ValueError instead of a session-poisoning IntegrityError.
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
    content_hash = generate_content_hash(content, search_space_id)
    content_collision = await session.execute(
        select(Document.id).where(
            Document.search_space_id == search_space_id,
            Document.content_hash == content_hash,
        )
    )
    if content_collision.scalar_one_or_none() is not None:
        raise ValueError(
            f"a document with identical content already exists for path '{virtual_path}'"
        )
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
# Commit body
# ---------------------------------------------------------------------------


async def commit_staged_filesystem_state(
    state: dict[str, Any] | AgentState,
    *,
    search_space_id: int,
    created_by_id: str | None,
    filesystem_mode: FilesystemMode = FilesystemMode.CLOUD,
    dispatch_events: bool = True,
) -> dict[str, Any] | None:
    """Commit all staged filesystem changes; return the state delta for reducers.

    Shared between :class:`KnowledgeBasePersistenceMiddleware.aafter_agent`
    and the optional stream-task fallback.
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
    pending_moves: list[dict[str, Any]] = list(state_dict.get("pending_moves") or [])
    dirty_paths: list[str] = list(state_dict.get("dirty_paths") or [])
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
            "pending_moves": [_CLEAR],
            "files": dict.fromkeys(temp_paths),
        }

    if not (staged_dirs or pending_moves or dirty_paths):
        return None

    committed_creates: list[dict[str, Any]] = []
    committed_updates: list[dict[str, Any]] = []
    discarded: list[str] = []
    applied_moves: list[dict[str, Any]] = []
    doc_id_path_tombstones: dict[str, int | None] = {}
    tree_changed = False

    try:
        async with shielded_async_session() as session:
            for folder_path in staged_dirs:
                if not isinstance(folder_path, str):
                    continue
                if not folder_path.startswith(DOCUMENTS_ROOT):
                    continue
                rel = folder_path[len(DOCUMENTS_ROOT) :].strip("/")
                folder_parts_full = [p for p in rel.split("/") if p]
                if not folder_parts_full:
                    continue
                await _ensure_folder_hierarchy(
                    session,
                    search_space_id=search_space_id,
                    created_by_id=created_by_id,
                    folder_parts=folder_parts_full,
                )
                tree_changed = True

            for move in pending_moves:
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

            kb_dirty_seen: set[str] = set()
            kb_dirty: list[str] = []
            for raw in dirty_paths:
                if not isinstance(raw, str):
                    continue
                final = _final_path(raw)
                if not final.startswith(DOCUMENTS_ROOT + "/"):
                    continue
                if final in kb_dirty_seen:
                    continue
                kb_dirty_seen.add(final)
                kb_dirty.append(final)

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
                    try:
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
                        continue
                    doc_id_by_path[path] = new_doc.id
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

            await session.commit()
    except Exception:  # pragma: no cover - rollback safety net
        logger.exception(
            "kb_persistence: commit failed (search_space=%s)", search_space_id
        )
        return None

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

    temp_paths = [
        p for p in files if isinstance(p, str) and _basename(p).startswith(_TEMP_PREFIX)
    ]

    doc_id_update: dict[str, int | None] = {**doc_id_path_tombstones}
    for payload in committed_creates:
        doc_id_update[str(payload.get("virtualPath") or "")] = int(payload["id"])

    delta: dict[str, Any] = {
        "dirty_paths": [_CLEAR],
        "staged_dirs": [_CLEAR],
        "pending_moves": [_CLEAR],
    }
    if temp_paths:
        delta["files"] = dict.fromkeys(temp_paths)
    if doc_id_update:
        delta["doc_id_by_path"] = doc_id_update
    if tree_changed:
        delta["tree_version"] = int(state_dict.get("tree_version") or 0) + 1

    logger.info(
        "kb_persistence: commit (search_space=%s) creates=%d updates=%d "
        "moves=%d staged_dirs=%d discarded=%d",
        search_space_id,
        len(committed_creates),
        len(committed_updates),
        len(applied_moves),
        len(staged_dirs),
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
    ) -> None:
        self.search_space_id = search_space_id
        self.created_by_id = created_by_id
        self.filesystem_mode = filesystem_mode

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
        )


__all__ = [
    "KnowledgeBasePersistenceMiddleware",
    "commit_staged_filesystem_state",
]
