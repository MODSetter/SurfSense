"""Document saves become store revisions (real git engine + real Redis lock)."""

from __future__ import annotations

import pytest

from app.config import config as app_config
from app.knowledge_store import KnowledgeStore
from app.services.document_revision_recorder import record_document_markdown

pytestmark = pytest.mark.integration


@pytest.fixture
def knowledge_root(tmp_path, monkeypatch):
    monkeypatch.setattr(app_config, "KNOWLEDGE_STORE_ENABLED", True)
    monkeypatch.setattr(app_config, "KNOWLEDGE_STORE_ROOT", str(tmp_path))
    return tmp_path


async def test_one_save_records_one_revision(knowledge_root, workspace_id):
    revision = await record_document_markdown(
        workspace_id=workspace_id,
        store_path="documents/notes/meeting.md",
        markdown="# Meeting",
        author_user_id="1",
    )

    store = KnowledgeStore.for_workspace(workspace_id)
    assert revision is not None
    assert await store.read_as_of(revision, "documents/notes/meeting.md") == b"# Meeting"
    rev = (await store.list_revisions())[0]
    assert "1" in rev.author
    assert "meeting.md" in rev.message


async def test_disabled_store_records_nothing(monkeypatch, tmp_path, workspace_id):
    monkeypatch.setattr(app_config, "KNOWLEDGE_STORE_ENABLED", False)
    monkeypatch.setattr(app_config, "KNOWLEDGE_STORE_ROOT", str(tmp_path))

    revision = await record_document_markdown(
        workspace_id=workspace_id,
        store_path="documents/notes/meeting.md",
        markdown="# Meeting",
        author_user_id="1",
    )

    assert revision is None
    assert not (tmp_path / str(workspace_id)).exists()
