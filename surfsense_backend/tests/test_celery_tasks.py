"""Tests for Celery tasks module."""

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.tasks.celery_tasks.connector_tasks import (
    get_celery_session_maker,
    _index_slack_messages,
    _index_notion_pages,
    _index_github_repos,
    _index_linear_issues,
    _index_jira_issues,
    _index_confluence_pages,
    _index_clickup_tasks,
    _index_google_calendar_events,
    _index_airtable_records,
    _index_google_gmail_messages,
    _index_discord_messages,
    _index_luma_events,
    _index_elasticsearch_documents,
    _index_crawled_urls,
)


class TestGetCelerySessionMaker:
    """Tests for get_celery_session_maker function."""

    def test_returns_session_maker(self):
        """Test that get_celery_session_maker returns a session maker."""
        with patch("app.tasks.celery_tasks.connector_tasks.create_async_engine") as mock_engine:
            with patch("app.tasks.celery_tasks.connector_tasks.async_sessionmaker") as mock_session_maker:
                mock_engine.return_value = MagicMock()
                mock_session_maker.return_value = MagicMock()
                
                result = get_celery_session_maker()
                
                assert result is not None
                mock_engine.assert_called_once()
                mock_session_maker.assert_called_once()

    def test_uses_null_pool(self):
        """Test that NullPool is used for Celery tasks."""
        from sqlalchemy.pool import NullPool
        
        with patch("app.tasks.celery_tasks.connector_tasks.create_async_engine") as mock_engine:
            with patch("app.tasks.celery_tasks.connector_tasks.async_sessionmaker"):
                get_celery_session_maker()
                
                # Check that NullPool was passed
                call_kwargs = mock_engine.call_args[1]
                assert call_kwargs.get("poolclass") == NullPool


class TestIndexSlackMessages:
    """Tests for Slack message indexing task."""

    @pytest.mark.asyncio
    async def test_index_slack_messages_calls_run_slack_indexing(self):
        """Test that _index_slack_messages calls run_slack_indexing."""
        mock_session = AsyncMock()
        mock_run_indexing = AsyncMock()
        
        with patch("app.tasks.celery_tasks.connector_tasks.get_celery_session_maker") as mock_maker:
            # Create a mock context manager
            mock_context = AsyncMock()
            mock_context.__aenter__.return_value = mock_session
            mock_context.__aexit__.return_value = None
            mock_maker.return_value.return_value = mock_context
            
            with patch("app.routes.search_source_connectors_routes.run_slack_indexing", mock_run_indexing):
                await _index_slack_messages(1, 1, "user1", "2024-01-01", "2024-12-31")


class TestIndexNotionPages:
    """Tests for Notion page indexing task."""

    @pytest.mark.asyncio
    async def test_index_notion_pages_calls_correct_function(self):
        """Test that _index_notion_pages calls run_notion_indexing."""
        mock_session = AsyncMock()
        
        with patch("app.tasks.celery_tasks.connector_tasks.get_celery_session_maker") as mock_maker:
            mock_context = AsyncMock()
            mock_context.__aenter__.return_value = mock_session
            mock_context.__aexit__.return_value = None
            mock_maker.return_value.return_value = mock_context
            
            with patch("app.routes.search_source_connectors_routes.run_notion_indexing", new_callable=AsyncMock) as mock_run:
                await _index_notion_pages(1, 1, "user1", "2024-01-01", "2024-12-31")


class TestIndexGithubRepos:
    """Tests for GitHub repository indexing task."""

    @pytest.mark.asyncio
    async def test_index_github_repos_with_valid_params(self):
        """Test GitHub repo indexing with valid parameters."""
        mock_session = AsyncMock()
        
        with patch("app.tasks.celery_tasks.connector_tasks.get_celery_session_maker") as mock_maker:
            mock_context = AsyncMock()
            mock_context.__aenter__.return_value = mock_session
            mock_context.__aexit__.return_value = None
            mock_maker.return_value.return_value = mock_context
            
            with patch("app.routes.search_source_connectors_routes.run_github_indexing", new_callable=AsyncMock):
                await _index_github_repos(1, 1, "user1", "2024-01-01", "2024-12-31")


class TestIndexLinearIssues:
    """Tests for Linear issues indexing task."""

    @pytest.mark.asyncio
    async def test_index_linear_issues_creates_session(self):
        """Test that Linear indexing creates a proper session."""
        mock_session = AsyncMock()
        
        with patch("app.tasks.celery_tasks.connector_tasks.get_celery_session_maker") as mock_maker:
            mock_context = AsyncMock()
            mock_context.__aenter__.return_value = mock_session
            mock_context.__aexit__.return_value = None
            mock_maker.return_value.return_value = mock_context
            
            with patch("app.routes.search_source_connectors_routes.run_linear_indexing", new_callable=AsyncMock):
                await _index_linear_issues(1, 1, "user1", "2024-01-01", "2024-12-31")


