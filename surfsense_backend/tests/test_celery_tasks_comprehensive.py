"""Comprehensive tests for Celery tasks module."""

from datetime import datetime, timedelta, UTC
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ============================================================================
# SCHEDULE CHECKER TASK TESTS
# ============================================================================


class TestScheduleCheckerTaskSessionMaker:
    """Tests for schedule checker task session maker."""

    def test_get_celery_session_maker_returns_maker(self):
        """Test that get_celery_session_maker returns a session maker."""
        from app.tasks.celery_tasks.schedule_checker_task import get_celery_session_maker

        with patch(
            "app.tasks.celery_tasks.schedule_checker_task.create_async_engine"
        ) as mock_engine:
            with patch(
                "app.tasks.celery_tasks.schedule_checker_task.async_sessionmaker"
            ) as mock_maker:
                mock_engine.return_value = MagicMock()
                mock_maker.return_value = MagicMock()

                result = get_celery_session_maker()

                assert result is not None
                mock_engine.assert_called_once()

    def test_get_celery_session_maker_uses_null_pool(self):
        """Test that NullPool is used."""
        from sqlalchemy.pool import NullPool
        from app.tasks.celery_tasks.schedule_checker_task import get_celery_session_maker

        with patch(
            "app.tasks.celery_tasks.schedule_checker_task.create_async_engine"
        ) as mock_engine:
            with patch(
                "app.tasks.celery_tasks.schedule_checker_task.async_sessionmaker"
            ):
                get_celery_session_maker()

                call_kwargs = mock_engine.call_args[1]
                assert call_kwargs.get("poolclass") == NullPool


