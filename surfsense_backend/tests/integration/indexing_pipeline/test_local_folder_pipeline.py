"""Integration tests for local folder indexer — Tier 3 (I1-I5), Tier 4 (F1-F7), Tier 5 (P1)."""

import os
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import (
    Document,
    DocumentStatus,
    DocumentType,
    DocumentVersion,
    Folder,
    SearchSpace,
    User,
)

pytestmark = pytest.mark.integration

UNIFIED_FIXTURES = (
    "patched_summarize", "patched_embed_texts", "patched_chunk_text",
)


# ====================================================================
# Tier 3: Full Indexer Integration (I1-I5)
# ====================================================================


class TestFullIndexer:

    @pytest.mark.usefixtures(*UNIFIED_FIXTURES)
    async def test_i1_new_file_indexed(
        self,
        db_session: AsyncSession,
        db_user: User,
        db_search_space: SearchSpace,
        tmp_path: Path,
    ):
        """I1: Single new .md file is indexed with status READY."""
        from app.tasks.connector_indexers.local_folder_indexer import index_local_folder

        (tmp_path / "note.md").write_text("# Hello World\n\nContent here.")

        count, skipped, root_folder_id, err = await index_local_folder(
            session=db_session,
            search_space_id=db_search_space.id,
            user_id=str(db_user.id),
            folder_path=str(tmp_path),
            folder_name="test-folder",
        )

        assert err is None
        assert count == 1

        docs = (
            await db_session.execute(
                select(Document).where(
                    Document.document_type == DocumentType.LOCAL_FOLDER_FILE,
                    Document.search_space_id == db_search_space.id,
                )
            )
        ).scalars().all()
        assert len(docs) == 1
        assert docs[0].document_type == DocumentType.LOCAL_FOLDER_FILE
        assert DocumentStatus.is_state(docs[0].status, DocumentStatus.READY)

    @pytest.mark.usefixtures(*UNIFIED_FIXTURES)
    async def test_i2_unchanged_skipped(
        self,
        db_session: AsyncSession,
        db_user: User,
        db_search_space: SearchSpace,
        tmp_path: Path,
    ):
        """I2: Second run on unchanged directory creates no new documents."""
        from app.tasks.connector_indexers.local_folder_indexer import index_local_folder

        (tmp_path / "note.md").write_text("# Hello\n\nSame content.")

        count1, _, root_folder_id, _ = await index_local_folder(
            session=db_session,
            search_space_id=db_search_space.id,
            user_id=str(db_user.id),
            folder_path=str(tmp_path),
            folder_name="test-folder",
        )
        assert count1 == 1

        count2, _, _, _ = await index_local_folder(
            session=db_session,
            search_space_id=db_search_space.id,
            user_id=str(db_user.id),
            folder_path=str(tmp_path),
            folder_name="test-folder",
            root_folder_id=root_folder_id,
        )
        assert count2 == 0

        total = (
            await db_session.execute(
                select(func.count()).select_from(Document).where(
                    Document.document_type == DocumentType.LOCAL_FOLDER_FILE,
                    Document.search_space_id == db_search_space.id,
                )
            )
        ).scalar_one()
        assert total == 1

    @pytest.mark.usefixtures(*UNIFIED_FIXTURES)
    async def test_i3_changed_reindexed(
        self,
        db_session: AsyncSession,
        db_user: User,
        db_search_space: SearchSpace,
        tmp_path: Path,
    ):
        """I3: Modified file content triggers re-index and creates a version."""
        from app.tasks.connector_indexers.local_folder_indexer import index_local_folder

        f = tmp_path / "note.md"
        f.write_text("# Version 1\n\nOriginal.")

        _, _, root_folder_id, _ = await index_local_folder(
            session=db_session,
            search_space_id=db_search_space.id,
            user_id=str(db_user.id),
            folder_path=str(tmp_path),
            folder_name="test-folder",
        )

        f.write_text("# Version 2\n\nUpdated.")
        os.utime(f, (f.stat().st_atime + 10, f.stat().st_mtime + 10))

        count, _, _, _ = await index_local_folder(
            session=db_session,
            search_space_id=db_search_space.id,
            user_id=str(db_user.id),
            folder_path=str(tmp_path),
            folder_name="test-folder",
            root_folder_id=root_folder_id,
        )
        assert count == 1

        versions = (
            await db_session.execute(
                select(DocumentVersion).join(Document).where(
                    Document.document_type == DocumentType.LOCAL_FOLDER_FILE,
                    Document.search_space_id == db_search_space.id,
                )
            )
        ).scalars().all()
        assert len(versions) >= 1

    @pytest.mark.usefixtures(*UNIFIED_FIXTURES)
    async def test_i4_deleted_removed(
        self,
        db_session: AsyncSession,
        db_user: User,
        db_search_space: SearchSpace,
        tmp_path: Path,
    ):
        """I4: Deleted file is removed from DB on re-sync."""
        from app.tasks.connector_indexers.local_folder_indexer import index_local_folder

        f = tmp_path / "to_delete.md"
        f.write_text("# Delete me")

        _, _, root_folder_id, _ = await index_local_folder(
            session=db_session,
            search_space_id=db_search_space.id,
            user_id=str(db_user.id),
            folder_path=str(tmp_path),
            folder_name="test-folder",
        )

        docs_before = (
            await db_session.execute(
                select(func.count()).select_from(Document).where(
                    Document.document_type == DocumentType.LOCAL_FOLDER_FILE,
                    Document.search_space_id == db_search_space.id,
                )
            )
        ).scalar_one()
        assert docs_before == 1

        f.unlink()

        await index_local_folder(
            session=db_session,
            search_space_id=db_search_space.id,
            user_id=str(db_user.id),
            folder_path=str(tmp_path),
            folder_name="test-folder",
            root_folder_id=root_folder_id,
        )

        docs_after = (
            await db_session.execute(
                select(func.count()).select_from(Document).where(
                    Document.document_type == DocumentType.LOCAL_FOLDER_FILE,
                    Document.search_space_id == db_search_space.id,
                )
            )
        ).scalar_one()
        assert docs_after == 0

    @pytest.mark.usefixtures(*UNIFIED_FIXTURES)
    async def test_i5_single_file_mode(
        self,
        db_session: AsyncSession,
        db_user: User,
        db_search_space: SearchSpace,
        tmp_path: Path,
    ):
        """I5: Batch mode with a single file only processes that file."""
        from app.tasks.connector_indexers.local_folder_indexer import index_local_folder

        (tmp_path / "a.md").write_text("File A")
        (tmp_path / "b.md").write_text("File B")
        (tmp_path / "c.md").write_text("File C")

        count, _, _, _ = await index_local_folder(
            session=db_session,
            search_space_id=db_search_space.id,
            user_id=str(db_user.id),
            folder_path=str(tmp_path),
            folder_name="test-folder",
            target_file_paths=[str(tmp_path / "b.md")],
        )
        assert count == 1

        docs = (
            await db_session.execute(
                select(Document).where(
                    Document.document_type == DocumentType.LOCAL_FOLDER_FILE,
                    Document.search_space_id == db_search_space.id,
                )
            )
        ).scalars().all()
        assert len(docs) == 1
        assert docs[0].title == "b.md"


