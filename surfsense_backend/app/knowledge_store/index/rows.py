"""The row half of the projection: ``documents`` rows that mirror store paths.

Split out of :mod:`converge` because two callers need it at two different
moments. The indexer builds a row on its way to building chunks; the commit path
builds the same row on its own, seconds earlier, so the UI can show a note the
moment it is written (see :mod:`project`). Keeping the row logic in one place is
what stops those two moments from disagreeing about identity — which row a path
resolves to, and whether a move keeps its id.

Nothing here imports the indexing pipeline: the commit path pays this module's
import cost on every save.
"""

from __future__ import annotations

import logging
import re
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import Document, DocumentStatus, DocumentType, Workspace
from app.knowledge_store import KnowledgeStore
from app.knowledge_store.paths import (
    parse_documents_path,
    virtual_path_to_doc,
)
from app.services.folder_service import ensure_folder_hierarchy
from app.utils.document_converters import (
    generate_content_hash,
    generate_unique_identifier_hash,
)

logger = logging.getLogger(__name__)

# A non-NULL ``path`` marks a row as living at a store path, i.e. owned by this
# indexer. Rows without it (Slack, Notion, the folder indexers) are never pruned.

_USER_AUTHOR = re.compile(r"<([^@>]+)@users\.surfsense>")


async def upsert_row(
    session: AsyncSession,
    *,
    workspace_id: int,
    virtual_path: str,
    content: str,
    author_id: str,
    owned: dict[str, Document],
) -> tuple[Document, bool] | None:
    """Upsert the row for one path; ``None`` when the path names no document.

    Returns the row and whether this call created it. The row is flushed before
    returning because both callers need its id: the pipeline to attach chunks,
    the commit path to name the document in a UI event.

    ``document_type`` is assigned only for a new Git-authored row. Existing rows
    keep their type, so projection cannot demote an artifact or uploaded file to
    a note merely because all of them live under ``/documents``.
    """
    folder_parts, title = parse_documents_path(virtual_path)
    if not title:
        logger.info("Skipping path with no document name: %s", virtual_path)
        return None

    document = await resolve(session, workspace_id, virtual_path, owned)
    folder_id = await ensure_folder_hierarchy(
        session,
        workspace_id=workspace_id,
        created_by_id=author_id,
        folder_parts=folder_parts,
    )
    created = document is None
    if document is None:
        # Agent-authored note: title is the filename without the storage .md.
        # parse_documents_path keeps that .md so it never cuts an upload's own
        # ".md" name short.
        document = Document(
            title=title.removesuffix(".md") or title,
            document_type=DocumentType.NOTE,
            document_metadata={},
            path=virtual_path,
            content=content,
            content_hash=generate_content_hash(content, workspace_id),
            unique_identifier_hash=generate_unique_identifier_hash(
                DocumentType.NOTE, virtual_path, workspace_id
            ),
            source_markdown=content,
            workspace_id=workspace_id,
            folder_id=folder_id,
            created_by_id=author_id,
            status=DocumentStatus.pending(),
            updated_at=datetime.now(UTC),
        )
        session.add(document)
    else:
        # Title and type are Postgres-owned: re-deriving either from the path
        # would rename a document or demote an artifact on every reindex.
        document.folder_id = folder_id
        document.path = virtual_path
        document.source_markdown = content
        document.content_hash = generate_content_hash(content, workspace_id)
        document.updated_at = datetime.now(UTC)

    await session.flush()
    return document, created


def follow_rename(
    owned: dict[str, Document],
    workspace_id: int,
    from_virtual: str,
    to_virtual: str,
) -> None:
    """Point the row living at ``from_virtual`` at the path it moved to.

    A move has to leave the row's id alone: ``document_versions`` and an upload's
    stored original both cascade from it, and citations saved in earlier answers
    name it. Re-keying is the whole trick — the upsert of the new path then
    resolves to this row and updates it in place, rather than inserting one row
    and deleting the other.
    """
    document = owned.pop(from_virtual, None)
    if document is None:
        # Nothing marked at the old path: an unindexed file, or a recorder that
        # already moved the marker. Either way the upsert resolves it by itself.
        return
    owned[to_virtual] = document
    from_hash = generate_unique_identifier_hash(
        DocumentType.NOTE, from_virtual, workspace_id
    )
    if document.unique_identifier_hash == from_hash:
        # Carry resolve's fallback key along with the marker, or a later file at
        # the old path resolves to this row. Only when the key is the path's own:
        # an upload identifies by filename, and rewriting that would let a
        # re-upload of the same file insert a second row.
        document.unique_identifier_hash = generate_unique_identifier_hash(
            DocumentType.NOTE, to_virtual, workspace_id
        )


