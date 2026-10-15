"""Documents: the guards ingest leans on when the same file arrives twice."""

import pytest
from sqlalchemy import Engine, exc, func, insert, select

from modules.documents.models import Document, DocumentType
from modules.folders.ensure_path import ensure_folder_path
from modules.source_roots.managed_root import ensure_managed_root
from modules.workspaces.models import Workspace
from shared.db import create_session_factory

pytestmark = pytest.mark.integration


def test_documents_require_a_workspace(engine: Engine) -> None:
    """Foreign keys are off per connection in SQLite; the engine must enable them."""
    with pytest.raises(exc.IntegrityError), engine.begin() as connection:
        connection.execute(
            insert(Document).values(workspace_id=404, title="x", document_type="FILE")
        )


def test_status_rejects_a_value_outside_the_enum(engine: Engine) -> None:
    """SQLite has no enum type, so the CHECK constraint is the only guard."""
    with engine.begin() as connection:
        connection.execute(insert(Workspace).values(id=1, name="one"))

    with pytest.raises(exc.IntegrityError), engine.begin() as connection:
        connection.execute(
            insert(Document).values(
                workspace_id=1, title="x", document_type="FILE", status="banana"
            )
        )


def test_status_accepts_cancelled(engine: Engine) -> None:
    """A stopped job is a first-class status, not a failed row with a special message."""
    with engine.begin() as connection:
        connection.execute(insert(Workspace).values(id=1, name="one"))
        connection.execute(
            insert(Document).values(
                workspace_id=1,
                title="x",
                document_type="FILE",
                status="cancelled",
            )
        )
        kept = connection.execute(select(func.count()).select_from(Document)).scalar()
        assert kept == 1


def test_dedup_key_is_unique_within_a_folder(engine: Engine) -> None:
    """Re-adding a file to its folder must collide; another folder may hold it."""
    with create_session_factory(engine)() as session:
        session.add_all([Workspace(id=1, name="1"), Workspace(id=2, name="2")])
        session.flush()
        library = ensure_managed_root(session, 1)
        other_folder = ensure_folder_path(session, library, ["Other"])
        other_workspace = ensure_managed_root(session, 2)
        folders = (library.id, other_folder.id, other_workspace.id)
        session.commit()
    with engine.begin() as connection:
        for workspace_id, folder_id in zip((1, 1, 2), folders, strict=True):
            connection.execute(
                insert(Document).values(
                    workspace_id=workspace_id,
                    folder_id=folder_id,
                    title="report",
                    document_type=DocumentType.FILE,
                    dedup_key="abc",
                )
            )

    with pytest.raises(exc.IntegrityError), engine.begin() as connection:
        connection.execute(
            insert(Document).values(
                workspace_id=1,
                folder_id=folders[0],
                title="again",
                document_type=DocumentType.FILE,
                dedup_key="abc",
            )
        )


def test_documents_without_a_dedup_key_do_not_collide(engine: Engine) -> None:
    """Notes carry no dedup key, so the partial unique index must skip them."""
    with engine.begin() as connection:
        connection.execute(insert(Workspace).values(id=1, name="one"))
        for title in ("first", "second"):
            connection.execute(
                insert(Document).values(
                    workspace_id=1, title=title, document_type=DocumentType.NOTE
                )
            )

        kept = connection.execute(select(func.count()).select_from(Document)).scalar()
        assert kept == 2
