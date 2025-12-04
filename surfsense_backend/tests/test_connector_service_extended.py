"""
Extended tests for connector service.
Tests the ConnectorService class with mocked database and external dependencies.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.connector_service import ConnectorService
from app.agents.researcher.configuration import SearchMode


class TestConnectorServiceInitialization:
    """Tests for ConnectorService initialization."""

    def test_init_with_search_space_id(self):
        """Test initialization with search space ID."""
        mock_session = AsyncMock()
        service = ConnectorService(mock_session, search_space_id=1)
        
        assert service.session == mock_session
        assert service.search_space_id == 1
        assert service.source_id_counter == 100000

    def test_init_without_search_space_id(self):
        """Test initialization without search space ID."""
        mock_session = AsyncMock()
        service = ConnectorService(mock_session)
        
        assert service.search_space_id is None

    @pytest.mark.asyncio
    async def test_initialize_counter_success(self):
        """Test counter initialization from database."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar.return_value = 50
        mock_session.execute = AsyncMock(return_value=mock_result)
        
        service = ConnectorService(mock_session, search_space_id=1)
        await service.initialize_counter()
        
        assert service.source_id_counter == 51

    @pytest.mark.asyncio
    async def test_initialize_counter_database_error(self):
        """Test counter initialization handles database errors gracefully."""
        from sqlalchemy.exc import SQLAlchemyError
        
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(side_effect=SQLAlchemyError("DB Error"))
        
        service = ConnectorService(mock_session, search_space_id=1)
        await service.initialize_counter()
        
        # Should fallback to 1
        assert service.source_id_counter == 1


class TestSearchCrawledUrls:
    """Tests for search_crawled_urls method."""

    @pytest.mark.asyncio
    async def test_search_crawled_urls_empty_results(self):
        """Test search with no results."""
        mock_session = AsyncMock()
        service = ConnectorService(mock_session, search_space_id=1)
        
        # Mock the chunk retriever
        service.chunk_retriever = MagicMock()
        service.chunk_retriever.hybrid_search = AsyncMock(return_value=[])
        
        result, chunks = await service.search_crawled_urls(
            user_query="test query",
            search_space_id=1,
            top_k=20,
            search_mode=SearchMode.CHUNKS,
        )
        
        assert result["type"] == "CRAWLED_URL"
        assert result["sources"] == []
        assert chunks == []

    @pytest.mark.asyncio
    async def test_search_crawled_urls_with_results(self):
        """Test search with results."""
        mock_session = AsyncMock()
        service = ConnectorService(mock_session, search_space_id=1)
        
        # Mock the chunk retriever
        mock_chunks = [
            {
                "chunk_id": 1,
                "content": "Test content",
                "document": {
                    "title": "Test Document",
                    "metadata": {
                        "source": "https://example.com",
                        "description": "Test description",
                    },
                },
            }
        ]
        service.chunk_retriever = MagicMock()
        service.chunk_retriever.hybrid_search = AsyncMock(return_value=mock_chunks)
        
        result, chunks = await service.search_crawled_urls(
            user_query="test query",
            search_space_id=1,
            top_k=20,
            search_mode=SearchMode.CHUNKS,
        )
        
        assert result["type"] == "CRAWLED_URL"
        assert len(result["sources"]) == 1
        assert result["sources"][0]["title"] == "Test Document"
        assert len(chunks) == 1


class TestSearchFiles:
    """Tests for search_files method."""

    @pytest.mark.asyncio
    async def test_search_files_empty_results(self):
        """Test file search with no results."""
        mock_session = AsyncMock()
        service = ConnectorService(mock_session, search_space_id=1)
        
        # Mock the chunk retriever
        service.chunk_retriever = MagicMock()
        service.chunk_retriever.hybrid_search = AsyncMock(return_value=[])
        
        result, chunks = await service.search_files(
            user_query="test query",
            search_space_id=1,
            top_k=20,
            search_mode=SearchMode.CHUNKS,
        )
        
        assert result["type"] == "FILE"
        assert result["sources"] == []
        assert chunks == []


