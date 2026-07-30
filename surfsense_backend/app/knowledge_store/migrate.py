"""Phase 5 seeder: export a workspace's documents into its store as one seed revision.

Parity is **byte identity** (content addresses compared, no file reads), never a
reindex — the seed copies bytes out of Postgres, so the existing chunk index is
already correct by construction. Runs before the flip, so unlike the recorder it
never guards on ``KNOWLEDGE_STORE_ENABLED``.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.chat.runtime.path_resolver import (
    build_path_index,
    doc_to_virtual_path,
    to_store_path,
)
from app.knowledge_store.engines.base import TrackedPath
from app.knowledge_store.identities import MIGRATION_IDENTITY
from app.knowledge_store.store import KnowledgeStore


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
    """Seed one workspace's current documents, mapped by the live path rules.

    Uses the same resolver as every write path (`doc_to_virtual_path`), so a
    connector re-sync or agent write after migration lands on the exact same
    path and updates instead of duplicating.

    Never raises: a failure while fetching or mapping documents is returned
    as ``MigrationReport.error``, like every seed failure.
    """
    from app.db import Document

    try:
        index = await build_path_index(session, workspace_id)
        rows = await session.execute(
            select(
                Document.id,
                Document.title,
                Document.folder_id,
                Document.source_markdown,
                Document.content,
            ).where(Document.workspace_id == workspace_id)
        )
        files: dict[str, str] = {}
        for doc_id, title, folder_id, source_markdown, content in rows:
            # Rows predating the nullable source_markdown column hold text in
            # content only; "Pending..." is the pre-index placeholder, never
            # content.
            markdown = source_markdown or content
            if not markdown or markdown == "Pending...":
                continue
            virtual_path = doc_to_virtual_path(
                doc_id=doc_id, title=title, folder_id=folder_id, index=index
            )
            files[to_store_path(virtual_path)] = markdown
    except Exception as exc:
        return _failure_report(workspace_id, dry_run, 0, exc)
    return await seed_workspace(workspace_id, files, dry_run=dry_run)
