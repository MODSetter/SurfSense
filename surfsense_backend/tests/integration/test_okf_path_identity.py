"""A document's virtual path must resolve back to the same row: concepts are
identified by path (``doc_to_virtual_path`` <-> ``virtual_path_to_doc``). Covers
the hard cases - folder nesting and colliding titles.
"""

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.chat.runtime.path_resolver import (
    build_path_index,
    doc_to_virtual_path,
    virtual_path_to_doc,
)
from app.db import Document, DocumentType, Folder, User, Workspace

pytestmark = pytest.mark.integration


async def _add_document(
    session: AsyncSession,
    *,
    workspace: Workspace,
    user: User,
    title: str,
    folder_id: int | None,
    unique_hash: str,
) -> Document:
    doc = Document(
        title=title,
        document_type=DocumentType.NOTE,
        document_metadata={},
        content="body",
        content_hash=unique_hash,
        unique_identifier_hash=unique_hash,
        source_markdown="body",
        workspace_id=workspace.id,
        created_by_id=user.id,
        folder_id=folder_id,
    )
    session.add(doc)
    await session.flush()
    return doc


async def _roundtrip(
    session: AsyncSession, workspace: Workspace, doc: Document
) -> Document | None:
    index = await build_path_index(session, workspace.id)
    path = doc_to_virtual_path(
        doc_id=doc.id, title=doc.title, folder_id=doc.folder_id, index=index
    )
    return await virtual_path_to_doc(
        session, workspace_id=workspace.id, virtual_path=path
    )


@pytest_asyncio.fixture
async def research_folder(
    db_session: AsyncSession, db_workspace: Workspace
) -> Folder:
    folder = Folder(name="Research", position="0", workspace_id=db_workspace.id)
    db_session.add(folder)
    await db_session.flush()
    return folder


async def test_folder_nested_document_roundtrips(
    db_session, db_user, db_workspace, research_folder
):
    doc = await _add_document(
        db_session,
        workspace=db_workspace,
        user=db_user,
        title="My Note",
        folder_id=research_folder.id,
        unique_hash="hash-nested",
    )
    assert await _roundtrip(db_session, db_workspace, doc) is doc


async def test_colliding_titles_get_distinct_resolvable_paths(
    db_session, db_user, db_workspace
):
    first = await _add_document(
        db_session,
        workspace=db_workspace,
        user=db_user,
        title="Hello",
        folder_id=None,
        unique_hash="hash-a",
    )
    second = await _add_document(
        db_session,
        workspace=db_workspace,
        user=db_user,
        title="Hello",
        folder_id=None,
        unique_hash="hash-b",
    )

    index = await build_path_index(db_session, db_workspace.id)
    first_path = doc_to_virtual_path(
        doc_id=first.id, title=first.title, folder_id=None, index=index
    )
    second_path = doc_to_virtual_path(
        doc_id=second.id, title=second.title, folder_id=None, index=index
    )
    # Distinct identities: the collision is broken by a " (<id>).xml" suffix.
    assert first_path != second_path

    # Only the disambiguated path is stable; the bare title stays ambiguous while a twin exists.
    resolved = await virtual_path_to_doc(
        db_session, workspace_id=db_workspace.id, virtual_path=second_path
    )
    assert resolved is second
