"""A real export must be a conformant OKF bundle end-to-end (real DB).

Unit tests cover the pure serializer; this drives the whole export pipeline
(folder-path map, batching, ZIP writing) and asserts the emitted artifact -
concept files plus reserved ``index.md``/``log.md`` - passes ``validate_bundle``.
"""

import os
import zipfile

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import Document, DocumentType, Folder, User, Workspace
from app.services.export_service import build_export_zip
from app.services.okf import validate_bundle

pytestmark = pytest.mark.integration


async def _add_doc(
    session: AsyncSession,
    *,
    workspace: Workspace,
    user: User,
    title: str,
    folder_id: int | None,
    uid: str,
) -> Document:
    doc = Document(
        title=title,
        document_type=DocumentType.NOTE,
        document_metadata={"tags": ["team"]},
        content="body text",
        content_hash=uid,
        unique_identifier_hash=uid,
        source_markdown=f"# {title}\n\nBody.",
        workspace_id=workspace.id,
        created_by_id=user.id,
        folder_id=folder_id,
    )
    session.add(doc)
    await session.flush()
    return doc


async def test_export_bundle_is_okf_conformant(
    db_session: AsyncSession, db_user: User, db_workspace: Workspace
):
    folder = Folder(name="Research", position="0", workspace_id=db_workspace.id)
    db_session.add(folder)
    await db_session.flush()

    await _add_doc(
        db_session, workspace=db_workspace, user=db_user,
        title="Root Note", folder_id=None, uid="okf-export-root",
    )
    await _add_doc(
        db_session, workspace=db_workspace, user=db_user,
        title="Nested Note", folder_id=folder.id, uid="okf-export-nested",
    )

    result = await build_export_zip(db_session, db_workspace.id)
    try:
        with zipfile.ZipFile(result.zip_path) as zf:
            files = {name: zf.read(name).decode("utf-8") for name in zf.namelist()}
    finally:
        os.unlink(result.zip_path)

    # Directory structure: concepts nested by folder, plus reserved files.
    assert "Root Note.md" in files
    assert "Research/Nested Note.md" in files
    assert files["index.md"].startswith('---\nokf_version: "0.1"\n---')
    assert any(name.endswith("log.md") for name in files)

    # The whole bundle conforms; reserved index/log files are exempt.
    assert validate_bundle(files) == {}