class TestCheckAndTriggerSchedules:
    """Tests for _check_and_trigger_schedules function."""

    @pytest.mark.asyncio
    async def test_no_due_connectors(self):
        """Test when no connectors are due for indexing."""
        from app.tasks.celery_tasks.schedule_checker_task import (
            _check_and_trigger_schedules,
        )

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        with patch(
            "app.tasks.celery_tasks.schedule_checker_task.get_celery_session_maker"
        ) as mock_maker:
            mock_context = AsyncMock()
            mock_context.__aenter__.return_value = mock_session
            mock_context.__aexit__.return_value = None
            mock_maker.return_value.return_value = mock_context

            await _check_and_trigger_schedules()

            mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_triggers_slack_connector_task(self):
        """Test triggering Slack connector indexing task."""
        from app.tasks.celery_tasks.schedule_checker_task import (
            _check_and_trigger_schedules,
        )
        from app.db import SearchSourceConnectorType

        mock_session = AsyncMock()
        mock_connector = MagicMock()
        mock_connector.id = 1
        mock_connector.search_space_id = 1
        mock_connector.user_id = "user123"
        mock_connector.connector_type = SearchSourceConnectorType.SLACK_CONNECTOR
        mock_connector.indexing_frequency_minutes = 60
        mock_connector.next_scheduled_at = datetime.now(UTC) - timedelta(minutes=5)

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_connector]
        mock_session.execute.return_value = mock_result

        with patch(
            "app.tasks.celery_tasks.schedule_checker_task.get_celery_session_maker"
        ) as mock_maker:
            mock_context = AsyncMock()
            mock_context.__aenter__.return_value = mock_session
            mock_context.__aexit__.return_value = None
            mock_maker.return_value.return_value = mock_context

            with patch(
                "app.tasks.celery_tasks.connector_tasks.index_slack_messages_task"
            ) as mock_slack_task:
                mock_slack_task.delay = MagicMock()

                await _check_and_trigger_schedules()

                mock_slack_task.delay.assert_called_once_with(
                    1, 1, "user123", None, None
                )
                assert mock_connector.next_scheduled_at is not None

    @pytest.mark.asyncio
    async def test_triggers_notion_connector_task(self):
        """Test triggering Notion connector indexing task."""
        from app.tasks.celery_tasks.schedule_checker_task import (
            _check_and_trigger_schedules,
        )
        from app.db import SearchSourceConnectorType

        mock_session = AsyncMock()
        mock_connector = MagicMock()
        mock_connector.id = 2
        mock_connector.search_space_id = 1
        mock_connector.user_id = "user456"
        mock_connector.connector_type = SearchSourceConnectorType.NOTION_CONNECTOR
        mock_connector.indexing_frequency_minutes = 120
        mock_connector.next_scheduled_at = datetime.now(UTC) - timedelta(minutes=10)

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_connector]
        mock_session.execute.return_value = mock_result

        with patch(
            "app.tasks.celery_tasks.schedule_checker_task.get_celery_session_maker"
        ) as mock_maker:
            mock_context = AsyncMock()
            mock_context.__aenter__.return_value = mock_session
            mock_context.__aexit__.return_value = None
            mock_maker.return_value.return_value = mock_context

            with patch(
                "app.tasks.celery_tasks.connector_tasks.index_notion_pages_task"
            ) as mock_notion_task:
                mock_notion_task.delay = MagicMock()

                await _check_and_trigger_schedules()

                mock_notion_task.delay.assert_called_once()

    @pytest.mark.asyncio
    async def test_triggers_github_connector_task(self):
        """Test triggering GitHub connector indexing task."""
        from app.tasks.celery_tasks.schedule_checker_task import (
            _check_and_trigger_schedules,
        )
        from app.db import SearchSourceConnectorType

        mock_session = AsyncMock()
        mock_connector = MagicMock()
        mock_connector.id = 3
        mock_connector.search_space_id = 2
        mock_connector.user_id = "user789"
        mock_connector.connector_type = SearchSourceConnectorType.GITHUB_CONNECTOR
        mock_connector.indexing_frequency_minutes = 30
        mock_connector.next_scheduled_at = datetime.now(UTC) - timedelta(minutes=1)

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_connector]
        mock_session.execute.return_value = mock_result

        with patch(
            "app.tasks.celery_tasks.schedule_checker_task.get_celery_session_maker"
        ) as mock_maker:
            mock_context = AsyncMock()
            mock_context.__aenter__.return_value = mock_session
            mock_context.__aexit__.return_value = None
            mock_maker.return_value.return_value = mock_context

            with patch(
                "app.tasks.celery_tasks.connector_tasks.index_github_repos_task"
            ) as mock_github_task:
                mock_github_task.delay = MagicMock()

                await _check_and_trigger_schedules()

                mock_github_task.delay.assert_called_once()

    @pytest.mark.asyncio
    async def test_triggers_multiple_connector_types(self):
        """Test triggering multiple different connector types."""
        from app.tasks.celery_tasks.schedule_checker_task import (
            _check_and_trigger_schedules,
        )
        from app.db import SearchSourceConnectorType

        mock_session = AsyncMock()

        # Create multiple connectors of different types
        mock_connectors = []
        connector_types = [
            SearchSourceConnectorType.SLACK_CONNECTOR,
            SearchSourceConnectorType.JIRA_CONNECTOR,
            SearchSourceConnectorType.CONFLUENCE_CONNECTOR,
        ]

        for i, ct in enumerate(connector_types):
            mock_connector = MagicMock()
            mock_connector.id = i + 1
            mock_connector.search_space_id = 1
            mock_connector.user_id = f"user{i}"
            mock_connector.connector_type = ct
            mock_connector.indexing_frequency_minutes = 60
            mock_connector.next_scheduled_at = datetime.now(UTC) - timedelta(minutes=5)
            mock_connectors.append(mock_connector)

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_connectors
        mock_session.execute.return_value = mock_result

        with patch(
            "app.tasks.celery_tasks.schedule_checker_task.get_celery_session_maker"
        ) as mock_maker:
            mock_context = AsyncMock()
            mock_context.__aenter__.return_value = mock_session
            mock_context.__aexit__.return_value = None
            mock_maker.return_value.return_value = mock_context

            with patch(
                "app.tasks.celery_tasks.connector_tasks.index_slack_messages_task"
            ) as mock_slack:
                with patch(
                    "app.tasks.celery_tasks.connector_tasks.index_jira_issues_task"
                ) as mock_jira:
                    with patch(
                        "app.tasks.celery_tasks.connector_tasks.index_confluence_pages_task"
                    ) as mock_confluence:
                        mock_slack.delay = MagicMock()
                        mock_jira.delay = MagicMock()
                        mock_confluence.delay = MagicMock()

                        await _check_and_trigger_schedules()

                        mock_slack.delay.assert_called_once()
                        mock_jira.delay.assert_called_once()
                        mock_confluence.delay.assert_called_once()

    @pytest.mark.asyncio
    async def test_handles_unknown_connector_type(self):
        """Test handling of unknown connector type gracefully."""
        from app.tasks.celery_tasks.schedule_checker_task import (
            _check_and_trigger_schedules,
        )

        mock_session = AsyncMock()
        mock_connector = MagicMock()
        mock_connector.id = 1
        mock_connector.search_space_id = 1
        mock_connector.user_id = "user123"
        mock_connector.connector_type = MagicMock()  # Unknown type
        mock_connector.connector_type.value = "UNKNOWN_CONNECTOR"
        mock_connector.indexing_frequency_minutes = 60
        mock_connector.next_scheduled_at = datetime.now(UTC) - timedelta(minutes=5)

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_connector]
        mock_session.execute.return_value = mock_result

        with patch(
            "app.tasks.celery_tasks.schedule_checker_task.get_celery_session_maker"
        ) as mock_maker:
            mock_context = AsyncMock()
            mock_context.__aenter__.return_value = mock_session
            mock_context.__aexit__.return_value = None
            mock_maker.return_value.return_value = mock_context

            # Should not raise an exception
            await _check_and_trigger_schedules()

    @pytest.mark.asyncio
    async def test_updates_next_scheduled_at(self):
        """Test that next_scheduled_at is updated after triggering."""
        from app.tasks.celery_tasks.schedule_checker_task import (
            _check_and_trigger_schedules,
        )
        from app.db import SearchSourceConnectorType

        mock_session = AsyncMock()
        mock_connector = MagicMock()
        mock_connector.id = 1
        mock_connector.search_space_id = 1
        mock_connector.user_id = "user123"
        mock_connector.connector_type = SearchSourceConnectorType.SLACK_CONNECTOR
        mock_connector.indexing_frequency_minutes = 60
        original_time = datetime.now(UTC) - timedelta(minutes=5)
        mock_connector.next_scheduled_at = original_time

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_connector]
        mock_session.execute.return_value = mock_result

        with patch(
            "app.tasks.celery_tasks.schedule_checker_task.get_celery_session_maker"
        ) as mock_maker:
            mock_context = AsyncMock()
            mock_context.__aenter__.return_value = mock_session
            mock_context.__aexit__.return_value = None
            mock_maker.return_value.return_value = mock_context

            with patch(
                "app.tasks.celery_tasks.connector_tasks.index_slack_messages_task"
            ) as mock_slack:
                mock_slack.delay = MagicMock()

                await _check_and_trigger_schedules()

                # Check that next_scheduled_at was updated
                assert mock_connector.next_scheduled_at != original_time
                mock_session.commit.assert_called()

    @pytest.mark.asyncio
    async def test_handles_database_error(self):
        """Test handling of database errors."""
        from app.tasks.celery_tasks.schedule_checker_task import (
            _check_and_trigger_schedules,
        )
        from sqlalchemy.exc import SQLAlchemyError

        mock_session = AsyncMock()
        mock_session.execute.side_effect = SQLAlchemyError("DB error")

        with patch(
            "app.tasks.celery_tasks.schedule_checker_task.get_celery_session_maker"
        ) as mock_maker:
            mock_context = AsyncMock()
            mock_context.__aenter__.return_value = mock_session
            mock_context.__aexit__.return_value = None
            mock_maker.return_value.return_value = mock_context

            # Should not raise, just log error
            await _check_and_trigger_schedules()

            mock_session.rollback.assert_called_once()