# ====================================================================
# Tier 4: Folder Mirroring (F1-F7)
# ====================================================================


class TestFolderMirroring:

    @pytest.mark.usefixtures(*UNIFIED_FIXTURES)
    async def test_f1_root_folder_created(
        self,
        db_session: AsyncSession,
        db_user: User,
        db_search_space: SearchSpace,
        tmp_path: Path,
    ):
        """F1: First sync creates a root Folder and returns root_folder_id."""
        from app.tasks.connector_indexers.local_folder_indexer import index_local_folder

        (tmp_path / "root.md").write_text("Root file")

        _, _, root_folder_id, _ = await index_local_folder(
            session=db_session,
            search_space_id=db_search_space.id,
            user_id=str(db_user.id),
            folder_path=str(tmp_path),
            folder_name="test-folder",
        )

        assert root_folder_id is not None

        root_folder = (
            await db_session.execute(select(Folder).where(Folder.id == root_folder_id))
        ).scalar_one()
        assert root_folder.name == "test-folder"

    @pytest.mark.usefixtures(*UNIFIED_FIXTURES)
    async def test_f2_nested_folder_rows(
        self,
        db_session: AsyncSession,
        db_user: User,
        db_search_space: SearchSpace,
        tmp_path: Path,
    ):
        """F2: Nested dirs create Folder rows with correct parent_id chain."""
        from app.tasks.connector_indexers.local_folder_indexer import index_local_folder

        daily = tmp_path / "notes" / "daily"
        daily.mkdir(parents=True)
        weekly = tmp_path / "notes" / "weekly"
        weekly.mkdir(parents=True)
        (daily / "today.md").write_text("today")
        (weekly / "review.md").write_text("review")

        await index_local_folder(
            session=db_session,
            search_space_id=db_search_space.id,
            user_id=str(db_user.id),
            folder_path=str(tmp_path),
            folder_name="test-folder",
        )

        folders = (
            await db_session.execute(
                select(Folder).where(Folder.search_space_id == db_search_space.id)
            )
        ).scalars().all()

        folder_names = {f.name for f in folders}
        assert "notes" in folder_names
        assert "daily" in folder_names
        assert "weekly" in folder_names

        notes_folder = next(f for f in folders if f.name == "notes")
        daily_folder = next(f for f in folders if f.name == "daily")
        weekly_folder = next(f for f in folders if f.name == "weekly")

        assert daily_folder.parent_id == notes_folder.id
        assert weekly_folder.parent_id == notes_folder.id

    @pytest.mark.usefixtures(*UNIFIED_FIXTURES)
    async def test_f3_resync_reuses_folders(
        self,
        db_session: AsyncSession,
        db_user: User,
        db_search_space: SearchSpace,
        tmp_path: Path,
    ):
        """F3: Re-sync reuses existing Folder rows, no duplicates."""
        from app.tasks.connector_indexers.local_folder_indexer import index_local_folder

        sub = tmp_path / "docs"
        sub.mkdir()
        (sub / "file.md").write_text("content")

        _, _, root_folder_id, _ = await index_local_folder(
            session=db_session,
            search_space_id=db_search_space.id,
            user_id=str(db_user.id),
            folder_path=str(tmp_path),
            folder_name="test-folder",
        )

        folders_before = (
            await db_session.execute(
                select(Folder).where(Folder.search_space_id == db_search_space.id)
            )
        ).scalars().all()
        ids_before = {f.id for f in folders_before}

        await index_local_folder(
            session=db_session,
            search_space_id=db_search_space.id,
            user_id=str(db_user.id),
            folder_path=str(tmp_path),
            folder_name="test-folder",
            root_folder_id=root_folder_id,
        )

        folders_after = (
            await db_session.execute(
                select(Folder).where(Folder.search_space_id == db_search_space.id)
            )
        ).scalars().all()
        ids_after = {f.id for f in folders_after}

        assert ids_before == ids_after

    @pytest.mark.usefixtures(*UNIFIED_FIXTURES)
    async def test_f4_folder_id_assigned(
        self,
        db_session: AsyncSession,
        db_user: User,
        db_search_space: SearchSpace,
        tmp_path: Path,
    ):
        """F4: Documents get correct folder_id based on their directory."""
        from app.tasks.connector_indexers.local_folder_indexer import index_local_folder

        daily = tmp_path / "notes" / "daily"
        daily.mkdir(parents=True)
        (daily / "today.md").write_text("today note")
        (tmp_path / "root.md").write_text("root note")

        _, _, root_folder_id, _ = await index_local_folder(
            session=db_session,
            search_space_id=db_search_space.id,
            user_id=str(db_user.id),
            folder_path=str(tmp_path),
            folder_name="test-folder",
        )

        docs = (
            await db_session.execute(
                select(Document).where(
                    Document.document_type == DocumentType.LOCAL_FOLDER_FILE,
                    Document.search_space_id == db_search_space.id,
                )
            )
        ).scalars().all()

        today_doc = next(d for d in docs if d.title == "today.md")
        root_doc = next(d for d in docs if d.title == "root.md")

        daily_folder = (
            await db_session.execute(
                select(Folder).where(Folder.name == "daily")
            )
        ).scalar_one()

        assert today_doc.folder_id == daily_folder.id

        assert root_doc.folder_id == root_folder_id

    @pytest.mark.usefixtures(*UNIFIED_FIXTURES)
    async def test_f5_empty_folder_cleanup(
        self,
        db_session: AsyncSession,
        db_user: User,
        db_search_space: SearchSpace,
        tmp_path: Path,
    ):
        """F5: Deleted dir's empty Folder row is cleaned up on re-sync."""
        from app.tasks.connector_indexers.local_folder_indexer import index_local_folder
        import shutil

        daily = tmp_path / "notes" / "daily"
        daily.mkdir(parents=True)
        weekly = tmp_path / "notes" / "weekly"
        weekly.mkdir(parents=True)
        (daily / "today.md").write_text("today")
        (weekly / "review.md").write_text("review")

        _, _, root_folder_id, _ = await index_local_folder(
            session=db_session,
            search_space_id=db_search_space.id,
            user_id=str(db_user.id),
            folder_path=str(tmp_path),
            folder_name="test-folder",
        )

        weekly_folder = (
            await db_session.execute(
                select(Folder).where(Folder.name == "weekly")
            )
        ).scalar_one_or_none()
        assert weekly_folder is not None

        shutil.rmtree(weekly)

        await index_local_folder(
            session=db_session,
            search_space_id=db_search_space.id,
            user_id=str(db_user.id),
            folder_path=str(tmp_path),
            folder_name="test-folder",
            root_folder_id=root_folder_id,
        )

        weekly_after = (
            await db_session.execute(
                select(Folder).where(Folder.name == "weekly")
            )
        ).scalar_one_or_none()
        assert weekly_after is None

        daily_after = (
            await db_session.execute(
                select(Folder).where(Folder.name == "daily")
            )
        ).scalar_one_or_none()
        assert daily_after is not None

    @pytest.mark.usefixtures(*UNIFIED_FIXTURES)
    async def test_f6_single_file_creates_subfolder(
        self,
        db_session: AsyncSession,
        db_user: User,
        db_search_space: SearchSpace,
        tmp_path: Path,
    ):
        """F6: Single-file mode creates missing Folder rows and assigns correct folder_id."""
        from app.tasks.connector_indexers.local_folder_indexer import index_local_folder

        (tmp_path / "root.md").write_text("root")

        _, _, root_folder_id, _ = await index_local_folder(
            session=db_session,
            search_space_id=db_search_space.id,
            user_id=str(db_user.id),
            folder_path=str(tmp_path),
            folder_name="test-folder",
        )

        sub = tmp_path / "notes" / "daily"
        sub.mkdir(parents=True)
        (sub / "new.md").write_text("new note in subfolder")

        count, _, _, _ = await index_local_folder(
            session=db_session,
            search_space_id=db_search_space.id,
            user_id=str(db_user.id),
            folder_path=str(tmp_path),
            folder_name="test-folder",
            target_file_paths=[str(sub / "new.md")],
            root_folder_id=root_folder_id,
        )
        assert count == 1

        doc = (
            await db_session.execute(
                select(Document).where(
                    Document.document_type == DocumentType.LOCAL_FOLDER_FILE,
                    Document.title == "new.md",
                )
            )
        ).scalar_one()

        daily_folder = (
            await db_session.execute(
                select(Folder).where(Folder.name == "daily")
            )
        ).scalar_one()

        assert doc.folder_id == daily_folder.id
        assert daily_folder.parent_id is not None

        notes_folder = (
            await db_session.execute(
                select(Folder).where(Folder.name == "notes")
            )
        ).scalar_one()
        assert daily_folder.parent_id == notes_folder.id
        assert notes_folder.parent_id == root_folder_id

    @pytest.mark.usefixtures(*UNIFIED_FIXTURES)
    async def test_f7_single_file_delete_cleans_empty_folders(
        self,
        db_session: AsyncSession,
        db_user: User,
        db_search_space: SearchSpace,
        tmp_path: Path,
    ):
        """F7: Deleting the only file in a subfolder via batch mode removes empty Folder rows."""
        from app.tasks.connector_indexers.local_folder_indexer import index_local_folder

        sub = tmp_path / "notes" / "ephemeral"
        sub.mkdir(parents=True)
        (sub / "temp.md").write_text("temporary")
        (tmp_path / "keep.md").write_text("keep this")

        _, _, root_folder_id, _ = await index_local_folder(
            session=db_session,
            search_space_id=db_search_space.id,
            user_id=str(db_user.id),
            folder_path=str(tmp_path),
            folder_name="test-folder",
        )

        eph_folder = (
            await db_session.execute(
                select(Folder).where(Folder.name == "ephemeral")
            )
        ).scalar_one_or_none()
        assert eph_folder is not None

        target = sub / "temp.md"
        target.unlink()

        await index_local_folder(
            session=db_session,
            search_space_id=db_search_space.id,
            user_id=str(db_user.id),
            folder_path=str(tmp_path),
            folder_name="test-folder",
            target_file_paths=[str(target)],
            root_folder_id=root_folder_id,
        )

        eph_after = (
            await db_session.execute(
                select(Folder).where(Folder.name == "ephemeral")
            )
        ).scalar_one_or_none()
        assert eph_after is None

        notes_after = (
            await db_session.execute(
                select(Folder).where(Folder.name == "notes")
            )
        ).scalar_one_or_none()
        assert notes_after is None


