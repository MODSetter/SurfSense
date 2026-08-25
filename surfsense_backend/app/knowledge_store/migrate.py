"""Phase 5 seeder: export a workspace's documents into its store as one seed revision.

Parity is **byte identity** (content addresses compared, no file reads), never a
reindex — the seed copies bytes out of Postgres, so the existing chunk index is
already correct by construction. Runs before the flip, so unlike the recorder it
never guards on ``KNOWLEDGE_STORE_ENABLED``.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.knowledge_store import KnowledgeStore
from app.knowledge_store.engines.base import TrackedPath
from app.knowledge_store.identities import MIGRATION_IDENTITY
from app.knowledge_store.paths import (
    DOCUMENTS_ROOT,
    KEEP_FILE,
    allocate_path,
    build_path_index,
    recorded_virtual_path,
    to_store_path,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class MigrationReport:
    """Outcome of one seed run; ``ok`` is the flip guard's verdict."""

    workspace_id: int | str
    dry_run: bool
    #: Revision recorded by this run; ``None`` on dry runs and no-op re-seeds.
    seeded_revision: str | None
    files: int
    missing: list[str] = field(default_factory=list)
    extra: list[str] = field(default_factory=list)
    mismatched: list[str] = field(default_factory=list)
    #: Failure this run captured instead of raising (e.g. an expired write
    #: lock); the parity fields describe whatever could still be inspected.
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None and not (
            self.missing or self.extra or self.mismatched
        )


async def seed_workspace(
    workspace_id: int | str,
    files: Mapping[str, str],
    *,
    dry_run: bool = False,
) -> MigrationReport:
    """Record ``files`` (store path → markdown) as one seed revision, then verify.

    Idempotent: re-seeding unchanged content records nothing. ``dry_run`` skips
    the write and only reports parity of ``files`` against the store's head.

    Never raises: any failure is returned as ``MigrationReport.error`` so a
    fleet-wide run records it and continues with the next workspace.
    """
    try:
        return await _seed_and_verify(workspace_id, files, dry_run=dry_run)
    except Exception as exc:
        return _failure_report(workspace_id, dry_run, len(files), exc)


async def _seed_and_verify(
    workspace_id: int | str,
    files: Mapping[str, str],
    *,
    dry_run: bool,
) -> MigrationReport:
    """``seed_workspace``'s body; raises freely, the wrapper reports."""
    store = KnowledgeStore.for_workspace(workspace_id)

    seeded_revision: str | None = None
    error: str | None = None
    if not dry_run and files:
        try:
            # Seed = "make the tree exactly this": orphans from documents
            # deleted in Postgres since a prior seed are removed, so
            # re-seeding converges.
            orphans = [
                t.path for t in await _tracked_paths(store) if t.path not in files
            ]
            async with store.transaction(
                message=f"migration: seed {len(files)} document(s)",
                author=MIGRATION_IDENTITY,
            ) as tx:
                for path, markdown in files.items():
                    tx.write(path, markdown.encode())
                for path in orphans:
                    tx.remove(path)
            seeded_revision = tx.revision
        except Exception as exc:
            # Caught here, not by the wrapper, so parity still runs and the
            # report shows what state the failed write left behind.
            error = f"{type(exc).__name__}: {exc}"

    # .keep is a folder marker, not document content: git owns it — it is how an
    # empty folder survives — and a folder that later gains a document keeps its
    # now-redundant marker. Parity is document bytes, so a marker on either side
    # is never drift; counting one would alarm such a folder forever and draw an
    # hourly repair reindex that cannot remove a git file.
    tracked = {
        t.path: t.content_id
        for t in await _tracked_paths(store)
        if not _is_keep(t.path)
    }
    desired = {
        path: store.compute_content_id(markdown.encode())
        for path, markdown in files.items()
        if not _is_keep(path)
    }

    return MigrationReport(
        workspace_id=workspace_id,
        dry_run=dry_run,
        seeded_revision=seeded_revision,
        files=len(desired),
        missing=sorted(p for p in desired if p not in tracked),
        extra=sorted(p for p in tracked if p not in desired),
        mismatched=sorted(
            p for p, cid in desired.items() if p in tracked and tracked[p] != cid
        ),
        error=error,
    )


def _is_keep(store_path: str) -> bool:
    """A folder's ``.keep`` marker, which parity treats as structure, not content."""
    return store_path.rsplit("/", 1)[-1] == KEEP_FILE


def _failure_report(
    workspace_id: int | str, dry_run: bool, files: int, exc: Exception
) -> MigrationReport:
    """One workspace's failure as an outcome, so a fleet run can move on."""
    return MigrationReport(
        workspace_id=workspace_id,
        dry_run=dry_run,
        seeded_revision=None,
        files=files,
        error=f"{type(exc).__name__}: {exc}",
    )


async def _tracked_paths(store: KnowledgeStore) -> list[TrackedPath]:
    """Paths at the store's head; empty for a store with no history yet."""
    head = await store.get_current_revision()
    return await store.list_paths(head) if head else []