# ============================================================================
# BLOCKNOTE MIGRATION TASK TESTS
# ============================================================================


class TestBlocknoteMigrationTaskSessionMaker:
    """Tests for blocknote migration task session maker."""

    def test_get_celery_session_maker_returns_maker(self):
        """Test that get_celery_session_maker returns a session maker."""
        from app.tasks.celery_tasks.blocknote_migration_tasks import (
            get_celery_session_maker,
        )

        with patch(
            "app.tasks.celery_tasks.blocknote_migration_tasks.create_async_engine"
        ) as mock_engine:
            with patch(
                "app.tasks.celery_tasks.blocknote_migration_tasks.async_sessionmaker"
            ) as mock_maker:
                mock_engine.return_value = MagicMock()
                mock_maker.return_value = MagicMock()

                result = get_celery_session_maker()

                assert result is not None

    def test_get_celery_session_maker_uses_null_pool(self):
        """Test that NullPool is used."""
        from sqlalchemy.pool import NullPool
        from app.tasks.celery_tasks.blocknote_migration_tasks import (
            get_celery_session_maker,
        )

        with patch(
            "app.tasks.celery_tasks.blocknote_migration_tasks.create_async_engine"
        ) as mock_engine:
            with patch(
                "app.tasks.celery_tasks.blocknote_migration_tasks.async_sessionmaker"
            ):
                get_celery_session_maker()

                call_kwargs = mock_engine.call_args[1]
                assert call_kwargs.get("poolclass") == NullPool