class TestIndexJiraIssues:
    """Tests for Jira issues indexing task."""

    @pytest.mark.asyncio
    async def test_index_jira_issues_passes_correct_params(self):
        """Test that Jira indexing passes correct parameters."""
        mock_session = AsyncMock()
        
        with patch("app.tasks.celery_tasks.connector_tasks.get_celery_session_maker") as mock_maker:
            mock_context = AsyncMock()
            mock_context.__aenter__.return_value = mock_session
            mock_context.__aexit__.return_value = None
            mock_maker.return_value.return_value = mock_context
            
            with patch("app.routes.search_source_connectors_routes.run_jira_indexing", new_callable=AsyncMock) as mock_run:
                await _index_jira_issues(5, 10, "user123", "2024-06-01", "2024-06-30")
                mock_run.assert_called_once_with(
                    mock_session, 5, 10, "user123", "2024-06-01", "2024-06-30"
                )


class TestIndexConfluencePages:
    """Tests for Confluence pages indexing task."""

    @pytest.mark.asyncio
    async def test_index_confluence_pages_with_valid_params(self):
        """Test Confluence indexing with valid parameters."""
        mock_session = AsyncMock()
        
        with patch("app.tasks.celery_tasks.connector_tasks.get_celery_session_maker") as mock_maker:
            mock_context = AsyncMock()
            mock_context.__aenter__.return_value = mock_session
            mock_context.__aexit__.return_value = None
            mock_maker.return_value.return_value = mock_context
            
            with patch("app.routes.search_source_connectors_routes.run_confluence_indexing", new_callable=AsyncMock):
                await _index_confluence_pages(1, 1, "user1", "2024-01-01", "2024-12-31")


class TestIndexClickupTasks:
    """Tests for ClickUp tasks indexing."""

    @pytest.mark.asyncio
    async def test_index_clickup_tasks_creates_session(self):
        """Test ClickUp indexing creates session."""
        mock_session = AsyncMock()
        
        with patch("app.tasks.celery_tasks.connector_tasks.get_celery_session_maker") as mock_maker:
            mock_context = AsyncMock()
            mock_context.__aenter__.return_value = mock_session
            mock_context.__aexit__.return_value = None
            mock_maker.return_value.return_value = mock_context
            
            with patch("app.routes.search_source_connectors_routes.run_clickup_indexing", new_callable=AsyncMock):
                await _index_clickup_tasks(1, 1, "user1", "2024-01-01", "2024-12-31")


class TestIndexGoogleCalendarEvents:
    """Tests for Google Calendar events indexing."""

    @pytest.mark.asyncio
    async def test_index_google_calendar_events_with_valid_params(self):
        """Test Google Calendar indexing with valid parameters."""
        mock_session = AsyncMock()
        
        with patch("app.tasks.celery_tasks.connector_tasks.get_celery_session_maker") as mock_maker:
            mock_context = AsyncMock()
            mock_context.__aenter__.return_value = mock_session
            mock_context.__aexit__.return_value = None
            mock_maker.return_value.return_value = mock_context
            
            with patch("app.routes.search_source_connectors_routes.run_google_calendar_indexing", new_callable=AsyncMock):
                await _index_google_calendar_events(1, 1, "user1", "2024-01-01", "2024-12-31")


class TestIndexAirtableRecords:
    """Tests for Airtable records indexing."""

    @pytest.mark.asyncio
    async def test_index_airtable_records_creates_session(self):
        """Test Airtable indexing creates session."""
        mock_session = AsyncMock()
        
        with patch("app.tasks.celery_tasks.connector_tasks.get_celery_session_maker") as mock_maker:
            mock_context = AsyncMock()
            mock_context.__aenter__.return_value = mock_session
            mock_context.__aexit__.return_value = None
            mock_maker.return_value.return_value = mock_context
            
            with patch("app.routes.search_source_connectors_routes.run_airtable_indexing", new_callable=AsyncMock):
                await _index_airtable_records(1, 1, "user1", "2024-01-01", "2024-12-31")