async def resolve(
    session: AsyncSession,
    workspace_id: int,
    virtual_path: str,
    owned: dict[str, Document],
) -> Document | None:
    """Find the row that already represents ``virtual_path``, if any.

    Uploads reach git through the recorder while their row keeps the identity the
    upload gave it (``FILE:<filename>``), so a NOTE-hash-only lookup would insert
    a second row for content that already has one — the same file twice in the
    tree and twice in search. Adopt whatever is already there instead.
    """
    marked = owned.get(virtual_path)
    if marked is not None:
        return marked

    unique_hash = generate_unique_identifier_hash(
        DocumentType.NOTE, virtual_path, workspace_id
    )
    result = await session.execute(
        select(Document).where(
            Document.workspace_id == workspace_id,
            Document.unique_identifier_hash == unique_hash,
        )
    )
    document = result.scalar_one_or_none()
    if document is not None:
        return document

    return await virtual_path_to_doc(
        session, workspace_id=workspace_id, virtual_path=virtual_path
    )


async def delete_row(
    session: AsyncSession,
    workspace_id: int,
    virtual_path: str,
    owned: dict[str, Document],
) -> Document | None:
    """Drop the document at a removed path; its chunks cascade.

    Returns the deleted row so a caller can name it in a UI event, or ``None``
    when there was nothing to delete.
    """
    document = await resolve(session, workspace_id, virtual_path, owned)
    if document is None:
        return None
    if document.path and document.path != virtual_path:
        # The row moved, it did not go away: the upsert has already claimed it, so
        # deleting here would drop what this same run just wrote. Reached when git
        # cannot see the move — a rewrite in flight leaves nothing to match, so it
        # arrives as a removal and an addition — while the recorder has moved the
        # path and left unique_identifier_hash, resolve's fallback, behind.
        return None
    from app.file_storage.service import purge_document_blobs

    await purge_document_blobs(session, document_ids=[document.id])
    owned.pop(virtual_path, None)
    await session.delete(document)
    return document


async def prune(
    session: AsyncSession, owned: dict[str, Document], live: set[str]
) -> int:
    """Delete indexer-owned rows whose path is no longer in the tree.

    Scoped to the ``path`` column, never to the workspace: connector rows (Slack,
    Notion, the folder indexers) have no path in the tree at all, and a
    workspace-wide prune would delete every one of them on the first rebuild.
    """
    stale = [
        (virtual_path, document)
        for virtual_path, document in owned.items()
        if virtual_path not in live
    ]
    if not stale:
        return 0

    from app.file_storage.service import purge_document_blobs

    # Blob metadata cascades with the document, so collect and purge every
    # reachable document/artifact blob while those rows still exist.
    await purge_document_blobs(
        session, document_ids=[document.id for _, document in stale]
    )
    for virtual_path, document in stale:
        await session.delete(document)
        owned.pop(virtual_path, None)
    return len(stale)


async def load_owned(session: AsyncSession, workspace_id: int) -> dict[str, Document]:
    """Indexer-owned rows for a workspace, keyed by the path they live at."""
    result = await session.execute(
        select(Document).where(
            Document.workspace_id == workspace_id,
            Document.path.is_not(None),
        )
    )
    owned: dict[str, Document] = {}
    for document in result.scalars():
        if document.path:
            owned[document.path] = document
    return owned


async def read_indexable(
    store: KnowledgeStore, revision: str, store_path: str
) -> str | None:
    """Decoded, non-blank text of a blob, or ``None`` when it can't be indexed.

    One unusable blob must not strand every other document in the revision, and
    both cases here are legal git: ``touch``ed files and binaries.
    """
    try:
        raw = await store.read_as_of(revision, store_path)
    except Exception:
        logger.warning("Skipping unreadable path %s", store_path, exc_info=True)
        return None
    try:
        content = raw.decode()
    except UnicodeDecodeError:
        logger.info("Skipping undecodable blob at %s", store_path)
        return None
    if not content.strip():
        logger.info("Skipping blank document at %s", store_path)
        return None
    return content


async def revision_author_id(
    store: KnowledgeStore, revision: str, workspace: Workspace
) -> str:
    """Actor for rows this run creates, derived from git — never passed in.

    A caller-supplied id would be erased by the next full rebuild, making the two
    paths disagree. Autonomous agent writes author as the agent, which carries no
    user id, so those fall back to the workspace owner: ``created_by_id`` is
    required and rejects blanks, and agent writes are the whole point of indexing.
    """
    owner = str(workspace.user_id)
    try:
        revisions = await store.list_revisions(limit=1)
    except Exception:
        logger.warning("Could not read revision author for %s", revision, exc_info=True)
        return owner
    if not revisions:
        return owner
    return _author_user_id(revisions[0].author) or owner


def _author_user_id(author: str) -> str | None:
    """User id encoded in a revision author, or ``None`` for the agent."""
    match = _USER_AUTHOR.search(author or "")
    if match is None:
        return None
    try:
        return str(uuid.UUID(match.group(1)))
    except ValueError:
        return None