class TestPopulateBlocknoteForDocuments:
    """Tests for _populate_blocknote_for_documents function."""

    @pytest.mark.asyncio
    async def test_no_documents_to_process(self):
        """Test when no documents need blocknote population."""
        from app.tasks.celery_tasks.blocknote_migration_tasks import (
            _populate_blocknote_for_documents,
        )

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        with patch(
            "app.tasks.celery_tasks.blocknote_migration_tasks.get_celery_session_maker"
        ) as mock_maker:
            mock_context = AsyncMock()
            mock_context.__aenter__.return_value = mock_session
            mock_context.__aexit__.return_value = None
            mock_maker.return_value.return_value = mock_context

            await _populate_blocknote_for_documents()

            mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_processes_documents_with_chunks(self):
        """Test processing documents that have chunks."""
        from app.tasks.celery_tasks.blocknote_migration_tasks import (
            _populate_blocknote_for_documents,
        )

        mock_session = AsyncMock()

        # Create mock document with chunks
        mock_chunk1 = MagicMock()
        mock_chunk1.id = 1
        mock_chunk1.content = "# Header\n\nFirst chunk content"

        mock_chunk2 = MagicMock()
        mock_chunk2.id = 2
        mock_chunk2.content = "Second chunk content"

        mock_document = MagicMock()
        mock_document.id = 1
        mock_document.title = "Test Document"
        mock_document.chunks = [mock_chunk1, mock_chunk2]
        mock_document.blocknote_document = None

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_document]
        mock_session.execute.return_value = mock_result

        with patch(
            "app.tasks.celery_tasks.blocknote_migration_tasks.get_celery_session_maker"
        ) as mock_maker:
            mock_context = AsyncMock()
            mock_context.__aenter__.return_value = mock_session
            mock_context.__aexit__.return_value = None
            mock_maker.return_value.return_value = mock_context

            with patch(
                "app.tasks.celery_tasks.blocknote_migration_tasks.convert_markdown_to_blocknote",
                new_callable=AsyncMock,
            ) as mock_convert:
                mock_convert.return_value = {"type": "doc", "content": []}

                await _populate_blocknote_for_documents()

                mock_convert.assert_called_once()
                mock_session.commit.assert_called()

    @pytest.mark.asyncio
    async def test_skips_documents_without_chunks(self):
        """Test skipping documents that have no chunks."""
        from app.tasks.celery_tasks.blocknote_migration_tasks import (
            _populate_blocknote_for_documents,
        )

        mock_session = AsyncMock()

        mock_document = MagicMock()
        mock_document.id = 1
        mock_document.title = "Empty Document"
        mock_document.chunks = []
        mock_document.blocknote_document = None

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_document]
        mock_session.execute.return_value = mock_result

        with patch(
            "app.tasks.celery_tasks.blocknote_migration_tasks.get_celery_session_maker"
        ) as mock_maker:
            mock_context = AsyncMock()
            mock_context.__aenter__.return_value = mock_session
            mock_context.__aexit__.return_value = None
            mock_maker.return_value.return_value = mock_context

            with patch(
                "app.tasks.celery_tasks.blocknote_migration_tasks.convert_markdown_to_blocknote",
                new_callable=AsyncMock,
            ) as mock_convert:
                await _populate_blocknote_for_documents()

                # Should not call convert for empty document
                mock_convert.assert_not_called()

    @pytest.mark.asyncio
    async def test_processes_specific_document_ids(self):
        """Test processing only specific document IDs."""
        from app.tasks.celery_tasks.blocknote_migration_tasks import (
            _populate_blocknote_for_documents,
        )

        mock_session = AsyncMock()

        mock_chunk = MagicMock()
        mock_chunk.id = 1
        mock_chunk.content = "Test content"

        mock_document = MagicMock()
        mock_document.id = 5
        mock_document.title = "Specific Document"
        mock_document.chunks = [mock_chunk]
        mock_document.blocknote_document = None

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_document]
        mock_session.execute.return_value = mock_result

        with patch(
            "app.tasks.celery_tasks.blocknote_migration_tasks.get_celery_session_maker"
        ) as mock_maker:
            mock_context = AsyncMock()
            mock_context.__aenter__.return_value = mock_session
            mock_context.__aexit__.return_value = None
            mock_maker.return_value.return_value = mock_context

            with patch(
                "app.tasks.celery_tasks.blocknote_migration_tasks.convert_markdown_to_blocknote",
                new_callable=AsyncMock,
            ) as mock_convert:
                mock_convert.return_value = {"type": "doc", "content": []}

                await _populate_blocknote_for_documents(document_ids=[5, 10, 15])

                mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_handles_conversion_failure(self):
        """Test handling conversion failures gracefully."""
        from app.tasks.celery_tasks.blocknote_migration_tasks import (
            _populate_blocknote_for_documents,
        )

        mock_session = AsyncMock()

        mock_chunk = MagicMock()
        mock_chunk.id = 1
        mock_chunk.content = "Test content"

        mock_document = MagicMock()
        mock_document.id = 1
        mock_document.title = "Test Document"
        mock_document.chunks = [mock_chunk]
        mock_document.blocknote_document = None

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_document]
        mock_session.execute.return_value = mock_result

        with patch(
            "app.tasks.celery_tasks.blocknote_migration_tasks.get_celery_session_maker"
        ) as mock_maker:
            mock_context = AsyncMock()
            mock_context.__aenter__.return_value = mock_session
            mock_context.__aexit__.return_value = None
            mock_maker.return_value.return_value = mock_context

            with patch(
                "app.tasks.celery_tasks.blocknote_migration_tasks.convert_markdown_to_blocknote",
                new_callable=AsyncMock,
            ) as mock_convert:
                mock_convert.return_value = None  # Conversion failed

                await _populate_blocknote_for_documents()

                # Should still commit (with failures tracked)
                mock_session.commit.assert_called()

    @pytest.mark.asyncio
    async def test_batch_processing(self):
        """Test batch processing of multiple documents."""
        from app.tasks.celery_tasks.blocknote_migration_tasks import (
            _populate_blocknote_for_documents,
        )

        mock_session = AsyncMock()

        # Create multiple documents
        documents = []
        for i in range(5):
            mock_chunk = MagicMock()
            mock_chunk.id = i
            mock_chunk.content = f"Content {i}"

            mock_doc = MagicMock()
            mock_doc.id = i
            mock_doc.title = f"Document {i}"
            mock_doc.chunks = [mock_chunk]
            mock_doc.blocknote_document = None
            documents.append(mock_doc)

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = documents
        mock_session.execute.return_value = mock_result

        with patch(
            "app.tasks.celery_tasks.blocknote_migration_tasks.get_celery_session_maker"
        ) as mock_maker:
            mock_context = AsyncMock()
            mock_context.__aenter__.return_value = mock_session
            mock_context.__aexit__.return_value = None
            mock_maker.return_value.return_value = mock_context

            with patch(
                "app.tasks.celery_tasks.blocknote_migration_tasks.convert_markdown_to_blocknote",
                new_callable=AsyncMock,
            ) as mock_convert:
                mock_convert.return_value = {"type": "doc", "content": []}

                await _populate_blocknote_for_documents(batch_size=2)

                # Should have called convert for each document
                assert mock_convert.call_count == 5


