import hashlib
import json
from collections.abc import Iterable
from dataclasses import dataclass, field

from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from modules.documents.models import DocumentStatus
from modules.source_scope.schemas import ScopeCounts, SourceScope

_INDEXING = {DocumentStatus.PENDING.value, DocumentStatus.PROCESSING.value}
_FAILED = {DocumentStatus.FAILED.value, DocumentStatus.CANCELLED.value}


@dataclass(frozen=True)
class ResolvedScope:
    """The ready source ids a scope means now, and how the rest of it stands."""

    ids: list[int]
    counts: ScopeCounts
    # What `removed` counted, so the stored scope can be pruned.
    removed_folder_ids: frozenset[int] = field(default_factory=frozenset)
    removed_document_ids: frozenset[int] = field(default_factory=frozenset)

    @property
    def ids_sha256(self) -> str:
        """Tells a replay whether it runs on the same sources, without the list."""
        return hashlib.sha256(json.dumps(sorted(self.ids)).encode()).hexdigest()

    def record(self, scope: SourceScope) -> dict:
        """What a turn or an artifact keeps of the scope it used."""
        return {
            "source_scope": pruned(scope, self).model_dump(),
            "resolved": {"count": len(self.ids), "ids_sha256": self.ids_sha256},
        }


def resolve_scope(
    session: Session,
    workspace_id: int,
    scope: SourceScope,
    *,
    exclude_document_ids: Iterable[int] = (),
) -> ResolvedScope:
    """Expand a scope to the workspace's sources it covers, ready ones first-class.

    `all` takes every FILE and NOTE and every filed artifact, never an unfiled
    one. Folders being deleted take their subtrees out at once. An id from
    another workspace is a 422; one that no longer exists is counted as removed.
    """
    removed_folders = _missing(
        session,
        "folders",
        workspace_id,
        {*scope.folder_ids, *scope.excluded_folder_ids},
    )
    removed_documents = _missing(
        session,
        "documents",
        workspace_id,
        {*scope.document_ids, *scope.excluded_document_ids},
    )
    rows = session.execute(
        text(
            "WITH RECURSIVE "
            "included(id) AS ("
            "  SELECT value FROM json_each(:folder_ids)"
            "  UNION SELECT f.id FROM folders f JOIN included i ON f.parent_id = i.id"
            "), excluded(id) AS ("
            "  SELECT value FROM json_each(:excluded_folder_ids)"
            "  UNION SELECT f.id FROM folders f JOIN excluded e ON f.parent_id = e.id"
            "), gone(id) AS ("
            "  SELECT id FROM folders WHERE workspace_id = :ws"
            "  AND state IN ('trashed', 'deleting')"
            "  UNION SELECT f.id FROM folders f JOIN gone g ON f.parent_id = g.id"
            ") "
            "SELECT d.id, d.status FROM documents d WHERE d.workspace_id = :ws "
            "AND (("
            "  ((:all AND (d.document_type IN ('FILE', 'NOTE') "
            "              OR d.folder_id IS NOT NULL))"
            "   OR d.folder_id IN (SELECT id FROM included))"
            "  AND (d.folder_id IS NULL OR d.folder_id NOT IN (SELECT id FROM excluded))"
            ") OR d.id IN (SELECT value FROM json_each(:document_ids))) "
            "AND d.id NOT IN (SELECT value FROM json_each(:excluded_document_ids)) "
            "AND d.id NOT IN (SELECT value FROM json_each(:exclude_ids)) "
            "AND (d.folder_id IS NULL OR d.folder_id NOT IN (SELECT id FROM gone)) "
            "ORDER BY d.id"
        ),
        {
            "ws": workspace_id,
            "all": int(scope.all),
            "folder_ids": json.dumps(scope.folder_ids),
            "excluded_folder_ids": json.dumps(scope.excluded_folder_ids),
            "document_ids": json.dumps(scope.document_ids),
            "excluded_document_ids": json.dumps(scope.excluded_document_ids),
            "exclude_ids": json.dumps(list(exclude_document_ids)),
        },
    ).all()

    ready = [row.id for row in rows if row.status == DocumentStatus.READY.value]
    return ResolvedScope(
        ids=ready,
        counts=ScopeCounts(
            ready=len(ready),
            indexing=sum(row.status in _INDEXING for row in rows),
            failed=sum(row.status in _FAILED for row in rows),
            removed=len(removed_folders) + len(removed_documents),
        ),
        removed_folder_ids=frozenset(removed_folders),
        removed_document_ids=frozenset(removed_documents),
    )


def pruned(scope: SourceScope, resolved: ResolvedScope) -> SourceScope:
    """The scope without the ids that no longer exist."""
    folders, documents = resolved.removed_folder_ids, resolved.removed_document_ids
    return SourceScope(
        all=scope.all,
        folder_ids=[i for i in scope.folder_ids if i not in folders],
        excluded_folder_ids=[i for i in scope.excluded_folder_ids if i not in folders],
        document_ids=[i for i in scope.document_ids if i not in documents],
        excluded_document_ids=[
            i for i in scope.excluded_document_ids if i not in documents
        ],
    )


def _missing(
    session: Session, table: str, workspace_id: int, ids: set[int]
) -> set[int]:
    """The ids that no longer exist; a 422 for any that belong to another workspace."""
    if not ids:
        return set()
    found = dict(
        session.execute(
            text(
                f"SELECT id, workspace_id FROM {table} "
                "WHERE id IN (SELECT value FROM json_each(:ids))"
            ),
            {"ids": json.dumps(sorted(ids))},
        ).all()
    )
    if any(owner != workspace_id for owner in found.values()):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "a chosen source is not in this workspace",
        )
    return ids - found.keys()
