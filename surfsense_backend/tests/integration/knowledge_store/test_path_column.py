"""Resolution reads ``documents.path`` first, the marker as fallback."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import Document, DocumentType, User, Workspace
from app.knowledge_store.paths import PATH_MARKER, virtual_path_to_doc

pytestmark = pytest.mark.integration


async def _add(
    session: AsyncSession,
    *,
    workspace: Workspace,
    user: User,
    unique_hash: str,
    path: str | None,
    marker: str | None,
) -> Document:
    doc = Document(
        title="Plan",
        document_type=DocumentType.NOTE,
        document_metadata={PATH_MARKER: marker} if marker else {},
        content="body",
        content_hash=unique_hash,
        unique_identifier_hash=unique_hash,
        source_markdown="body",
        path=path,
        workspace_id=workspace.id,
        created_by_id=user.id,
        folder_id=None,
    )
    session.add(doc)
    await session.flush()
    return doc


async def test_the_healed_column_resolves_without_a_marker(
    db_session, db_user, db_workspace
):
    doc = await _add(
        db_session,
        workspace=db_workspace,
        user=db_user,
        unique_hash="hash-column",
        path="/documents/notes/plan.md",
        marker=None,
    )
    resolved = await virtual_path_to_doc(
        db_session, workspace_id=db_workspace.id, virtual_path="/documents/notes/plan.md"
    )
    assert resolved is doc


async def test_an_unhealed_row_still_resolves_by_its_marker(
    db_session, db_user, db_workspace
):
    doc = await _add(
        db_session,
        workspace=db_workspace,
        user=db_user,
        unique_hash="hash-marker",
        path=None,
        marker="/documents/notes/legacy.md",
    )
    resolved = await virtual_path_to_doc(
        db_session,
        workspace_id=db_workspace.id,
        virtual_path="/documents/notes/legacy.md",
    )
    assert resolved is doc