# ============================================================================
# DOCUMENT REINDEX TASK TESTS
# ============================================================================


class TestDocumentReindexTaskSessionMaker:
    """Tests for document reindex task session maker."""

    def test_get_celery_session_maker_returns_maker(self):
        """Test that get_celery_session_maker returns a session maker."""
        from app.tasks.celery_tasks.document_reindex_tasks import get_celery_session_maker

        with patch(
            "app.tasks.celery_tasks.document_reindex_tasks.create_async_engine"
        ) as mock_engine:
            with patch(
                "app.tasks.celery_tasks.document_reindex_tasks.async_sessionmaker"
            ) as mock_maker:
                mock_engine.return_value = MagicMock()
                mock_maker.return_value = MagicMock()

                result = get_celery_session_maker()

                assert result is not None

    def test_get_celery_session_maker_uses_null_pool(self):
        """Test that NullPool is used."""
        from sqlalchemy.pool import NullPool
        from app.tasks.celery_tasks.document_reindex_tasks import get_celery_session_maker

        with patch(
            "app.tasks.celery_tasks.document_reindex_tasks.create_async_engine"
        ) as mock_engine:
            with patch(
                "app.tasks.celery_tasks.document_reindex_tasks.async_sessionmaker"
            ):
                get_celery_session_maker()

                call_kwargs = mock_engine.call_args[1]
                assert call_kwargs.get("poolclass") == NullPool


