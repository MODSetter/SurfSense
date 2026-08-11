"""Two git paths, identical bytes must converge into two rows.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.config import config as app_config
from app.db import Document
from app.knowledge_store import KnowledgeStore
from app.knowledge_store.identities import user_identity
from app.knowledge_store.index.converge import index_changes
from app.utils.document_converters import generate_content_hash

pytestmark = pytest.mark.integration

DUPLICATE = "# Shared\n\nidentical bytes at two paths\n"


@pytest.fixture
def knowledge_root(tmp_path, monkeypatch):
    monkeypatch.setattr(app_config, "KNOWLEDGE_STORE_ENABLED", True)
    monkeypatch.setattr(app_config, "KNOWLEDGE_STORE_ROOT", str(tmp_path))
    return tmp_path


@pytest.fixture
def store(knowledge_root, db_workspace):
    return KnowledgeStore.for_workspace(db_workspace.id)


async def _commit_two_identical_files(store):
    async with store.transaction(message="test", author=user_identity("1")) as tx:
        tx.write("documents/a.xml", DUPLICATE.encode())
        tx.write("documents/b.xml", DUPLICATE.encode())
    return tx.revision


async def test_identical_content_at_two_paths_converges_to_two_rows(
    store, db_session, db_workspace, patched_embed_texts, patched_chunk_text
):
    await _commit_two_identical_files(store)

    await index_changes(db_session, db_workspace.id)

    rows = (
        (
            await db_session.execute(
                select(Document).where(Document.workspace_id == db_workspace.id)
            )
        )
        .scalars()
        .all()
    )
    assert {row.path for row in rows} == {"/documents/a.xml", "/documents/b.xml"}
    assert {row.content_hash for row in rows} == {
        generate_content_hash(DUPLICATE, db_workspace.id)
    }
