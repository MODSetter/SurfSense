"""Integration tests for document versioning snapshot + cleanup."""

from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import Document, DocumentType, DocumentVersion, User, Workspace

pytestmark = pytest.mark.integration


@pytest_asyncio.fixture
async def db_document(
    db_session: AsyncSession, db_user: User, db_workspace: Workspace
) -> Document:
    doc = Document(
        title="Test Doc",
        document_type=DocumentType.LOCAL_FOLDER_FILE,
        document_metadata={},
        content="Summary of test doc.",
        content_hash="abc123",
        unique_identifier_hash="local_folder:test-folder:test.md",
        source_markdown="# Test\n\nOriginal content.",
        workspace_id=db_workspace.id,
        created_by_id=db_user.id,
    )
    db_session.add(doc)
    await db_session.flush()
    return doc


@pytest_asyncio.fixture
async def client(db_session: AsyncSession, db_user: User):
    """httpx over ASGI, bound to the transactional session and the owner."""
    import httpx
    from httpx import ASGITransport

    from app.app import app
    from app.auth.context import AuthContext
    from app.db import get_async_session
    from app.users import get_auth_context

    async def override_session():
        yield db_session

    async def override_auth() -> AuthContext:
        return AuthContext.session(db_user)

    previous = app.dependency_overrides.copy()
    app.dependency_overrides[get_async_session] = override_session
    app.dependency_overrides[get_auth_context] = override_auth
    try:
        async with httpx.AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test", timeout=30.0
        ) as c:
            yield c
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous)


async def test_restore_is_refused_for_a_git_backed_workspace(
    client, db_session, db_document, monkeypatch, workspace_flip
):
    """Restore rewrites content behind git's back, so it cannot be allowed.

    It is also the only writer of ``DocumentVersion`` rows on the save path, so
    this 409 is what makes "a save in a flagged workspace creates no version
    rows" true rather than merely intended.
    """
    from app.config import config as app_config
    from app.utils.document_versioning import create_version_snapshot

    await create_version_snapshot(db_session, db_document)
    await db_session.commit()
    before = await _version_count(db_session, db_document.id)
    monkeypatch.setattr(app_config, "KNOWLEDGE_STORE_ENABLED", True)
    workspace_flip(True)

    response = await client.post(
        f"/api/v1/documents/{db_document.id}/versions/1/restore"
    )

    assert response.status_code == 409
    assert await _version_count(db_session, db_document.id) == before


async def test_restore_still_works_for_an_unflipped_workspace(
    client, db_session, db_document, monkeypatch, workspace_flip
):
    """The 409 is per workspace, not per deployment.

    With the global flag on but this workspace still on Postgres, restore is the
    only way back — a guard keyed on the global flag would take it away from
    every workspace on the fleet the moment the flag is turned on.
    """
    from app.config import config as app_config
    from app.utils.document_versioning import create_version_snapshot

    # Past the 30-minute window, so restore's own pre-restore snapshot adds a
    # version instead of overwriting the one being restored.
    t0 = datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC)
    monkeypatch.setattr("app.utils.document_versioning._now", lambda: t0)
    await create_version_snapshot(db_session, db_document)
    db_document.source_markdown = "# Test\n\nLater content."
    db_document.content_hash = "def456"
    await db_session.commit()
    later = t0 + timedelta(minutes=31)
    monkeypatch.setattr("app.utils.document_versioning._now", lambda: later)
    monkeypatch.setattr(app_config, "KNOWLEDGE_STORE_ENABLED", True)
    workspace_flip(False)

    response = await client.post(
        f"/api/v1/documents/{db_document.id}/versions/1/restore"
    )

    assert response.status_code == 200
    await db_session.refresh(db_document)
    assert db_document.source_markdown == "# Test\n\nOriginal content."


async def _version_count(session: AsyncSession, document_id: int) -> int:
    result = await session.execute(
        select(func.count())
        .select_from(DocumentVersion)
        .where(DocumentVersion.document_id == document_id)
    )
    return result.scalar_one()


async def _get_versions(
    session: AsyncSession, document_id: int
) -> list[DocumentVersion]:
    result = await session.execute(
        select(DocumentVersion)
        .where(DocumentVersion.document_id == document_id)
        .order_by(DocumentVersion.version_number)
    )
    return list(result.scalars().all())