class TestReindexDocument:
    """Tests for _reindex_document function."""

    @pytest.mark.asyncio
    async def test_document_not_found(self):
        """Test handling when document is not found."""
        from app.tasks.celery_tasks.document_reindex_tasks import _reindex_document

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = None
        mock_session.execute.return_value = mock_result

        with patch(
            "app.tasks.celery_tasks.document_reindex_tasks.get_celery_session_maker"
        ) as mock_maker:
            mock_context = AsyncMock()
            mock_context.__aenter__.return_value = mock_session
            mock_context.__aexit__.return_value = None
            mock_maker.return_value.return_value = mock_context

            await _reindex_document(999, "user1")

            # Should not commit anything
            mock_session.commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_document_without_blocknote_content(self):
        """Test handling document without blocknote content."""
        from app.tasks.celery_tasks.document_reindex_tasks import _reindex_document

        mock_session = AsyncMock()
        mock_document = MagicMock()
        mock_document.id = 1
        mock_document.blocknote_document = None

        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = mock_document
        mock_session.execute.return_value = mock_result

        with patch(
            "app.tasks.celery_tasks.document_reindex_tasks.get_celery_session_maker"
        ) as mock_maker:
            mock_context = AsyncMock()
            mock_context.__aenter__.return_value = mock_session
            mock_context.__aexit__.return_value = None
            mock_maker.return_value.return_value = mock_context

            await _reindex_document(1, "user1")

            mock_session.commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_successful_reindex(self):
        """Test successful document reindexing."""
        from app.tasks.celery_tasks.document_reindex_tasks import _reindex_document
        from app.db import DocumentType

        mock_session = AsyncMock()
        # session.add is synchronous, so use MagicMock
        mock_session.add = MagicMock()
        mock_document = MagicMock()
        mock_document.id = 1
        mock_document.title = "Test Document"
        mock_document.blocknote_document = {"type": "doc", "content": []}
        mock_document.document_type = DocumentType.FILE
        mock_document.search_space_id = 1
        mock_document.chunks = []

        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = mock_document
        mock_session.execute.return_value = mock_result

        with patch(
            "app.tasks.celery_tasks.document_reindex_tasks.get_celery_session_maker"
        ) as mock_maker:
            mock_context = AsyncMock()
            mock_context.__aenter__.return_value = mock_session
            mock_context.__aexit__.return_value = None
            mock_maker.return_value.return_value = mock_context

            with patch(
                "app.tasks.celery_tasks.document_reindex_tasks.convert_blocknote_to_markdown",
                new_callable=AsyncMock,
            ) as mock_convert:
                mock_convert.return_value = "# Test Document\n\nContent here"

                with patch(
                    "app.tasks.celery_tasks.document_reindex_tasks.create_document_chunks",
                    new_callable=AsyncMock,
                ) as mock_chunks:
                    mock_chunk = MagicMock()
                    mock_chunk.document_id = None
                    mock_chunks.return_value = [mock_chunk]

                    with patch(
                        "app.tasks.celery_tasks.document_reindex_tasks.get_user_long_context_llm",
                        new_callable=AsyncMock,
                    ) as mock_llm:
                        mock_llm_instance = MagicMock()
                        mock_llm.return_value = mock_llm_instance

                        with patch(
                            "app.tasks.celery_tasks.document_reindex_tasks.generate_document_summary",
                            new_callable=AsyncMock,
                        ) as mock_summary:
                            mock_summary.return_value = (
                                "Summary content",
                                [0.1, 0.2, 0.3],
                            )

                            await _reindex_document(1, "user1")

                            mock_convert.assert_called_once()
                            mock_chunks.assert_called_once()
                            mock_summary.assert_called_once()
                            mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_reindex_deletes_old_chunks(self):
        """Test that old chunks are deleted during reindex."""
        from app.tasks.celery_tasks.document_reindex_tasks import _reindex_document
        from app.db import DocumentType

        mock_session = AsyncMock()
        mock_document = MagicMock()
        mock_document.id = 1
        mock_document.title = "Test"
        mock_document.blocknote_document = {"type": "doc"}
        mock_document.document_type = DocumentType.FILE
        mock_document.search_space_id = 1

        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = mock_document
        mock_session.execute.return_value = mock_result

        with patch(
            "app.tasks.celery_tasks.document_reindex_tasks.get_celery_session_maker"
        ) as mock_maker:
            mock_context = AsyncMock()
            mock_context.__aenter__.return_value = mock_session
            mock_context.__aexit__.return_value = None
            mock_maker.return_value.return_value = mock_context

            with patch(
                "app.tasks.celery_tasks.document_reindex_tasks.convert_blocknote_to_markdown",
                new_callable=AsyncMock,
            ) as mock_convert:
                mock_convert.return_value = "Content"

                with patch(
                    "app.tasks.celery_tasks.document_reindex_tasks.create_document_chunks",
                    new_callable=AsyncMock,
                ) as mock_chunks:
                    mock_chunks.return_value = []

                    with patch(
                        "app.tasks.celery_tasks.document_reindex_tasks.get_user_long_context_llm",
                        new_callable=AsyncMock,
                    ):
                        with patch(
                            "app.tasks.celery_tasks.document_reindex_tasks.generate_document_summary",
                            new_callable=AsyncMock,
                        ) as mock_summary:
                            mock_summary.return_value = ("Summary", [0.1])

                            await _reindex_document(1, "user1")

                            # Verify delete was called (execute is called for select and delete)
                            assert mock_session.execute.call_count >= 2
                            mock_session.flush.assert_called()

    @pytest.mark.asyncio
    async def test_handles_conversion_failure(self):
        """Test handling markdown conversion failure."""
        from app.tasks.celery_tasks.document_reindex_tasks import _reindex_document

        mock_session = AsyncMock()
        mock_document = MagicMock()
        mock_document.id = 1
        mock_document.title = "Test"
        mock_document.blocknote_document = {"type": "doc"}

        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = mock_document
        mock_session.execute.return_value = mock_result

        with patch(
            "app.tasks.celery_tasks.document_reindex_tasks.get_celery_session_maker"
        ) as mock_maker:
            mock_context = AsyncMock()
            mock_context.__aenter__.return_value = mock_session
            mock_context.__aexit__.return_value = None
            mock_maker.return_value.return_value = mock_context

            with patch(
                "app.tasks.celery_tasks.document_reindex_tasks.convert_blocknote_to_markdown",
                new_callable=AsyncMock,
            ) as mock_convert:
                mock_convert.return_value = None  # Conversion failed

                await _reindex_document(1, "user1")

                mock_session.commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_handles_database_error(self):
        """Test handling database errors during reindex."""
        from app.tasks.celery_tasks.document_reindex_tasks import _reindex_document
        from sqlalchemy.exc import SQLAlchemyError
        from app.db import DocumentType

        mock_session = AsyncMock()
        mock_document = MagicMock()
        mock_document.id = 1
        mock_document.title = "Test"
        mock_document.blocknote_document = {"type": "doc"}
        mock_document.document_type = DocumentType.FILE
        mock_document.search_space_id = 1

        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = mock_document
        mock_session.execute.return_value = mock_result
        mock_session.commit.side_effect = SQLAlchemyError("DB error")

        with patch(
            "app.tasks.celery_tasks.document_reindex_tasks.get_celery_session_maker"
        ) as mock_maker:
            mock_context = AsyncMock()
            mock_context.__aenter__.return_value = mock_session
            mock_context.__aexit__.return_value = None
            mock_maker.return_value.return_value = mock_context

            with patch(
                "app.tasks.celery_tasks.document_reindex_tasks.convert_blocknote_to_markdown",
                new_callable=AsyncMock,
            ) as mock_convert:
                mock_convert.return_value = "Content"

                with patch(
                    "app.tasks.celery_tasks.document_reindex_tasks.create_document_chunks",
                    new_callable=AsyncMock,
                ):
                    with patch(
                        "app.tasks.celery_tasks.document_reindex_tasks.get_user_long_context_llm",
                        new_callable=AsyncMock,
                    ):
                        with patch(
                            "app.tasks.celery_tasks.document_reindex_tasks.generate_document_summary",
                            new_callable=AsyncMock,
                        ) as mock_summary:
                            mock_summary.return_value = ("Summary", [0.1])

                            with pytest.raises(SQLAlchemyError):
                                await _reindex_document(1, "user1")

                            mock_session.rollback.assert_called_once()