# ====================================================================
# Tier 5: Pipeline Integration (P1)
# ====================================================================


class TestPipelineIntegration:

    @pytest.mark.usefixtures(*UNIFIED_FIXTURES)
    async def test_p1_local_folder_file_through_pipeline(
        self,
        db_session: AsyncSession,
        db_user: User,
        db_search_space: SearchSpace,
        mocker,
    ):
        """P1: LOCAL_FOLDER_FILE ConnectorDocument through prepare+index to READY."""
        from app.indexing_pipeline.connector_document import ConnectorDocument
        from app.indexing_pipeline.indexing_pipeline_service import IndexingPipelineService

        doc = ConnectorDocument(
            title="Test Local File",
            source_markdown="## Local file\n\nContent from disk.",
            unique_id="test-folder:test.md",
            document_type=DocumentType.LOCAL_FOLDER_FILE,
            search_space_id=db_search_space.id,
            connector_id=None,
            created_by_id=str(db_user.id),
        )

        service = IndexingPipelineService(session=db_session)
        prepared = await service.prepare_for_indexing([doc])
        assert len(prepared) == 1

        db_doc = prepared[0]
        result = await service.index(db_doc, doc, llm=mocker.Mock())
        assert result is not None

        docs = (
            await db_session.execute(
                select(Document).where(
                    Document.document_type == DocumentType.LOCAL_FOLDER_FILE,
                    Document.search_space_id == db_search_space.id,
                )
            )
        ).scalars().all()
        assert len(docs) == 1
        assert DocumentStatus.is_state(docs[0].status, DocumentStatus.READY)
