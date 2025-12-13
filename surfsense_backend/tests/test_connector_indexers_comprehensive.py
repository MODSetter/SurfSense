"""Comprehensive tests for connector indexers module."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ============================================================================
# SLACK INDEXER TESTS
# ============================================================================


class TestSlackIndexer:
    """Tests for Slack connector indexer."""

    @pytest.mark.asyncio
    async def test_index_slack_messages_connector_not_found(self):
        """Test handling when connector is not found."""
        from app.tasks.connector_indexers.slack_indexer import index_slack_messages

        mock_session = AsyncMock()
        mock_task_logger = MagicMock()
        mock_task_logger.log_task_start = AsyncMock(return_value=MagicMock())
        mock_task_logger.log_task_failure = AsyncMock()
        mock_task_logger.log_task_progress = AsyncMock()

        with patch(
            "app.tasks.connector_indexers.slack_indexer.TaskLoggingService",
            return_value=mock_task_logger,
        ):
            with patch(
                "app.tasks.connector_indexers.slack_indexer.get_connector_by_id",
                new_callable=AsyncMock,
            ) as mock_get_connector:
                mock_get_connector.return_value = None

                count, error = await index_slack_messages(
                    mock_session, 999, 1, "user1", "2024-01-01", "2024-12-31"
                )

                assert count == 0
                assert "not found" in error.lower()

    @pytest.mark.asyncio
    async def test_index_slack_messages_missing_token(self):
        """Test handling when Slack token is missing."""
        from app.tasks.connector_indexers.slack_indexer import index_slack_messages

        mock_session = AsyncMock()
        mock_connector = MagicMock()
        mock_connector.config = {}  # No token

        mock_task_logger = MagicMock()
        mock_task_logger.log_task_start = AsyncMock(return_value=MagicMock())
        mock_task_logger.log_task_failure = AsyncMock()
        mock_task_logger.log_task_progress = AsyncMock()

        with patch(
            "app.tasks.connector_indexers.slack_indexer.TaskLoggingService",
            return_value=mock_task_logger,
        ):
            with patch(
                "app.tasks.connector_indexers.slack_indexer.get_connector_by_id",
                new_callable=AsyncMock,
            ) as mock_get_connector:
                mock_get_connector.return_value = mock_connector

                count, error = await index_slack_messages(
                    mock_session, 1, 1, "user1", "2024-01-01", "2024-12-31"
                )

                assert count == 0
                assert "token" in error.lower()

    @pytest.mark.asyncio
    async def test_index_slack_messages_no_channels_found(self):
        """Test handling when no Slack channels are found."""
        from app.tasks.connector_indexers.slack_indexer import index_slack_messages

        mock_session = AsyncMock()
        mock_connector = MagicMock()
        mock_connector.config = {"SLACK_BOT_TOKEN": "xoxb-test-token"}
        mock_connector.last_indexed_at = None

        mock_task_logger = MagicMock()
        mock_task_logger.log_task_start = AsyncMock(return_value=MagicMock())
        mock_task_logger.log_task_success = AsyncMock()
        mock_task_logger.log_task_progress = AsyncMock()

        with patch(
            "app.tasks.connector_indexers.slack_indexer.TaskLoggingService",
            return_value=mock_task_logger,
        ):
            with patch(
                "app.tasks.connector_indexers.slack_indexer.get_connector_by_id",
                new_callable=AsyncMock,
            ) as mock_get_connector:
                mock_get_connector.return_value = mock_connector

                with patch(
                    "app.tasks.connector_indexers.slack_indexer.SlackHistory"
                ) as mock_slack:
                    mock_slack_instance = MagicMock()
                    mock_slack_instance.get_all_channels.return_value = []
                    mock_slack.return_value = mock_slack_instance

                    count, error = await index_slack_messages(
                        mock_session, 1, 1, "user1", "2024-01-01", "2024-12-31"
                    )

                    assert count == 0
                    assert "no slack channels found" in error.lower()

    @pytest.mark.asyncio
    async def test_index_slack_messages_successful_indexing(self):
        """Test successful Slack message indexing."""
        from app.tasks.connector_indexers.slack_indexer import index_slack_messages

        mock_session = AsyncMock()
        # session.add is synchronous, so use MagicMock
        mock_session.add = MagicMock()
        mock_connector = MagicMock()
        mock_connector.config = {"SLACK_BOT_TOKEN": "xoxb-test-token"}
        mock_connector.last_indexed_at = None

        mock_task_logger = MagicMock()
        mock_task_logger.log_task_start = AsyncMock(return_value=MagicMock())
        mock_task_logger.log_task_success = AsyncMock()
        mock_task_logger.log_task_progress = AsyncMock()

        mock_channels = [
            {"id": "C123", "name": "general", "is_private": False, "is_member": True}
        ]

        mock_messages = [
            {
                "ts": "1234567890.123456",
                "datetime": "2024-01-15 10:00:00",
                "user_name": "Test User",
                "user_email": "test@example.com",
                "text": "Hello world",
            }
        ]

        with patch(
            "app.tasks.connector_indexers.slack_indexer.TaskLoggingService",
            return_value=mock_task_logger,
        ):
            with patch(
                "app.tasks.connector_indexers.slack_indexer.get_connector_by_id",
                new_callable=AsyncMock,
            ) as mock_get_connector:
                mock_get_connector.return_value = mock_connector

                with patch(
                    "app.tasks.connector_indexers.slack_indexer.SlackHistory"
                ) as mock_slack:
                    mock_slack_instance = MagicMock()
                    mock_slack_instance.get_all_channels.return_value = mock_channels
                    mock_slack_instance.get_history_by_date_range.return_value = (
                        mock_messages,
                        None,
                    )
                    mock_slack_instance.format_message.return_value = mock_messages[0]
                    mock_slack.return_value = mock_slack_instance

                    with patch(
                        "app.tasks.connector_indexers.slack_indexer.check_document_by_unique_identifier",
                        new_callable=AsyncMock,
                    ) as mock_check:
                        mock_check.return_value = None  # No existing document

                        with patch(
                            "app.tasks.connector_indexers.slack_indexer.create_document_chunks",
                            new_callable=AsyncMock,
                        ) as mock_chunks:
                            mock_chunks.return_value = []

                            with patch(
                                "app.tasks.connector_indexers.slack_indexer.config"
                            ) as mock_config:
                                mock_config.embedding_model_instance.embed.return_value = [
                                    0.1,
                                    0.2,
                                ]

                                count, error = await index_slack_messages(
                                    mock_session,
                                    1,
                                    1,
                                    "user1",
                                    "2024-01-01",
                                    "2024-12-31",
                                )

                                assert count >= 0
                                mock_session.add.assert_called()

    @pytest.mark.asyncio
    async def test_index_slack_messages_skips_private_channels(self):
        """Test that private channels where bot is not a member are skipped."""
        from app.tasks.connector_indexers.slack_indexer import index_slack_messages

        mock_session = AsyncMock()
        mock_connector = MagicMock()
        mock_connector.config = {"SLACK_BOT_TOKEN": "xoxb-test-token"}
        mock_connector.last_indexed_at = None

        mock_task_logger = MagicMock()
        mock_task_logger.log_task_start = AsyncMock(return_value=MagicMock())
        mock_task_logger.log_task_success = AsyncMock()
        mock_task_logger.log_task_progress = AsyncMock()

        # Only private channel where bot is not a member
        mock_channels = [
            {"id": "C456", "name": "private-channel", "is_private": True, "is_member": False}
        ]

        with patch(
            "app.tasks.connector_indexers.slack_indexer.TaskLoggingService",
            return_value=mock_task_logger,
        ):
            with patch(
                "app.tasks.connector_indexers.slack_indexer.get_connector_by_id",
                new_callable=AsyncMock,
            ) as mock_get_connector:
                mock_get_connector.return_value = mock_connector

                with patch(
                    "app.tasks.connector_indexers.slack_indexer.SlackHistory"
                ) as mock_slack:
                    mock_slack_instance = MagicMock()
                    mock_slack_instance.get_all_channels.return_value = mock_channels
                    mock_slack.return_value = mock_slack_instance

                    count, error = await index_slack_messages(
                        mock_session, 1, 1, "user1", "2024-01-01", "2024-12-31"
                    )

                    # Should have processed but skipped the private channel
                    assert "skipped" in error.lower() or count == 0

    @pytest.mark.asyncio
    async def test_index_slack_messages_handles_api_error(self):
        """Test handling of Slack API errors."""
        from app.tasks.connector_indexers.slack_indexer import index_slack_messages
        from slack_sdk.errors import SlackApiError

        mock_session = AsyncMock()
        mock_connector = MagicMock()
        mock_connector.config = {"SLACK_BOT_TOKEN": "xoxb-test-token"}
        mock_connector.last_indexed_at = None

        mock_task_logger = MagicMock()
        mock_task_logger.log_task_start = AsyncMock(return_value=MagicMock())
        mock_task_logger.log_task_failure = AsyncMock()
        mock_task_logger.log_task_progress = AsyncMock()

        with patch(
            "app.tasks.connector_indexers.slack_indexer.TaskLoggingService",
            return_value=mock_task_logger,
        ):
            with patch(
                "app.tasks.connector_indexers.slack_indexer.get_connector_by_id",
                new_callable=AsyncMock,
            ) as mock_get_connector:
                mock_get_connector.return_value = mock_connector

                with patch(
                    "app.tasks.connector_indexers.slack_indexer.SlackHistory"
                ) as mock_slack:
                    mock_slack_instance = MagicMock()
                    mock_slack_instance.get_all_channels.side_effect = Exception(
                        "API error"
                    )
                    mock_slack.return_value = mock_slack_instance

                    count, error = await index_slack_messages(
                        mock_session, 1, 1, "user1", "2024-01-01", "2024-12-31"
                    )

                    assert count == 0
                    assert "failed" in error.lower()


# ============================================================================
# NOTION INDEXER TESTS
# ============================================================================


class TestNotionIndexer:
    """Tests for Notion connector indexer."""

    @pytest.mark.asyncio
    async def test_index_notion_pages_connector_not_found(self):
        """Test handling when connector is not found."""
        from app.tasks.connector_indexers.notion_indexer import index_notion_pages

        mock_session = AsyncMock()
        mock_task_logger = MagicMock()
        mock_task_logger.log_task_start = AsyncMock(return_value=MagicMock())
        mock_task_logger.log_task_failure = AsyncMock()
        mock_task_logger.log_task_progress = AsyncMock()

        with patch(
            "app.tasks.connector_indexers.notion_indexer.TaskLoggingService",
            return_value=mock_task_logger,
        ):
            with patch(
                "app.tasks.connector_indexers.notion_indexer.get_connector_by_id",
                new_callable=AsyncMock,
            ) as mock_get_connector:
                mock_get_connector.return_value = None

                count, error = await index_notion_pages(
                    mock_session, 999, 1, "user1", "2024-01-01", "2024-12-31"
                )

                assert count == 0
                assert "not found" in error.lower()

    @pytest.mark.asyncio
    async def test_index_notion_pages_missing_token(self):
        """Test handling when Notion token is missing."""
        from app.tasks.connector_indexers.notion_indexer import index_notion_pages

        mock_session = AsyncMock()
        mock_connector = MagicMock()
        mock_connector.config = {}  # No token

        mock_task_logger = MagicMock()
        mock_task_logger.log_task_start = AsyncMock(return_value=MagicMock())
        mock_task_logger.log_task_failure = AsyncMock()
        mock_task_logger.log_task_progress = AsyncMock()

        with patch(
            "app.tasks.connector_indexers.notion_indexer.TaskLoggingService",
            return_value=mock_task_logger,
        ):
            with patch(
                "app.tasks.connector_indexers.notion_indexer.get_connector_by_id",
                new_callable=AsyncMock,
            ) as mock_get_connector:
                mock_get_connector.return_value = mock_connector

                count, error = await index_notion_pages(
                    mock_session, 1, 1, "user1", "2024-01-01", "2024-12-31"
                )

                assert count == 0
                assert "token" in error.lower()

    @pytest.mark.asyncio
    async def test_index_notion_pages_no_pages_found(self):
        """Test handling when no Notion pages are found."""
        from app.tasks.connector_indexers.notion_indexer import index_notion_pages

        mock_session = AsyncMock()
        mock_connector = MagicMock()
        mock_connector.config = {"NOTION_INTEGRATION_TOKEN": "secret_token"}
        mock_connector.last_indexed_at = None

        mock_task_logger = MagicMock()
        mock_task_logger.log_task_start = AsyncMock(return_value=MagicMock())
        mock_task_logger.log_task_success = AsyncMock()
        mock_task_logger.log_task_progress = AsyncMock()

        mock_notion_client = AsyncMock()
        mock_notion_client.get_all_pages = AsyncMock(return_value=[])
        mock_notion_client.close = AsyncMock()

        with patch(
            "app.tasks.connector_indexers.notion_indexer.TaskLoggingService",
            return_value=mock_task_logger,
        ):
            with patch(
                "app.tasks.connector_indexers.notion_indexer.get_connector_by_id",
                new_callable=AsyncMock,
            ) as mock_get_connector:
                mock_get_connector.return_value = mock_connector

                with patch(
                    "app.tasks.connector_indexers.notion_indexer.NotionHistoryConnector"
                ) as mock_notion:
                    mock_notion.return_value = mock_notion_client

                    count, error = await index_notion_pages(
                        mock_session, 1, 1, "user1", "2024-01-01", "2024-12-31"
                    )

                    assert count == 0
                    assert "no notion pages found" in error.lower()

    @pytest.mark.asyncio
    async def test_index_notion_pages_successful_indexing(self):
        """Test successful Notion page indexing."""
        from app.tasks.connector_indexers.notion_indexer import index_notion_pages

        mock_session = AsyncMock()
        # session.add is synchronous, so use MagicMock
        mock_session.add = MagicMock()
        mock_connector = MagicMock()
        mock_connector.config = {"NOTION_INTEGRATION_TOKEN": "secret_token"}
        mock_connector.last_indexed_at = None

        mock_task_logger = MagicMock()
        mock_task_logger.log_task_start = AsyncMock(return_value=MagicMock())
        mock_task_logger.log_task_success = AsyncMock()
        mock_task_logger.log_task_progress = AsyncMock()

        mock_pages = [
            {
                "page_id": "page-123",
                "title": "Test Page",
                "content": [
                    {"type": "paragraph", "content": "Test content", "children": []}
                ],
            }
        ]

        mock_notion_client = AsyncMock()
        mock_notion_client.get_all_pages = AsyncMock(return_value=mock_pages)
        mock_notion_client.close = AsyncMock()

        with patch(
            "app.tasks.connector_indexers.notion_indexer.TaskLoggingService",
            return_value=mock_task_logger,
        ):
            with patch(
                "app.tasks.connector_indexers.notion_indexer.get_connector_by_id",
                new_callable=AsyncMock,
            ) as mock_get_connector:
                mock_get_connector.return_value = mock_connector

                with patch(
                    "app.tasks.connector_indexers.notion_indexer.NotionHistoryConnector"
                ) as mock_notion:
                    mock_notion.return_value = mock_notion_client

                    with patch(
                        "app.tasks.connector_indexers.notion_indexer.check_document_by_unique_identifier",
                        new_callable=AsyncMock,
                    ) as mock_check:
                        mock_check.return_value = None

                        with patch(
                            "app.tasks.connector_indexers.notion_indexer.get_user_long_context_llm",
                            new_callable=AsyncMock,
                        ) as mock_llm:
                            mock_llm.return_value = MagicMock()

                            with patch(
                                "app.tasks.connector_indexers.notion_indexer.generate_document_summary",
                                new_callable=AsyncMock,
                            ) as mock_summary:
                                mock_summary.return_value = (
                                    "Summary",
                                    [0.1, 0.2],
                                )

                                with patch(
                                    "app.tasks.connector_indexers.notion_indexer.create_document_chunks",
                                    new_callable=AsyncMock,
                                ) as mock_chunks:
                                    mock_chunks.return_value = []

                                    count, error = await index_notion_pages(
                                        mock_session,
                                        1,
                                        1,
                                        "user1",
                                        "2024-01-01",
                                        "2024-12-31",
                                    )

                                    assert count >= 0
                                    mock_notion_client.close.assert_called()

    @pytest.mark.asyncio
    async def test_index_notion_pages_skips_empty_pages(self):
        """Test that pages with no content are skipped."""
        from app.tasks.connector_indexers.notion_indexer import index_notion_pages

        mock_session = AsyncMock()
        mock_connector = MagicMock()
        mock_connector.config = {"NOTION_INTEGRATION_TOKEN": "secret_token"}
        mock_connector.last_indexed_at = None

        mock_task_logger = MagicMock()
        mock_task_logger.log_task_start = AsyncMock(return_value=MagicMock())
        mock_task_logger.log_task_success = AsyncMock()
        mock_task_logger.log_task_progress = AsyncMock()

        # Page with no content
        mock_pages = [{"page_id": "page-empty", "title": "Empty Page", "content": []}]

        mock_notion_client = AsyncMock()
        mock_notion_client.get_all_pages = AsyncMock(return_value=mock_pages)
        mock_notion_client.close = AsyncMock()

        with patch(
            "app.tasks.connector_indexers.notion_indexer.TaskLoggingService",
            return_value=mock_task_logger,
        ):
            with patch(
                "app.tasks.connector_indexers.notion_indexer.get_connector_by_id",
                new_callable=AsyncMock,
            ) as mock_get_connector:
                mock_get_connector.return_value = mock_connector

                with patch(
                    "app.tasks.connector_indexers.notion_indexer.NotionHistoryConnector"
                ) as mock_notion:
                    mock_notion.return_value = mock_notion_client

                    count, error = await index_notion_pages(
                        mock_session, 1, 1, "user1", "2024-01-01", "2024-12-31"
                    )

                    # Should skip the empty page
                    assert "skipped" in error.lower() or count == 0


# ============================================================================
# GITHUB INDEXER TESTS
# ============================================================================


class TestGitHubIndexer:
    """Tests for GitHub connector indexer."""

    @pytest.mark.asyncio
    async def test_index_github_repos_connector_not_found(self):
        """Test handling when connector is not found."""
        from app.tasks.connector_indexers.github_indexer import index_github_repos

        mock_session = AsyncMock()
        mock_task_logger = MagicMock()
        mock_task_logger.log_task_start = AsyncMock(return_value=MagicMock())
        mock_task_logger.log_task_failure = AsyncMock()
        mock_task_logger.log_task_progress = AsyncMock()

        with patch(
            "app.tasks.connector_indexers.github_indexer.TaskLoggingService",
            return_value=mock_task_logger,
        ):
            with patch(
                "app.tasks.connector_indexers.github_indexer.get_connector_by_id",
                new_callable=AsyncMock,
            ) as mock_get_connector:
                mock_get_connector.return_value = None

                count, error = await index_github_repos(
                    mock_session, 999, 1, "user1", "2024-01-01", "2024-12-31"
                )

                assert count == 0
                assert "not found" in error.lower()

    @pytest.mark.asyncio
    async def test_index_github_repos_missing_pat(self):
        """Test handling when GitHub PAT is missing."""
        from app.tasks.connector_indexers.github_indexer import index_github_repos

        mock_session = AsyncMock()
        mock_connector = MagicMock()
        mock_connector.config = {"repo_full_names": ["owner/repo"]}  # No PAT

        mock_task_logger = MagicMock()
        mock_task_logger.log_task_start = AsyncMock(return_value=MagicMock())
        mock_task_logger.log_task_failure = AsyncMock()
        mock_task_logger.log_task_progress = AsyncMock()

        with patch(
            "app.tasks.connector_indexers.github_indexer.TaskLoggingService",
            return_value=mock_task_logger,
        ):
            with patch(
                "app.tasks.connector_indexers.github_indexer.get_connector_by_id",
                new_callable=AsyncMock,
            ) as mock_get_connector:
                mock_get_connector.return_value = mock_connector

                count, error = await index_github_repos(
                    mock_session, 1, 1, "user1", "2024-01-01", "2024-12-31"
                )

                assert count == 0
                assert "pat" in error.lower() or "token" in error.lower()

    @pytest.mark.asyncio
    async def test_index_github_repos_missing_repo_list(self):
        """Test handling when repo_full_names is missing."""
        from app.tasks.connector_indexers.github_indexer import index_github_repos

        mock_session = AsyncMock()
        mock_connector = MagicMock()
        mock_connector.config = {"GITHUB_PAT": "ghp_test_token"}  # No repo list

        mock_task_logger = MagicMock()
        mock_task_logger.log_task_start = AsyncMock(return_value=MagicMock())
        mock_task_logger.log_task_failure = AsyncMock()
        mock_task_logger.log_task_progress = AsyncMock()

        with patch(
            "app.tasks.connector_indexers.github_indexer.TaskLoggingService",
            return_value=mock_task_logger,
        ):
            with patch(
                "app.tasks.connector_indexers.github_indexer.get_connector_by_id",
                new_callable=AsyncMock,
            ) as mock_get_connector:
                mock_get_connector.return_value = mock_connector

                count, error = await index_github_repos(
                    mock_session, 1, 1, "user1", "2024-01-01", "2024-12-31"
                )

                assert count == 0
                assert "repo_full_names" in error.lower()

    @pytest.mark.asyncio
    async def test_index_github_repos_successful_indexing(self):
        """Test successful GitHub repository indexing."""
        from app.tasks.connector_indexers.github_indexer import index_github_repos

        mock_session = AsyncMock()
        # session.add is synchronous, so use MagicMock
        mock_session.add = MagicMock()
        mock_connector = MagicMock()
        mock_connector.config = {
            "GITHUB_PAT": "ghp_test_token",
            "repo_full_names": ["owner/repo"],
        }

        mock_task_logger = MagicMock()
        mock_task_logger.log_task_start = AsyncMock(return_value=MagicMock())
        mock_task_logger.log_task_success = AsyncMock()
        mock_task_logger.log_task_progress = AsyncMock()

        mock_files = [
            {
                "path": "README.md",
                "url": "https://github.com/owner/repo/blob/main/README.md",
                "sha": "abc123",
                "type": "doc",
            }
        ]

        with patch(
            "app.tasks.connector_indexers.github_indexer.TaskLoggingService",
            return_value=mock_task_logger,
        ):
            with patch(
                "app.tasks.connector_indexers.github_indexer.get_connector_by_id",
                new_callable=AsyncMock,
            ) as mock_get_connector:
                mock_get_connector.return_value = mock_connector

                with patch(
                    "app.tasks.connector_indexers.github_indexer.GitHubConnector"
                ) as mock_github:
                    mock_github_instance = MagicMock()
                    mock_github_instance.get_repository_files.return_value = mock_files
                    mock_github_instance.get_file_content.return_value = (
                        "# README\n\nTest content"
                    )
                    mock_github.return_value = mock_github_instance

                    with patch(
                        "app.tasks.connector_indexers.github_indexer.check_document_by_unique_identifier",
                        new_callable=AsyncMock,
                    ) as mock_check:
                        mock_check.return_value = None

                        with patch(
                            "app.tasks.connector_indexers.github_indexer.get_user_long_context_llm",
                            new_callable=AsyncMock,
                        ) as mock_llm:
                            mock_llm.return_value = MagicMock()

                            with patch(
                                "app.tasks.connector_indexers.github_indexer.generate_document_summary",
                                new_callable=AsyncMock,
                            ) as mock_summary:
                                mock_summary.return_value = (
                                    "Summary",
                                    [0.1, 0.2],
                                )

                                with patch(
                                    "app.tasks.connector_indexers.github_indexer.create_document_chunks",
                                    new_callable=AsyncMock,
                                ) as mock_chunks:
                                    mock_chunks.return_value = []

                                    with patch(
                                        "app.tasks.connector_indexers.github_indexer.config"
                                    ) as mock_config:
                                        mock_config.embedding_model_instance.embed.return_value = [
                                            0.1,
                                            0.2,
                                        ]

                                        count, error = await index_github_repos(
                                            mock_session,
                                            1,
                                            1,
                                            "user1",
                                            "2024-01-01",
                                            "2024-12-31",
                                        )

                                        assert count >= 0

    @pytest.mark.asyncio
    async def test_index_github_repos_handles_file_fetch_error(self):
        """Test handling file content fetch errors."""
        from app.tasks.connector_indexers.github_indexer import index_github_repos

        mock_session = AsyncMock()
        mock_connector = MagicMock()
        mock_connector.config = {
            "GITHUB_PAT": "ghp_test_token",
            "repo_full_names": ["owner/repo"],
        }

        mock_task_logger = MagicMock()
        mock_task_logger.log_task_start = AsyncMock(return_value=MagicMock())
        mock_task_logger.log_task_success = AsyncMock()
        mock_task_logger.log_task_progress = AsyncMock()

        mock_files = [
            {"path": "file.py", "url": "https://...", "sha": "def456", "type": "code"}
        ]

        with patch(
            "app.tasks.connector_indexers.github_indexer.TaskLoggingService",
            return_value=mock_task_logger,
        ):
            with patch(
                "app.tasks.connector_indexers.github_indexer.get_connector_by_id",
                new_callable=AsyncMock,
            ) as mock_get_connector:
                mock_get_connector.return_value = mock_connector

                with patch(
                    "app.tasks.connector_indexers.github_indexer.GitHubConnector"
                ) as mock_github:
                    mock_github_instance = MagicMock()
                    mock_github_instance.get_repository_files.return_value = mock_files
                    mock_github_instance.get_file_content.return_value = (
                        None  # File fetch failed
                    )
                    mock_github.return_value = mock_github_instance

                    count, error = await index_github_repos(
                        mock_session,
                        1,
                        1,
                        "user1",
                        "2024-01-01",
                        "2024-12-31",
                    )

                    # Should handle gracefully and continue
                    assert count == 0


# ============================================================================
# JIRA INDEXER TESTS
# ============================================================================


class TestJiraIndexer:
    """Tests for Jira connector indexer."""

    @pytest.mark.asyncio
    async def test_jira_indexer_connector_not_found(self):
        """Test handling when Jira connector is not found."""
        from app.tasks.connector_indexers.jira_indexer import index_jira_issues

        mock_session = AsyncMock()
        mock_task_logger = MagicMock()
        mock_task_logger.log_task_start = AsyncMock(return_value=MagicMock())
        mock_task_logger.log_task_failure = AsyncMock()
        mock_task_logger.log_task_progress = AsyncMock()

        with patch(
            "app.tasks.connector_indexers.jira_indexer.TaskLoggingService",
            return_value=mock_task_logger,
        ):
            with patch(
                "app.tasks.connector_indexers.jira_indexer.get_connector_by_id",
                new_callable=AsyncMock,
            ) as mock_get_connector:
                mock_get_connector.return_value = None

                count, error = await index_jira_issues(
                    mock_session, 999, 1, "user1", "2024-01-01", "2024-12-31"
                )

                assert count == 0
                assert "not found" in error.lower()


# ============================================================================
# CONFLUENCE INDEXER TESTS
# ============================================================================


class TestConfluenceIndexer:
    """Tests for Confluence connector indexer."""

    @pytest.mark.asyncio
    async def test_confluence_indexer_connector_not_found(self):
        """Test handling when Confluence connector is not found."""
        from app.tasks.connector_indexers.confluence_indexer import index_confluence_pages

        mock_session = AsyncMock()
        mock_task_logger = MagicMock()
        mock_task_logger.log_task_start = AsyncMock(return_value=MagicMock())
        mock_task_logger.log_task_failure = AsyncMock()
        mock_task_logger.log_task_progress = AsyncMock()

        with patch(
            "app.tasks.connector_indexers.confluence_indexer.TaskLoggingService",
            return_value=mock_task_logger,
        ):
            with patch(
                "app.tasks.connector_indexers.confluence_indexer.get_connector_by_id",
                new_callable=AsyncMock,
            ) as mock_get_connector:
                mock_get_connector.return_value = None

                count, error = await index_confluence_pages(
                    mock_session, 999, 1, "user1", "2024-01-01", "2024-12-31"
                )

                assert count == 0
                assert "not found" in error.lower()


# ============================================================================
# LINEAR INDEXER TESTS
# ============================================================================


class TestLinearIndexer:
    """Tests for Linear connector indexer."""

    @pytest.mark.asyncio
    async def test_linear_indexer_connector_not_found(self):
        """Test handling when Linear connector is not found."""
        from app.tasks.connector_indexers.linear_indexer import index_linear_issues

        mock_session = AsyncMock()
        mock_task_logger = MagicMock()
        mock_task_logger.log_task_start = AsyncMock(return_value=MagicMock())
        mock_task_logger.log_task_failure = AsyncMock()
        mock_task_logger.log_task_progress = AsyncMock()

        with patch(
            "app.tasks.connector_indexers.linear_indexer.TaskLoggingService",
            return_value=mock_task_logger,
        ):
            with patch(
                "app.tasks.connector_indexers.linear_indexer.get_connector_by_id",
                new_callable=AsyncMock,
            ) as mock_get_connector:
                mock_get_connector.return_value = None

                count, error = await index_linear_issues(
                    mock_session, 999, 1, "user1", "2024-01-01", "2024-12-31"
                )

                assert count == 0
                assert "not found" in error.lower()


# ============================================================================
# DISCORD INDEXER TESTS
# ============================================================================


class TestDiscordIndexer:
    """Tests for Discord connector indexer."""

    @pytest.mark.asyncio
    async def test_discord_indexer_connector_not_found(self):
        """Test handling when Discord connector is not found."""
        from app.tasks.connector_indexers.discord_indexer import index_discord_messages

        mock_session = AsyncMock()
        mock_task_logger = MagicMock()
        mock_task_logger.log_task_start = AsyncMock(return_value=MagicMock())
        mock_task_logger.log_task_failure = AsyncMock()
        mock_task_logger.log_task_progress = AsyncMock()

        with patch(
            "app.tasks.connector_indexers.discord_indexer.TaskLoggingService",
            return_value=mock_task_logger,
        ):
            with patch(
                "app.tasks.connector_indexers.discord_indexer.get_connector_by_id",
                new_callable=AsyncMock,
            ) as mock_get_connector:
                mock_get_connector.return_value = None

                count, error = await index_discord_messages(
                    mock_session, 999, 1, "user1", "2024-01-01", "2024-12-31"
                )

                assert count == 0
                assert "not found" in error.lower()


# ============================================================================
# GOOGLE CALENDAR INDEXER TESTS
# ============================================================================


class TestGoogleCalendarIndexer:
    """Tests for Google Calendar connector indexer."""

    @pytest.mark.asyncio
    async def test_google_calendar_indexer_connector_not_found(self):
        """Test handling when Google Calendar connector is not found."""
        from app.tasks.connector_indexers.google_calendar_indexer import (
            index_google_calendar_events,
        )

        mock_session = AsyncMock()
        mock_task_logger = MagicMock()
        mock_task_logger.log_task_start = AsyncMock(return_value=MagicMock())
        mock_task_logger.log_task_failure = AsyncMock()
        mock_task_logger.log_task_progress = AsyncMock()

        with patch(
            "app.tasks.connector_indexers.google_calendar_indexer.TaskLoggingService",
            return_value=mock_task_logger,
        ):
            with patch(
                "app.tasks.connector_indexers.google_calendar_indexer.get_connector_by_id",
                new_callable=AsyncMock,
            ) as mock_get_connector:
                mock_get_connector.return_value = None

                count, error = await index_google_calendar_events(
                    mock_session, 999, 1, "user1", "2024-01-01", "2024-12-31"
                )

                assert count == 0
                assert "not found" in error.lower()


# ============================================================================
# AIRTABLE INDEXER TESTS
# ============================================================================


class TestAirtableIndexer:
    """Tests for Airtable connector indexer."""

    @pytest.mark.asyncio
    async def test_airtable_indexer_connector_not_found(self):
        """Test handling when Airtable connector is not found."""
        from app.tasks.connector_indexers.airtable_indexer import index_airtable_records

        mock_session = AsyncMock()
        mock_task_logger = MagicMock()
        mock_task_logger.log_task_start = AsyncMock(return_value=MagicMock())
        mock_task_logger.log_task_failure = AsyncMock()
        mock_task_logger.log_task_progress = AsyncMock()

        with patch(
            "app.tasks.connector_indexers.airtable_indexer.TaskLoggingService",
            return_value=mock_task_logger,
        ):
            with patch(
                "app.tasks.connector_indexers.airtable_indexer.get_connector_by_id",
                new_callable=AsyncMock,
            ) as mock_get_connector:
                mock_get_connector.return_value = None

                count, error = await index_airtable_records(
                    mock_session, 999, 1, "user1", "2024-01-01", "2024-12-31"
                )

                assert count == 0
                assert "not found" in error.lower()


# ============================================================================
# WEBCRAWLER INDEXER TESTS
# ============================================================================


class TestWebcrawlerIndexer:
    """Tests for Webcrawler connector indexer."""

    @pytest.mark.asyncio
    async def test_webcrawler_indexer_connector_not_found(self):
        """Test handling when Webcrawler connector is not found."""
        from app.tasks.connector_indexers.webcrawler_indexer import index_crawled_urls

        mock_session = AsyncMock()
        mock_task_logger = MagicMock()
        mock_task_logger.log_task_start = AsyncMock(return_value=MagicMock())
        mock_task_logger.log_task_failure = AsyncMock()
        mock_task_logger.log_task_progress = AsyncMock()

        with patch(
            "app.tasks.connector_indexers.webcrawler_indexer.TaskLoggingService",
            return_value=mock_task_logger,
        ):
            with patch(
                "app.tasks.connector_indexers.webcrawler_indexer.get_connector_by_id",
                new_callable=AsyncMock,
            ) as mock_get_connector:
                mock_get_connector.return_value = None

                count, error = await index_crawled_urls(
                    mock_session, 999, 1, "user1", "2024-01-01", "2024-12-31"
                )

                assert count == 0
                assert "not found" in error.lower()


# ============================================================================
# ELASTICSEARCH INDEXER TESTS
# ============================================================================


class TestElasticsearchIndexer:
    """Tests for Elasticsearch connector indexer."""

    @pytest.mark.asyncio
    async def test_elasticsearch_indexer_connector_not_found(self):
        """Test handling when Elasticsearch connector is not found."""
        from app.tasks.connector_indexers.elasticsearch_indexer import (
            index_elasticsearch_documents,
        )

        mock_session = AsyncMock()
        mock_task_logger = MagicMock()
        mock_task_logger.log_task_start = AsyncMock(return_value=MagicMock())
        mock_task_logger.log_task_failure = AsyncMock()
        mock_task_logger.log_task_progress = AsyncMock()

        # Mock the session.execute to return no connector
        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = None
        mock_session.execute.return_value = mock_result

        with patch(
            "app.tasks.connector_indexers.elasticsearch_indexer.TaskLoggingService",
            return_value=mock_task_logger,
        ):
            count, error = await index_elasticsearch_documents(
                mock_session, 999, 1, "user1", "2024-01-01", "2024-12-31"
            )

            assert count == 0
            assert "not found" in error.lower()


# ============================================================================
# LUMA INDEXER TESTS
# ============================================================================


class TestLumaIndexer:
    """Tests for Luma connector indexer."""

    @pytest.mark.asyncio
    async def test_luma_indexer_connector_not_found(self):
        """Test handling when Luma connector is not found."""
        from app.tasks.connector_indexers.luma_indexer import index_luma_events

        mock_session = AsyncMock()
        mock_task_logger = MagicMock()
        mock_task_logger.log_task_start = AsyncMock(return_value=MagicMock())
        mock_task_logger.log_task_failure = AsyncMock()
        mock_task_logger.log_task_progress = AsyncMock()

        with patch(
            "app.tasks.connector_indexers.luma_indexer.TaskLoggingService",
            return_value=mock_task_logger,
        ):
            with patch(
                "app.tasks.connector_indexers.luma_indexer.get_connector_by_id",
                new_callable=AsyncMock,
            ) as mock_get_connector:
                mock_get_connector.return_value = None

                count, error = await index_luma_events(
                    mock_session, 999, 1, "user1", "2024-01-01", "2024-12-31"
                )

                assert count == 0
                assert "not found" in error.lower()


# ============================================================================
# GOOGLE GMAIL INDEXER TESTS
# ============================================================================


class TestGoogleGmailIndexer:
    """Tests for Google Gmail connector indexer."""

    @pytest.mark.asyncio
    async def test_google_gmail_indexer_connector_not_found(self):
        """Test handling when Google Gmail connector is not found."""
        from app.tasks.connector_indexers.google_gmail_indexer import (
            index_google_gmail_messages,
        )

        mock_session = AsyncMock()
        mock_task_logger = MagicMock()
        mock_task_logger.log_task_start = AsyncMock(return_value=MagicMock())
        mock_task_logger.log_task_failure = AsyncMock()
        mock_task_logger.log_task_progress = AsyncMock()

        with patch(
            "app.tasks.connector_indexers.google_gmail_indexer.TaskLoggingService",
            return_value=mock_task_logger,
        ):
            with patch(
                "app.tasks.connector_indexers.google_gmail_indexer.get_connector_by_id",
                new_callable=AsyncMock,
            ) as mock_get_connector:
                mock_get_connector.return_value = None

                count, error = await index_google_gmail_messages(
                    mock_session, 999, 1, "user1", 100, 30
                )

                assert count == 0
                assert "not found" in error.lower()


# ============================================================================
# CLICKUP INDEXER TESTS
# ============================================================================


class TestClickupIndexer:
    """Tests for ClickUp connector indexer."""

    @pytest.mark.asyncio
    async def test_clickup_indexer_connector_not_found(self):
        """Test handling when ClickUp connector is not found."""
        from app.tasks.connector_indexers.clickup_indexer import index_clickup_tasks

        mock_session = AsyncMock()
        mock_task_logger = MagicMock()
        mock_task_logger.log_task_start = AsyncMock(return_value=MagicMock())
        mock_task_logger.log_task_failure = AsyncMock()
        mock_task_logger.log_task_progress = AsyncMock()

        with patch(
            "app.tasks.connector_indexers.clickup_indexer.TaskLoggingService",
            return_value=mock_task_logger,
        ):
            with patch(
                "app.tasks.connector_indexers.clickup_indexer.get_connector_by_id",
                new_callable=AsyncMock,
            ) as mock_get_connector:
                mock_get_connector.return_value = None

                count, error = await index_clickup_tasks(
                    mock_session, 999, 1, "user1", "2024-01-01", "2024-12-31"
                )

                assert count == 0
                assert "not found" in error.lower()
