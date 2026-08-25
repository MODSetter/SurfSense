"""Where the seeder puts a document, and what it records about it.

An authored-once recorded path is honored; an unmarked row is authored a fresh
``.md`` path, with same-title collisions numbered deterministically.
"""

from __future__ import annotations

import pytest

from app.config import config as app_config
from app.db import Document, DocumentType
from app.knowledge_store import KnowledgeStore
from app.knowledge_store.migrate import migrate_workspace
from app.knowledge_store.paths import PATH_MARKER
from app.utils.document_converters import generate_content_hash

pytestmark = pytest.mark.integration


@pytest.fixture
def knowledge_root(tmp_path, monkeypatch):
    monkeypatch.setattr(app_config, "KNOWLEDGE_STORE_ROOT", str(tmp_path))
    return tmp_path


async def _add_document(
    session, workspace, *, title, markdown, marker=None, folder_id=None
):
    document = Document(
        title=title,
        document_type=DocumentType.NOTE,
        document_metadata={PATH_MARKER: marker} if marker else {},
        content=markdown,
        content_hash=generate_content_hash(markdown, workspace.id),
        source_markdown=markdown,
        path=marker,
        folder_id=folder_id,
        workspace_id=workspace.id,
    )
    session.add(document)
    await session.flush()
    return document


async def _seeded_paths(report) -> set[str]:
    store = KnowledgeStore.for_workspace(report.workspace_id)
    return {t.path for t in await store.list_paths(report.seeded_revision)}


async def test_a_recorded_path_is_seeded_verbatim(
    knowledge_root, db_session, db_workspace
):
    """A path the agent already authored is not re-derived from the title."""
    await _add_document(
        db_session,
        db_workspace,
        title="Whatever",
        markdown="# Canary",
        marker="/documents/canary.md",
    )

    report = await migrate_workspace(db_session, db_workspace.id)

    assert report.ok, report
    assert await _seeded_paths(report) == {"documents/canary.md"}


async def test_seed_honors_the_column_over_a_disagreeing_marker(
    knowledge_root, db_session, db_workspace
):
    """Runtime pins a doc by its path column first, the legacy marker only as a
    fallback (``recorded_virtual_path``). A legacy row can carry a marker and a
    column that disagree; the seeder must resolve to the same column, or a re-seed
    and a live re-sync write the document at two different paths and fork it.
    """
    document = await _add_document(
        db_session,
        db_workspace,
        title="Whatever",
        markdown="# Body",
        marker="/documents/marker.md",
    )
    document.path = "/documents/column.md"
    await db_session.flush()

    report = await migrate_workspace(db_session, db_workspace.id)

    assert report.ok, report
    assert await _seeded_paths(report) == {"documents/column.md"}


async def test_an_unmarked_row_is_authored_as_markdown(
    knowledge_root, db_session, db_workspace
):
    """A title with no extension becomes a ``.md`` file, not the legacy ``.xml``."""
    await _add_document(
        db_session, db_workspace, title="Strategy", markdown="# Strategy"
    )

    report = await migrate_workspace(db_session, db_workspace.id)

    assert report.ok, report
    assert await _seeded_paths(report) == {"documents/Strategy.md"}


async def test_colliding_titles_get_a_numbered_sibling(
    knowledge_root, db_session, db_workspace
):
    """Two rows with one title resolve to distinct paths, oldest keeping the bare name."""
    await _add_document(db_session, db_workspace, title="Plan", markdown="# One")
    await _add_document(db_session, db_workspace, title="Plan", markdown="# Two")

    report = await migrate_workspace(db_session, db_workspace.id)

    assert report.ok, report
    assert await _seeded_paths(report) == {
        "documents/Plan.md",
        "documents/Plan (2).md",
    }


async def test_seeding_records_the_path_it_wrote(
    knowledge_root, db_session, db_workspace
):
    """The recorded path is what a later retitle drops from the tree."""
    document = await _add_document(
        db_session, db_workspace, title="Strategy", markdown="# Strategy"
    )
    assert document.path is None

    await migrate_workspace(db_session, db_workspace.id)

    await db_session.refresh(document)
    assert document.path == "/documents/Strategy.md"


async def test_a_dry_run_records_nothing(knowledge_root, db_session, db_workspace):
    document = await _add_document(
        db_session, db_workspace, title="Strategy", markdown="# Strategy"
    )

    await migrate_workspace(db_session, db_workspace.id, dry_run=True)

    await db_session.refresh(document)
    assert document.path is None


async def test_a_re_seed_is_stable(knowledge_root, db_session, db_workspace):
    """The path the first seed records is honored by the second, so no drift."""
    await _add_document(
        db_session, db_workspace, title="Strategy", markdown="# Strategy"
    )

    first = await migrate_workspace(db_session, db_workspace.id)
    second = await migrate_workspace(db_session, db_workspace.id)

    assert second.ok, second
    assert second.seeded_revision is None
    assert await _seeded_paths(first) == {"documents/Strategy.md"}


async def test_an_empty_folder_is_seeded_as_a_keep(
    knowledge_root, db_session, db_workspace
):
    """Git holds no empty directory, so the seed materializes one as ``.keep``."""
    from app.services.folder_service import ensure_folder_hierarchy

    await ensure_folder_hierarchy(
        db_session,
        workspace_id=db_workspace.id,
        created_by_id=None,
        folder_parts=["Archive"],
    )
    await _add_document(
        db_session, db_workspace, title="Strategy", markdown="# Strategy"
    )

    report = await migrate_workspace(db_session, db_workspace.id)

    assert report.ok, report
    assert "documents/Archive/.keep" in await _seeded_paths(report)


async def test_only_the_leaf_of_an_empty_chain_is_kept(
    knowledge_root, db_session, db_workspace
):
    """A parent rides along on its child's ``.keep``, so only the leaf carries one."""
    from app.services.folder_service import ensure_folder_hierarchy

    await ensure_folder_hierarchy(
        db_session,
        workspace_id=db_workspace.id,
        created_by_id=None,
        folder_parts=["Parent", "Child"],
    )
    await _add_document(
        db_session, db_workspace, title="Strategy", markdown="# Strategy"
    )

    report = await migrate_workspace(db_session, db_workspace.id)

    paths = await _seeded_paths(report)
    assert "documents/Parent/Child/.keep" in paths
    assert "documents/Parent/.keep" not in paths


async def test_a_folder_holding_a_document_gets_no_keep(
    knowledge_root, db_session, db_workspace
):
    """A folder a document already lives in is kept by that document, not a marker."""
    from app.services.folder_service import ensure_folder_hierarchy

    folder_id = await ensure_folder_hierarchy(
        db_session,
        workspace_id=db_workspace.id,
        created_by_id=None,
        folder_parts=["Notes"],
    )
    await _add_document(
        db_session,
        db_workspace,
        title="Strategy",
        markdown="# Strategy",
        folder_id=folder_id,
    )

    report = await migrate_workspace(db_session, db_workspace.id)

    paths = await _seeded_paths(report)
    assert "documents/Notes/Strategy.md" in paths
    assert "documents/Notes/.keep" not in paths