class TestSearchDocuments:
    """Tests for document search mode."""

    @pytest.mark.asyncio
    async def test_search_uses_document_retriever_in_documents_mode(self):
        """Test that document mode uses document retriever."""
        mock_session = AsyncMock()
        service = ConnectorService(mock_session, search_space_id=1)
        
        # Mock both retrievers
        service.chunk_retriever = MagicMock()
        service.chunk_retriever.hybrid_search = AsyncMock(return_value=[])
        service.document_retriever = MagicMock()
        service.document_retriever.hybrid_search = AsyncMock(return_value=[])
        
        await service.search_crawled_urls(
            user_query="test query",
            search_space_id=1,
            top_k=20,
            search_mode=SearchMode.DOCUMENTS,
        )
        
        # Document retriever should be called, not chunk retriever
        assert service.document_retriever.hybrid_search.called


class TestTransformDocumentResults:
    """Tests for _transform_document_results method."""

    def test_transform_empty_list(self):
        """Test transformation of empty results."""
        mock_session = AsyncMock()
        service = ConnectorService(mock_session)
        
        result = service._transform_document_results([])
        
        assert result == []

    def test_transform_document_with_chunks_content(self):
        """Test transformation uses chunks_content when available."""
        mock_session = AsyncMock()
        service = ConnectorService(mock_session)
        
        input_docs = [
            {
                "document_id": 1,
                "title": "Test",
                "document_type": "FILE",
                "metadata": {},
                "content": "Short",
                "chunks_content": "Full content from chunks",
                "score": 0.8,
            }
        ]
        
        result = service._transform_document_results(input_docs)
        
        assert len(result) == 1
        assert result[0]["content"] == "Full content from chunks"

    def test_transform_document_falls_back_to_content(self):
        """Test transformation falls back to content when no chunks_content."""
        mock_session = AsyncMock()
        service = ConnectorService(mock_session)
        
        input_docs = [
            {
                "document_id": 1,
                "title": "Test",
                "document_type": "FILE",
                "metadata": {},
                "content": "Only content available",
                "score": 0.8,
            }
        ]
        
        result = service._transform_document_results(input_docs)
        
        assert len(result) == 1
        assert result[0]["content"] == "Only content available"


class TestSearchExtension:
    """Tests for extension document search."""

    @pytest.mark.asyncio
    async def test_search_extension_documents(self):
        """Test searching extension documents."""
        mock_session = AsyncMock()
        service = ConnectorService(mock_session, search_space_id=1)
        
        # Mock the chunk retriever
        mock_chunks = [
            {
                "chunk_id": 1,
                "content": "Browser captured content",
                "document": {
                    "title": "Web Page Title",
                    "metadata": {
                        "url": "https://example.com/page",
                        "BrowsingSessionId": "session-123",
                    },
                },
            }
        ]
        service.chunk_retriever = MagicMock()
        service.chunk_retriever.hybrid_search = AsyncMock(return_value=mock_chunks)
        
        result, chunks = await service.search_extension(
            user_query="test",
            search_space_id=1,
            top_k=20,
            search_mode=SearchMode.CHUNKS,
        )
        
        assert result["type"] == "EXTENSION"
        assert len(result["sources"]) == 1


class TestSearchSlack:
    """Tests for Slack connector search."""

    @pytest.mark.asyncio
    async def test_search_slack_documents(self):
        """Test searching Slack documents."""
        mock_session = AsyncMock()
        service = ConnectorService(mock_session, search_space_id=1)
        
        # Mock the chunk retriever
        mock_chunks = [
            {
                "chunk_id": 1,
                "content": "Slack message content",
                "document": {
                    "title": "Slack Channel - #general",
                    "metadata": {
                        "channel_name": "general",
                        "username": "john_doe",
                        "timestamp": "2024-01-01T12:00:00Z",
                    },
                },
            }
        ]
        service.chunk_retriever = MagicMock()
        service.chunk_retriever.hybrid_search = AsyncMock(return_value=mock_chunks)
        
        result, chunks = await service.search_slack(
            user_query="test",
            search_space_id=1,
            top_k=20,
            search_mode=SearchMode.CHUNKS,
        )
        
        assert result["type"] == "SLACK_CONNECTOR"
        assert len(result["sources"]) == 1


class TestSearchNotion:
    """Tests for Notion connector search."""

    @pytest.mark.asyncio
    async def test_search_notion_documents(self):
        """Test searching Notion documents."""
        mock_session = AsyncMock()
        service = ConnectorService(mock_session, search_space_id=1)
        
        # Mock the chunk retriever
        mock_chunks = [
            {
                "chunk_id": 1,
                "content": "Notion page content",
                "document": {
                    "title": "Meeting Notes",
                    "metadata": {
                        "page_id": "notion-page-123",
                        "url": "https://notion.so/page",
                    },
                },
            }
        ]
        service.chunk_retriever = MagicMock()
        service.chunk_retriever.hybrid_search = AsyncMock(return_value=mock_chunks)
        
        result, chunks = await service.search_notion(
            user_query="test",
            search_space_id=1,
            top_k=20,
            search_mode=SearchMode.CHUNKS,
        )
        
        assert result["type"] == "NOTION_CONNECTOR"
        assert len(result["sources"]) == 1


