"""Documents: the guards ingest leans on when the same file arrives twice."""

import pytest
from sqlalchemy import Engine, exc, func, insert, select

from modules.documents.models import Document, DocumentType
from modules.workspaces.models import Workspace


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


def test_dedup_key_is_unique_within_a_workspace(engine: Engine) -> None:
    """Re-ingesting a file must collide, while a second workspace may hold it."""
    with engine.begin() as connection:
        connection.execute(
            insert(Workspace).values([{"id": 1, "name": "1"}, {"id": 2, "name": "2"}])
        )
        for workspace_id in (1, 2):
            connection.execute(
                insert(Document).values(
                    workspace_id=workspace_id,
                    title="report",
                    document_type=DocumentType.FILE,
                    dedup_key="abc",
                )
            )

    with pytest.raises(exc.IntegrityError), engine.begin() as connection:
        connection.execute(
            insert(Document).values(
                workspace_id=1,
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
