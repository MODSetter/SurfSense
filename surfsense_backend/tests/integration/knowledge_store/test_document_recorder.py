"""Document saves become store revisions (real git engine + real Redis lock)."""

from __future__ import annotations

import pytest

from app.config import config as app_config
from app.knowledge_store import KnowledgeStore
from app.services.document_revision_recorder import record_markdown_files

pytestmark = pytest.mark.integration


@pytest.fixture
def knowledge_root(tmp_path, monkeypatch):
    monkeypatch.setattr(app_config, "KNOWLEDGE_STORE_ENABLED", True)
    monkeypatch.setattr(app_config, "KNOWLEDGE_STORE_ROOT", str(tmp_path))
    return tmp_path


async def test_one_save_records_one_revision(knowledge_root, workspace_id):
    revision = await record_markdown_files(
        workspace_id=workspace_id,
        files={"documents/notes/meeting.md": "# Meeting"},
        message="docs: save meeting.md",
        author_user_id="1",
    )

    store = KnowledgeStore.for_workspace(workspace_id)
    assert revision is not None
    assert (
        await store.read_as_of(revision, "documents/notes/meeting.md") == b"# Meeting"
    )
    rev = (await store.list_revisions())[0]
    assert "1" in rev.author
    assert "meeting.md" in rev.message


async def test_a_sync_batch_records_one_revision(knowledge_root, workspace_id):
    revision = await record_markdown_files(
        workspace_id=workspace_id,
        files={
            "documents/notion/roadmap.md": "# Roadmap",
            "documents/notion/okrs.md": "# OKRs",
        },
        message="sync: index 2 document(s)",
        author_user_id="1",
    )

    store = KnowledgeStore.for_workspace(workspace_id)
    revisions = await store.list_revisions()
    assert [r.id for r in revisions] == [revision]
    assert await store.read_as_of(revision, "documents/notion/okrs.md") == b"# OKRs"


async def test_unchanged_content_records_nothing(knowledge_root, workspace_id):
    files = {"documents/notion/roadmap.md": "# Roadmap"}
    first = await record_markdown_files(
        workspace_id=workspace_id, files=files, message="sync", author_user_id="1"
    )
    second = await record_markdown_files(
        workspace_id=workspace_id, files=files, message="sync", author_user_id="1"
    )

    assert first is not None
    assert second is None
    assert len(await KnowledgeStore.for_workspace(workspace_id).list_revisions()) == 1


async def test_empty_batch_records_nothing(knowledge_root, workspace_id):
    revision = await record_markdown_files(
        workspace_id=workspace_id, files={}, message="sync", author_user_id="1"
    )

    assert revision is None
    assert not (knowledge_root / str(workspace_id)).exists()


async def test_a_retitled_document_leaves_no_file_at_its_old_path(
    knowledge_root, workspace_id
):
    """One document is one file. Without the removal a retitle forks it into two."""
    await record_markdown_files(
        workspace_id=workspace_id,
        files={"documents/Old title.xml": "# Body"},
        message="docs: save Old title.xml",
        author_user_id="1",
    )

    revision = await record_markdown_files(
        workspace_id=workspace_id,
        files={"documents/New title.xml": "# Body"},
        message="docs: save New title.xml",
        author_user_id="1",
        removes=["documents/Old title.xml"],
    )

    store = KnowledgeStore.for_workspace(workspace_id)
    paths = {entry.path for entry in await store.list_paths(revision)}
    assert paths == {"documents/New title.xml"}


async def test_disabled_store_records_nothing(monkeypatch, tmp_path, workspace_id):
    monkeypatch.setattr(app_config, "KNOWLEDGE_STORE_ENABLED", False)
    monkeypatch.setattr(app_config, "KNOWLEDGE_STORE_ROOT", str(tmp_path))

    revision = await record_markdown_files(
        workspace_id=workspace_id,
        files={"documents/notes/meeting.md": "# Meeting"},
        message="docs: save meeting.md",
        author_user_id="1",
    )

    assert revision is None
    assert not (tmp_path / str(workspace_id)).exists()
