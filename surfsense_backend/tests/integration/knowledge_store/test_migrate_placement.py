"""Where the seeder puts a document, and what it records about it.

Placement is shared with every other writer, so the seeder must not re-invent it.
Deriving a path from the title is only ever a guess: the agent's ``write_file``
names its own files, so the store already holds names no title would produce.
"""

from __future__ import annotations

import pytest

from app.agents.chat.runtime.path_resolver import PATH_MARKER
from app.config import config as app_config
from app.db import Document, DocumentType
from app.knowledge_store import KnowledgeStore
from app.knowledge_store.migrate import migrate_workspace
from app.utils.document_converters import generate_content_hash

pytestmark = pytest.mark.integration


@pytest.fixture
def knowledge_root(tmp_path, monkeypatch):
    monkeypatch.setattr(app_config, "KNOWLEDGE_STORE_ROOT", str(tmp_path))
    return tmp_path


async def _add_document(session, workspace, *, title, markdown, marker=None):
    document = Document(
        title=title,
        document_type=DocumentType.NOTE,
        document_metadata={PATH_MARKER: marker} if marker else {},
        content=markdown,
        content_hash=generate_content_hash(markdown, workspace.id),
        source_markdown=markdown,
        workspace_id=workspace.id,
    )
    session.add(document)
    await session.flush()
    return document


async def test_an_agent_authored_name_is_seeded_where_it_already_lives(
    knowledge_root, db_session, db_workspace
):
    """The store holds ``canary.md``; the title would derive ``canary.md.xml``.
    Deriving would report false drift, and a real run would write the derived
    name and delete the agent's file as an orphan."""
    await _add_document(
        db_session,
        db_workspace,
        title="canary.md",
        markdown="# Canary",
        marker="/documents/canary.md",
    )

    report = await migrate_workspace(db_session, db_workspace.id)

    assert report.ok, report
    store = KnowledgeStore.for_workspace(db_workspace.id)
    paths = {t.path for t in await store.list_paths(report.seeded_revision)}
    assert paths == {"documents/canary.md"}


async def test_a_row_with_no_marker_keeps_the_derived_name(
    knowledge_root, db_session, db_workspace
):
    """Every migrated row starts unmarked, so derivation stays the fallback and
    an existing store is not renamed out from under itself."""
    await _add_document(
        db_session, db_workspace, title="strategy.md", markdown="# Strategy"
    )

    report = await migrate_workspace(db_session, db_workspace.id)

    assert report.ok, report
    store = KnowledgeStore.for_workspace(db_workspace.id)
    paths = {t.path for t in await store.list_paths(report.seeded_revision)}
    assert paths == {"documents/strategy.md.xml"}


async def test_seeding_records_the_path_it_wrote(
    knowledge_root, db_session, db_workspace
):
    """Without the marker a retitle cannot tell which file to drop from the
    tree, so it forks the document into two."""
    document = await _add_document(
        db_session, db_workspace, title="strategy.md", markdown="# Strategy"
    )
    assert PATH_MARKER not in (document.document_metadata or {})

    await migrate_workspace(db_session, db_workspace.id)

    await db_session.refresh(document)
    assert document.document_metadata[PATH_MARKER] == "/documents/strategy.md.xml"


async def test_a_dry_run_records_nothing(knowledge_root, db_session, db_workspace):
    document = await _add_document(
        db_session, db_workspace, title="strategy.md", markdown="# Strategy"
    )

    await migrate_workspace(db_session, db_workspace.id, dry_run=True)

    await db_session.refresh(document)
    assert PATH_MARKER not in (document.document_metadata or {})


async def test_the_marker_makes_a_re_seed_stable(
    knowledge_root, db_session, db_workspace
):
    """The path recorded by the first seed is what the second one reads back, so
    a workspace cannot drift to a new name just by being seeded twice."""
    await _add_document(
        db_session, db_workspace, title="strategy.md", markdown="# Strategy"
    )

    first = await migrate_workspace(db_session, db_workspace.id)
    second = await migrate_workspace(db_session, db_workspace.id)

    assert second.ok, second
    assert second.seeded_revision is None
    store = KnowledgeStore.for_workspace(db_workspace.id)
    paths = {t.path for t in await store.list_paths(first.seeded_revision)}
    assert paths == {"documents/strategy.md.xml"}