class TestCreateVersionSnapshot:
    """V1-V5: TDD slices for create_version_snapshot."""

    async def test_v1_creates_first_version(self, db_session, db_document):
        """V1: First snapshot creates version 1 with the document's current state."""
        from app.utils.document_versioning import create_version_snapshot

        await create_version_snapshot(db_session, db_document)

        versions = await _get_versions(db_session, db_document.id)
        assert len(versions) == 1
        assert versions[0].version_number == 1
        assert versions[0].source_markdown == "# Test\n\nOriginal content."
        assert versions[0].content_hash == "abc123"
        assert versions[0].title == "Test Doc"
        assert versions[0].document_id == db_document.id

    async def test_v2_creates_version_2_after_30_min(
        self, db_session, db_document, monkeypatch
    ):
        """V2: After 30+ minutes, a new version is created (not overwritten)."""
        from app.utils.document_versioning import create_version_snapshot

        t0 = datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC)
        monkeypatch.setattr("app.utils.document_versioning._now", lambda: t0)
        await create_version_snapshot(db_session, db_document)

        # Simulate content change and time passing
        db_document.source_markdown = "# Test\n\nUpdated content."
        db_document.content_hash = "def456"
        t1 = t0 + timedelta(minutes=31)
        monkeypatch.setattr("app.utils.document_versioning._now", lambda: t1)
        await create_version_snapshot(db_session, db_document)

        versions = await _get_versions(db_session, db_document.id)
        assert len(versions) == 2
        assert versions[0].version_number == 1
        assert versions[1].version_number == 2
        assert versions[1].source_markdown == "# Test\n\nUpdated content."

    async def test_v3_overwrites_within_30_min(
        self, db_session, db_document, monkeypatch
    ):
        """V3: Within 30 minutes, the latest version is overwritten."""
        from app.utils.document_versioning import create_version_snapshot

        t0 = datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC)
        monkeypatch.setattr("app.utils.document_versioning._now", lambda: t0)
        await create_version_snapshot(db_session, db_document)
        count_after_first = await _version_count(db_session, db_document.id)
        assert count_after_first == 1

        # Simulate quick edit within 30 minutes
        db_document.source_markdown = "# Test\n\nQuick edit."
        db_document.content_hash = "quick123"
        t1 = t0 + timedelta(minutes=10)
        monkeypatch.setattr("app.utils.document_versioning._now", lambda: t1)
        await create_version_snapshot(db_session, db_document)

        count_after_second = await _version_count(db_session, db_document.id)
        assert count_after_second == 1  # still 1, not 2

        versions = await _get_versions(db_session, db_document.id)
        assert versions[0].source_markdown == "# Test\n\nQuick edit."
        assert versions[0].content_hash == "quick123"

    async def test_v4_cleanup_90_day_old_versions(
        self, db_session, db_document, monkeypatch
    ):
        """V4: Versions older than 90 days are cleaned up."""
        from app.utils.document_versioning import create_version_snapshot

        base = datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC)

        # Create 5 versions spread across time: 3 older than 90 days, 2 recent
        for i in range(5):
            db_document.source_markdown = f"Content v{i + 1}"
            db_document.content_hash = f"hash_{i + 1}"
            t = base + timedelta(days=i) if i < 3 else base + timedelta(days=100 + i)
            monkeypatch.setattr("app.utils.document_versioning._now", lambda _t=t: _t)
            await create_version_snapshot(db_session, db_document)

        # Now trigger cleanup from a "current" time that makes the first 3 versions > 90 days old
        now = base + timedelta(days=200)
        monkeypatch.setattr("app.utils.document_versioning._now", lambda: now)
        db_document.source_markdown = "Content v6"
        db_document.content_hash = "hash_6"
        await create_version_snapshot(db_session, db_document)

        versions = await _get_versions(db_session, db_document.id)
        # The first 3 (old) should be cleaned up; versions 4, 5, 6 remain
        for v in versions:
            age = now - v.created_at.replace(tzinfo=UTC)
            assert age <= timedelta(days=90), f"Version {v.version_number} is too old"

    async def test_v5_cap_at_20_versions(self, db_session, db_document, monkeypatch):
        """V5: More than 20 versions triggers cap — oldest gets deleted."""
        from app.utils.document_versioning import create_version_snapshot

        base = datetime(2025, 6, 1, 12, 0, 0, tzinfo=UTC)

        # Create 21 versions (all within 90 days, each 31 min apart)
        for i in range(21):
            db_document.source_markdown = f"Content v{i + 1}"
            db_document.content_hash = f"hash_{i + 1}"
            t = base + timedelta(minutes=31 * i)
            monkeypatch.setattr("app.utils.document_versioning._now", lambda _t=t: _t)
            await create_version_snapshot(db_session, db_document)

        versions = await _get_versions(db_session, db_document.id)
        assert len(versions) == 20
        # The lowest version_number should be 2 (version 1 was the oldest and got capped)
        assert versions[0].version_number == 2
