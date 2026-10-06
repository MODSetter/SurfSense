"""Resolving a source scope: what it covers, what it counts, and what it refuses."""

from collections.abc import Iterator

import pytest
from fastapi import HTTPException
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from modules.documents.models import Document, DocumentStatus, DocumentType
from modules.folders.ensure_path import ensure_folder_path
from modules.folders.models import Folder, FolderState
from modules.source_roots.managed_root import ensure_managed_root
from modules.source_scope.resolve import pruned, resolve_scope
from modules.source_scope.schemas import SourceScope
from modules.workspaces.models import Workspace
from shared.db import create_session_factory

pytestmark = pytest.mark.integration


@pytest.fixture
def session(engine: Engine) -> Iterator[Session]:
    """A session on the migrated database."""
    with create_session_factory(engine)() as session:
        yield session


def _workspace(session: Session) -> Workspace:
    workspace = Workspace(name="Research")
    session.add(workspace)
    session.flush()
    return workspace


def _document(
    session: Session,
    workspace: Workspace,
    folder: Folder | None,
    *,
    kind: DocumentType = DocumentType.NOTE,
    status: DocumentStatus = DocumentStatus.READY,
) -> int:
    document = Document(
        workspace_id=workspace.id,
        title="doc",
        document_type=kind,
        status=status,
        content="text",
        folder_id=folder.id if folder else None,
    )
    session.add(document)
    session.flush()
    return document.id


def test_all_takes_every_file_and_note_but_no_unfiled_artifact(
    session: Session,
) -> None:
    """All takes every file and note but no unfiled artifact."""
    workspace = _workspace(session)
    library = ensure_managed_root(session, workspace.id)
    note = _document(session, workspace, library)
    unfiled_note = _document(session, workspace, None)
    _document(session, workspace, None, kind=DocumentType.ARTIFACT)
    filed_artifact = _document(session, workspace, library, kind=DocumentType.ARTIFACT)

    resolved = resolve_scope(session, workspace.id, SourceScope(all=True))

    assert resolved.ids == [note, unfiled_note, filed_artifact]


def test_sources_still_indexing_are_counted_not_refused(session: Session) -> None:
    """Sources still indexing are counted not refused."""
    workspace = _workspace(session)
    library = ensure_managed_root(session, workspace.id)
    ready = _document(session, workspace, library)
    _document(session, workspace, library, status=DocumentStatus.PENDING)
    _document(session, workspace, library, status=DocumentStatus.PROCESSING)
    _document(session, workspace, library, status=DocumentStatus.FAILED)

    resolved = resolve_scope(session, workspace.id, SourceScope(all=True))

    assert resolved.ids == [ready]
    assert resolved.counts.model_dump() == {
        "ready": 1,
        "indexing": 2,
        "failed": 1,
        "removed": 0,
    }


def test_an_id_from_another_workspace_is_refused(session: Session) -> None:
    """An id from another workspace is refused."""
    mine, other = _workspace(session), _workspace(session)
    foreign = _document(session, other, ensure_managed_root(session, other.id))

    with pytest.raises(HTTPException) as refused:
        resolve_scope(session, mine.id, SourceScope(document_ids=[foreign]))

    assert refused.value.status_code == 422


def test_a_deleted_source_is_dropped_counted_and_pruned(session: Session) -> None:
    """A deleted source is dropped counted and pruned."""
    workspace = _workspace(session)
    library = ensure_managed_root(session, workspace.id)
    kept = _document(session, workspace, library)
    gone = _document(session, workspace, library)
    session.delete(session.get(Document, gone))
    session.flush()
    scope = SourceScope(document_ids=[kept, gone])

    resolved = resolve_scope(session, workspace.id, scope)

    assert resolved.ids == [kept]
    assert resolved.counts.removed == 1
    assert pruned(scope, resolved).document_ids == [kept]


def test_an_artifact_is_left_out_of_its_own_sources(session: Session) -> None:
    """An artifact is left out of its own sources."""
    workspace = _workspace(session)
    library = ensure_managed_root(session, workspace.id)
    note = _document(session, workspace, library)
    itself = _document(session, workspace, library, kind=DocumentType.ARTIFACT)

    resolved = resolve_scope(
        session, workspace.id, SourceScope(all=True), exclude_document_ids=[itself]
    )

    assert resolved.ids == [note]


def test_a_ticked_folder_takes_files_added_to_it_later(session: Session) -> None:
    """A ticked folder takes files added to it later."""
    workspace = _workspace(session)
    library = ensure_managed_root(session, workspace.id)
    research = ensure_folder_path(session, library, ["Research"])
    _document(session, workspace, library)
    scope = SourceScope(folder_ids=[research.id])
    assert resolve_scope(session, workspace.id, scope).ids == []

    later = _document(session, workspace, ensure_folder_path(session, research, ["AI"]))

    assert resolve_scope(session, workspace.id, scope).ids == [later]


def test_an_excluded_subfolder_is_out_and_a_file_ticked_inside_it_is_in(
    session: Session,
) -> None:
    """An excluded subfolder is out and a file ticked inside it is in."""
    workspace = _workspace(session)
    library = ensure_managed_root(session, workspace.id)
    research = ensure_folder_path(session, library, ["Research"])
    drafts = ensure_folder_path(session, research, ["Drafts"])
    paper = _document(session, workspace, research)
    _draft = _document(session, workspace, drafts)
    chosen = _document(session, workspace, drafts)

    resolved = resolve_scope(
        session,
        workspace.id,
        SourceScope(
            folder_ids=[research.id],
            excluded_folder_ids=[drafts.id],
            document_ids=[chosen],
        ),
    )

    assert resolved.ids == [paper, chosen]


def test_a_folder_being_deleted_leaves_every_scope_at_once(session: Session) -> None:
    """A folder being deleted leaves every scope at once."""
    workspace = _workspace(session)
    library = ensure_managed_root(session, workspace.id)
    research = ensure_folder_path(session, library, ["Research", "AI"])
    kept = _document(session, workspace, library)
    _document(session, workspace, research)
    parent = session.get(Folder, research.parent_id)
    assert parent is not None
    parent.state = FolderState.DELETING
    session.flush()

    resolved = resolve_scope(session, workspace.id, SourceScope(all=True))

    assert resolved.ids == [kept]