# ============================================================================
# CONNECTOR TASKS ADDITIONAL TESTS
# ============================================================================


class TestConnectorTasksGmailDaysBackCalculation:
    """Additional tests for Gmail days_back calculation."""

    @pytest.mark.asyncio
    async def test_gmail_calculates_correct_days_back(self):
        """Test Gmail indexing calculates correct days_back from start_date."""
        from app.tasks.celery_tasks.connector_tasks import _index_google_gmail_messages
        from datetime import datetime, timedelta

        mock_session = AsyncMock()

        # Set start_date to 15 days ago
        start_date = (datetime.now() - timedelta(days=15)).strftime("%Y-%m-%d")

        with patch(
            "app.tasks.celery_tasks.connector_tasks.get_celery_session_maker"
        ) as mock_maker:
            mock_context = AsyncMock()
            mock_context.__aenter__.return_value = mock_session
            mock_context.__aexit__.return_value = None
            mock_maker.return_value.return_value = mock_context

            with patch(
                "app.routes.search_source_connectors_routes.run_google_gmail_indexing",
                new_callable=AsyncMock,
            ) as mock_run:
                await _index_google_gmail_messages(1, 1, "user1", start_date, None)

                mock_run.assert_called_once()
                call_args = mock_run.call_args[0]
                # days_back should be approximately 15
                assert 14 <= call_args[5] <= 16

    @pytest.mark.asyncio
    async def test_gmail_minimum_days_back(self):
        """Test Gmail uses minimum of 1 day when start_date is today."""
        from app.tasks.celery_tasks.connector_tasks import _index_google_gmail_messages
        from datetime import datetime

        mock_session = AsyncMock()

        # Set start_date to today
        start_date = datetime.now().strftime("%Y-%m-%d")

        with patch(
            "app.tasks.celery_tasks.connector_tasks.get_celery_session_maker"
        ) as mock_maker:
            mock_context = AsyncMock()
            mock_context.__aenter__.return_value = mock_session
            mock_context.__aexit__.return_value = None
            mock_maker.return_value.return_value = mock_context

            with patch(
                "app.routes.search_source_connectors_routes.run_google_gmail_indexing",
                new_callable=AsyncMock,
            ) as mock_run:
                await _index_google_gmail_messages(1, 1, "user1", start_date, None)

                mock_run.assert_called_once()
                call_args = mock_run.call_args[0]
                # days_back should be at least 1
                assert call_args[5] >= 1