async def migrate_workspace(
    session: AsyncSession,
    workspace_id: int,
    *,
    dry_run: bool = False,
) -> MigrationReport:
    """Seed a workspace, applying the path law to each of its documents.

    A row that already records an authored-once path keeps it, whatever its
    status. An unmarked row is authored a fresh ``.md`` path via
    :func:`allocate_path`, in ``created_at`` then ``id`` order so collisions
    resolve the same way on every re-seed, and the chosen path is recorded back
    onto the row — unless it is still processing or failed before it was
    recorded, which the store is not yet meant to hold.

    Never raises: a failure fetching or mapping documents is returned as
    ``MigrationReport.error``.
    """
    from app.db import Document, DocumentStatus

    try:
        index = await build_path_index(session, workspace_id, populate_occupants=False)
        rows = await session.execute(
            select(
                Document.id,
                Document.title,
                Document.folder_id,
                Document.document_metadata,
                Document.path,
                Document.source_markdown,
                Document.content,
                Document.status,
            )
            .where(Document.workspace_id == workspace_id)
            .order_by(Document.created_at, Document.id)
        )
        files: dict[str, str] = {}
        seeded_paths: dict[int, str] = {}
        seeded_folder_ids: set[int] = set()
        taken: set[str] = set()
        pending: list[tuple[int, str, int | None, str]] = []
        # An unplaced row in one of these never earned a git file — still
        # processing, or failed before it was recorded — so the store is not yet
        # its to hold. A row that already records a path keeps its file whatever
        # its status.
        unready = {
            DocumentStatus.PENDING,
            DocumentStatus.PROCESSING,
            DocumentStatus.FAILED,
        }
        for (
            doc_id,
            title,
            folder_id,
            metadata,
            path,
            source_markdown,
            content,
            status,
        ) in rows:
            # "Pending..." is the pre-index placeholder; rows predating the
            # nullable source_markdown column hold text in content only.
            markdown = source_markdown or content
            if not markdown or markdown == "Pending...":
                continue
            recorded = recorded_virtual_path(metadata, path)
            if recorded is not None:
                taken.add(recorded)
                files[to_store_path(recorded)] = markdown
                seeded_paths[doc_id] = recorded
            elif DocumentStatus.get_state(status) in unready:
                # Seeding would write unfinished bytes, and the drift check would
                # then alarm on a row the reindex repair (git→Postgres) cannot
                # turn into a file. The live writer records it once it is ready.
                continue
            else:
                pending.append((doc_id, title, folder_id, markdown))
            if folder_id is not None:
                seeded_folder_ids.add(folder_id)
        # Author the unmarked rows only after every recorded path is reserved,
        # so a fresh name never lands on one a marked row already owns.
        for doc_id, title, folder_id, markdown in pending:
            placed = allocate_path(
                name=str(title or "untitled"),
                folder_parts=_folder_parts(index.folder_paths.get(folder_id)),
                taken=taken,
            )
            files[placed.store_path] = markdown
            seeded_paths[doc_id] = placed.virtual_path
        # Git holds no empty directory, so an explicitly-created folder with no
        # seeded document would vanish at the flip. Materialize each empty leaf
        # folder as a .keep; its ancestors ride along on that path.
        for keep_path in await _empty_folder_keeps(
            session, workspace_id, index, seeded_folder_ids
        ):
            files[keep_path] = ""
    except Exception as exc:
        return _failure_report(workspace_id, dry_run, 0, exc)

    report = await seed_workspace(workspace_id, files, dry_run=dry_run)
    if report.ok and not dry_run:
        await _record_seeded_paths(session, seeded_paths)
    return report


def _folder_parts(folder_path: str | None) -> list[str]:
    """Folder segments from a ``/documents/A/B`` path; ``[]`` at the root."""
    if not folder_path:
        return []
    rel = folder_path[len(DOCUMENTS_ROOT) :].strip("/")
    return rel.split("/") if rel else []


async def _empty_folder_keeps(
    session: AsyncSession,
    workspace_id: int,
    index,
    seeded_folder_ids: set[int],
) -> list[str]:
    """``.keep`` store paths for the folders no seeded document keeps alive.

    Only a leaf folder (one with no child folder) needs its own marker; a folder
    with children stays live through whichever descendant leaf gets the ``.keep``.
    """
    from app.db import Folder

    rows = (
        await session.execute(
            select(Folder.id, Folder.parent_id).where(
                Folder.workspace_id == workspace_id
            )
        )
    ).all()
    has_child = {parent_id for _id, parent_id in rows if parent_id is not None}
    keeps: list[str] = []
    for folder_id, _parent_id in rows:
        if folder_id in has_child or folder_id in seeded_folder_ids:
            continue
        folder_path = index.folder_paths.get(folder_id)
        if folder_path and folder_path != DOCUMENTS_ROOT:
            keeps.append(f"{to_store_path(folder_path)}/{KEEP_FILE}")
    return keeps


async def _record_seeded_paths(
    session: AsyncSession, seeded_paths: Mapping[int, str]
) -> None:
    """Record on each seeded row the path its content was written to.

    Best-effort: the seed revision is already committed, and a row without the
    column still resolves by derivation — it just cannot survive a retitle, which
    the next seed repairs.
    """
    from app.db import Document

    if not seeded_paths:
        return
    try:
        rows = await session.execute(
            select(Document).where(Document.id.in_(list(seeded_paths)))
        )
        for document in rows.scalars().all():
            document.path = seeded_paths[document.id]
        await session.commit()
    except Exception:
        logger.warning("Could not record seeded paths", exc_info=True)
        await session.rollback()
