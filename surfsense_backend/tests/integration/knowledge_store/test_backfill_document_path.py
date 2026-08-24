"""The 189 backfill copies a legacy ``virtual_path`` marker into the column.

The re-home keys ownership and resolution on ``documents.path``. A row written
before that column existed carries the path only on its metadata marker, so
until the column is filled it is invisible to the new lookups. This proves the
backfill closes that window against the real resolver, not a stand-in.
"""

import pytest
from sqlalchemy import text

from app.db import Document, DocumentType, User, Workspace
from app.knowledge_store.paths import virtual_path_to_doc
from app.utils.document_converters import generate_unique_identifier_hash

pytestmark = pytest.mark.integration

# Verbatim from alembic/versions/189_backfill_document_path.py: the test guards
# the statement the migration ships, so a drift in either side fails here.
_BACKFILL = text(
    "UPDATE documents SET path = document_metadata ->> 'virtual_path' "
    "WHERE path IS NULL "
    "AND document_metadata ->> 'virtual_path' LIKE '/documents/%'"
)


async def _add(
    session,
    *,
    workspace: Workspace,
    user: User,
    marker: str | None,
    path: str | None,
    title: str = "Plan",
    unique_path: str | None = None,
) -> Document:
    tag = f"{title}-{marker}-{path}"
    doc = Document(
        title=title,
        document_type=DocumentType.NOTE,
        document_metadata={"virtual_path": marker} if marker else {},
        content=f"body-{tag}",
        content_hash=f"content-{tag}",
        unique_identifier_hash=generate_unique_identifier_hash(
            DocumentType.NOTE, unique_path or f"/documents/{tag}.md", workspace.id
        ),
        source_markdown=f"body-{tag}",
        path=path,
        workspace_id=workspace.id,
        created_by_id=user.id,
        folder_id=None,
    )
    session.add(doc)
    await session.flush()
    return doc


async def test_backfill_makes_a_legacy_moved_note_resolve_by_column(
    db_session, db_user, db_workspace
):
    """A note moved before the column existed: only the marker tracks the new
    path. Its unique hash still hashes the old path and its title no longer
    matches the new name, so nothing but the marker/column can find it."""
    doc = await _add(
        db_session,
        workspace=db_workspace,
        user=db_user,
        title="old-name",
        marker="/documents/notes/new-name.md",
        path=None,
        unique_path="/documents/notes/old-name.md",
    )

    # The problem: at its current path the moved note is unresolvable.
    assert (
        await virtual_path_to_doc(
            db_session,
            workspace_id=db_workspace.id,
            virtual_path="/documents/notes/new-name.md",
        )
        is None
    )

    await db_session.execute(_BACKFILL)
    await db_session.refresh(doc)

    # The fix: the column now carries the path, so resolution lands on the row.
    assert doc.path == "/documents/notes/new-name.md"
    resolved = await virtual_path_to_doc(
        db_session,
        workspace_id=db_workspace.id,
        virtual_path="/documents/notes/new-name.md",
    )
    assert resolved is doc


async def test_backfill_only_fills_null_columns_from_documents_markers(
    db_session, db_user, db_workspace
):
    """Fill an empty column from a ``/documents`` marker and nothing else: an
    already-set column is authored data, a foreign marker is another store's."""
    legacy = await _add(
        db_session,
        workspace=db_workspace,
        user=db_user,
        title="legacy",
        marker="/documents/a.md",
        path=None,
    )
    already = await _add(
        db_session,
        workspace=db_workspace,
        user=db_user,
        title="already",
        marker="/documents/moved-from.md",
        path="/documents/kept.md",
    )
    foreign = await _add(
        db_session,
        workspace=db_workspace,
        user=db_user,
        title="foreign",
        marker="slack://C1/123",
        path=None,
    )
    unmarked = await _add(
        db_session,
        workspace=db_workspace,
        user=db_user,
        title="unmarked",
        marker=None,
        path=None,
    )

    await db_session.execute(_BACKFILL)
    for doc in (legacy, already, foreign, unmarked):
        await db_session.refresh(doc)

    assert legacy.path == "/documents/a.md"
    assert already.path == "/documents/kept.md"
    assert foreign.path is None
    assert unmarked.path is None
