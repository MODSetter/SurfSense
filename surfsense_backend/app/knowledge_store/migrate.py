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
    PATH_MARKER,
    allocate_path,
    build_path_index,
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

    tracked = {t.path: t.content_id for t in await _tracked_paths(store)}
    desired = {
        path: store.compute_content_id(markdown.encode())
        for path, markdown in files.items()
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

    A row that already records an authored-once path keeps it. An unmarked row
    is authored a fresh ``.md`` path via :func:`allocate_path`, in ``created_at``
    then ``id`` order so collisions resolve the same way on every re-seed. The
    chosen path is recorded back onto the row.

    Never raises: a failure fetching or mapping documents is returned as
    ``MigrationReport.error``.
    """
    from app.db import Document

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
            )
            .where(Document.workspace_id == workspace_id)
            .order_by(Document.created_at, Document.id)
        )
        files: dict[str, str] = {}
        seeded_paths: dict[int, str] = {}
        taken: set[str] = set()
        pending: list[tuple[int, str, int | None, str]] = []
        for doc_id, title, folder_id, metadata, path, source_markdown, content in rows:
            # "Pending..." is the pre-index placeholder; rows predating the
            # nullable source_markdown column hold text in content only.
            markdown = source_markdown or content
            if not markdown or markdown == "Pending...":
                continue
            recorded = _recorded_path(path, metadata)
            if recorded is not None:
                taken.add(recorded)
                files[to_store_path(recorded)] = markdown
                seeded_paths[doc_id] = recorded
            else:
                pending.append((doc_id, title, folder_id, markdown))
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
    except Exception as exc:
        return _failure_report(workspace_id, dry_run, 0, exc)

    report = await seed_workspace(workspace_id, files, dry_run=dry_run)
    if report.ok and not dry_run:
        await _record_seeded_paths(session, seeded_paths)
    return report


def _recorded_path(path: str | None, metadata: Mapping[str, str] | None) -> str | None:
    """The authored-once path a row already carries, column before marker."""
    for value in (path, (metadata or {}).get(PATH_MARKER)):
        if isinstance(value, str) and value.startswith(f"{DOCUMENTS_ROOT}/"):
            return value
    return None


def _folder_parts(folder_path: str | None) -> list[str]:
    """Folder segments from a ``/documents/A/B`` path; ``[]`` at the root."""
    if not folder_path:
        return []
    rel = folder_path[len(DOCUMENTS_ROOT) :].strip("/")
    return rel.split("/") if rel else []


async def _record_seeded_paths(
    session: AsyncSession, seeded_paths: Mapping[int, str]
) -> None:
    """Mark each seeded row with the path its content was written to.

    Only rows whose marker would change are touched, so a re-seed of an already
    marked workspace writes nothing. Best-effort: the seed revision is already
    committed, and an unmarked row still resolves by derivation — it just cannot
    survive a retitle, which the next seed repairs.
    """
    from app.db import Document

    if not seeded_paths:
        return
    try:
        rows = await session.execute(
            select(Document).where(Document.id.in_(list(seeded_paths)))
        )
        for document in rows.scalars().all():
            path = seeded_paths[document.id]
            document.path = path
            metadata = dict(document.document_metadata or {})
            if metadata.get(PATH_MARKER) == path:
                continue
            metadata[PATH_MARKER] = path
            # Reassigned, not mutated: SQLAlchemy tracks JSON columns by identity.
            document.document_metadata = metadata
        await session.commit()
    except Exception:
        logger.warning("Could not record seeded paths", exc_info=True)
        await session.rollback()