class TestSearchYoutube:
    """Tests for YouTube document search."""

    @pytest.mark.asyncio
    async def test_search_youtube_documents(self):
        """Test searching YouTube documents."""
        mock_session = AsyncMock()
        service = ConnectorService(mock_session, search_space_id=1)
        
        # Mock the chunk retriever
        mock_chunks = [
            {
                "chunk_id": 1,
                "content": "Video transcript content",
                "document": {
                    "title": "YouTube Video Title",
                    "metadata": {
                        "video_id": "dQw4w9WgXcQ",
                        "channel": "Channel Name",
                        "duration": "3:45",
                    },
                },
            }
        ]
        service.chunk_retriever = MagicMock()
        service.chunk_retriever.hybrid_search = AsyncMock(return_value=mock_chunks)
        
        result, chunks = await service.search_youtube(
            user_query="test",
            search_space_id=1,
            top_k=20,
            search_mode=SearchMode.CHUNKS,
        )
        
        assert result["type"] == "YOUTUBE_VIDEO"
        assert len(result["sources"]) == 1


class TestSearchGithub:
    """Tests for GitHub connector search."""

    @pytest.mark.asyncio
    async def test_search_github_documents(self):
        """Test searching GitHub documents."""
        mock_session = AsyncMock()
        service = ConnectorService(mock_session, search_space_id=1)
        
        # Mock the chunk retriever
        mock_chunks = [
            {
                "chunk_id": 1,
                "content": "Code content from GitHub",
                "document": {
                    "title": "repo/file.py",
                    "metadata": {
                        "repo": "owner/repo",
                        "path": "src/file.py",
                        "branch": "main",
                    },
                },
            }
        ]
        service.chunk_retriever = MagicMock()
        service.chunk_retriever.hybrid_search = AsyncMock(return_value=mock_chunks)
        
        result, chunks = await service.search_github(
            user_query="test",
            search_space_id=1,
            top_k=20,
            search_mode=SearchMode.CHUNKS,
        )
        
        assert result["type"] == "GITHUB_CONNECTOR"
        assert len(result["sources"]) == 1


class TestExternalSearchConnectors:
    """Tests for external search API connectors."""

    @pytest.mark.asyncio
    async def test_tavily_search_no_connector(self):
        """Test Tavily search returns empty when no connector configured."""
        mock_session = AsyncMock()
        
        # Mock no connector found
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.first.return_value = None
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute = AsyncMock(return_value=mock_result)
        
        service = ConnectorService(mock_session, search_space_id=1)
        
        result = await service.search_tavily(
            user_query="test",
            search_space_id=1,
        )
        
        # Returns a tuple (sources_info_dict, documents_list)
        sources_info, documents = result
        assert sources_info["type"] == "TAVILY_API"
        assert sources_info["sources"] == []
        assert documents == []

    @pytest.mark.asyncio
    async def test_linkup_search_no_connector(self):
        """Test Linkup search returns empty when no connector configured."""
        mock_session = AsyncMock()
        
        # Mock no connector found
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.first.return_value = None
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute = AsyncMock(return_value=mock_result)
        
        service = ConnectorService(mock_session, search_space_id=1)
        
        result = await service.search_linkup(
            user_query="test",
            search_space_id=1,
        )
        
        # Returns a tuple (sources_info_dict, documents_list)
        sources_info, documents = result
        assert sources_info["type"] == "LINKUP_API"
        assert sources_info["sources"] == []
        assert documents == []

    @pytest.mark.asyncio
    async def test_searxng_search_no_connector(self):
        """Test SearXNG search returns empty when no connector configured."""
        mock_session = AsyncMock()
        
        # Mock no connector found
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.first.return_value = None
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute = AsyncMock(return_value=mock_result)
        
        service = ConnectorService(mock_session, search_space_id=1)
        
        result = await service.search_searxng(
            user_query="test",
            search_space_id=1,
        )
        
        # Returns a tuple (sources_info_dict, documents_list)
        sources_info, documents = result
        assert sources_info["type"] == "SEARXNG_API"
        assert sources_info["sources"] == []
        assert documents == []