class TestIndexGoogleGmailMessages:
    """Tests for Google Gmail messages indexing."""

    @pytest.mark.asyncio
    async def test_index_gmail_messages_calculates_days_back(self):
        """Test Gmail indexing calculates days_back from start_date."""
        mock_session = AsyncMock()
        
        with patch("app.tasks.celery_tasks.connector_tasks.get_celery_session_maker") as mock_maker:
            mock_context = AsyncMock()
            mock_context.__aenter__.return_value = mock_session
            mock_context.__aexit__.return_value = None
            mock_maker.return_value.return_value = mock_context
            
            with patch("app.routes.search_source_connectors_routes.run_google_gmail_indexing", new_callable=AsyncMock) as mock_run:
                await _index_google_gmail_messages(1, 1, "user1", "2024-01-01", "2024-12-31")
                # Should have been called with calculated days_back
                mock_run.assert_called_once()

    @pytest.mark.asyncio
    async def test_index_gmail_messages_default_days_back(self):
        """Test Gmail indexing uses default days_back when no start_date."""
        mock_session = AsyncMock()
        
        with patch("app.tasks.celery_tasks.connector_tasks.get_celery_session_maker") as mock_maker:
            mock_context = AsyncMock()
            mock_context.__aenter__.return_value = mock_session
            mock_context.__aexit__.return_value = None
            mock_maker.return_value.return_value = mock_context
            
            with patch("app.routes.search_source_connectors_routes.run_google_gmail_indexing", new_callable=AsyncMock) as mock_run:
                await _index_google_gmail_messages(1, 1, "user1", None, None)
                # Should have been called with max_messages=100 and default days_back=30
                # Args: session, connector_id, search_space_id, user_id, max_messages, days_back
                mock_run.assert_called_once()
                call_args = mock_run.call_args[0]
                assert call_args[4] == 100  # max_messages (index 4)
                assert call_args[5] == 30  # days_back (index 5)

    @pytest.mark.asyncio
    async def test_index_gmail_messages_invalid_date_uses_default(self):
        """Test Gmail indexing uses default when date parsing fails."""
        mock_session = AsyncMock()
        
        with patch("app.tasks.celery_tasks.connector_tasks.get_celery_session_maker") as mock_maker:
            mock_context = AsyncMock()
            mock_context.__aenter__.return_value = mock_session
            mock_context.__aexit__.return_value = None
            mock_maker.return_value.return_value = mock_context
            
            with patch("app.routes.search_source_connectors_routes.run_google_gmail_indexing", new_callable=AsyncMock) as mock_run:
                await _index_google_gmail_messages(1, 1, "user1", "invalid-date", None)
                mock_run.assert_called_once()
                # Args: session, connector_id, search_space_id, user_id, max_messages, days_back
                call_args = mock_run.call_args[0]
                assert call_args[4] == 100  # max_messages (index 4)
                assert call_args[5] == 30  # days_back default (index 5)


class TestIndexDiscordMessages:
    """Tests for Discord messages indexing."""

    @pytest.mark.asyncio
    async def test_index_discord_messages_with_valid_params(self):
        """Test Discord indexing with valid parameters."""
        mock_session = AsyncMock()
        
        with patch("app.tasks.celery_tasks.connector_tasks.get_celery_session_maker") as mock_maker:
            mock_context = AsyncMock()
            mock_context.__aenter__.return_value = mock_session
            mock_context.__aexit__.return_value = None
            mock_maker.return_value.return_value = mock_context
            
            with patch("app.routes.search_source_connectors_routes.run_discord_indexing", new_callable=AsyncMock):
                await _index_discord_messages(1, 1, "user1", "2024-01-01", "2024-12-31")


class TestIndexLumaEvents:
    """Tests for Luma events indexing."""

    @pytest.mark.asyncio
    async def test_index_luma_events_creates_session(self):
        """Test Luma indexing creates session."""
        mock_session = AsyncMock()
        
        with patch("app.tasks.celery_tasks.connector_tasks.get_celery_session_maker") as mock_maker:
            mock_context = AsyncMock()
            mock_context.__aenter__.return_value = mock_session
            mock_context.__aexit__.return_value = None
            mock_maker.return_value.return_value = mock_context
            
            with patch("app.routes.search_source_connectors_routes.run_luma_indexing", new_callable=AsyncMock):
                await _index_luma_events(1, 1, "user1", "2024-01-01", "2024-12-31")


class TestIndexElasticsearchDocuments:
    """Tests for Elasticsearch documents indexing."""

    @pytest.mark.asyncio
    async def test_index_elasticsearch_documents_with_valid_params(self):
        """Test Elasticsearch indexing with valid parameters."""
        mock_session = AsyncMock()
        
        with patch("app.tasks.celery_tasks.connector_tasks.get_celery_session_maker") as mock_maker:
            mock_context = AsyncMock()
            mock_context.__aenter__.return_value = mock_session
            mock_context.__aexit__.return_value = None
            mock_maker.return_value.return_value = mock_context
            
            with patch("app.routes.search_source_connectors_routes.run_elasticsearch_indexing", new_callable=AsyncMock):
                await _index_elasticsearch_documents(1, 1, "user1", "2024-01-01", "2024-12-31")


class TestIndexCrawledUrls:
    """Tests for web page URL indexing."""

    @pytest.mark.asyncio
    async def test_index_crawled_urls_creates_session(self):
        """Test web page indexing creates session."""
        mock_session = AsyncMock()
        
        with patch("app.tasks.celery_tasks.connector_tasks.get_celery_session_maker") as mock_maker:
            mock_context = AsyncMock()
            mock_context.__aenter__.return_value = mock_session
            mock_context.__aexit__.return_value = None
            mock_maker.return_value.return_value = mock_context
            
            with patch("app.routes.search_source_connectors_routes.run_web_page_indexing", new_callable=AsyncMock):
                await _index_crawled_urls(1, 1, "user1", "2024-01-01", "2024-12-31")