class TestConnectorTasksErrorHandling:
    """Tests for error handling in connector tasks."""

    @pytest.mark.asyncio
    async def test_slack_task_handles_session_error(self):
        """Test Slack task handles session creation errors."""
        from app.tasks.celery_tasks.connector_tasks import _index_slack_messages

        with patch(
            "app.tasks.celery_tasks.connector_tasks.get_celery_session_maker"
        ) as mock_maker:
            mock_maker.side_effect = Exception("Session creation failed")

            with pytest.raises(Exception, match="Session creation failed"):
                await _index_slack_messages(1, 1, "user1", "2024-01-01", "2024-12-31")

    @pytest.mark.asyncio
    async def test_github_task_handles_indexing_error(self):
        """Test GitHub task handles indexing errors."""
        from app.tasks.celery_tasks.connector_tasks import _index_github_repos

        mock_session = AsyncMock()

        with patch(
            "app.tasks.celery_tasks.connector_tasks.get_celery_session_maker"
        ) as mock_maker:
            mock_context = AsyncMock()
            mock_context.__aenter__.return_value = mock_session
            mock_context.__aexit__.return_value = None
            mock_maker.return_value.return_value = mock_context

            with patch(
                "app.routes.search_source_connectors_routes.run_github_indexing",
                new_callable=AsyncMock,
            ) as mock_run:
                mock_run.side_effect = Exception("GitHub API error")

                with pytest.raises(Exception, match="GitHub API error"):
                    await _index_github_repos(1, 1, "user1", "2024-01-01", "2024-12-31")
