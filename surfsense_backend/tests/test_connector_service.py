"""
Tests for the ConnectorService class.

These tests validate:
1. Search results are properly transformed with correct structure
2. Missing connectors are handled gracefully (empty results, not errors)
3. Counter initialization is resilient to database errors
4. Search modes affect which retriever is used
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

# Skip these tests if app dependencies aren't installed
pytest.importorskip("linkup")
pytest.importorskip("litellm")

from app.services.connector_service import ConnectorService
from app.agents.researcher.configuration import SearchMode


class TestConnectorServiceResilience:
    """Tests for ConnectorService resilience and error handling."""

    def test_init_sets_safe_defaults(self, mock_session):
        """
        Service must initialize with safe defaults.
        Critical: source_id_counter must never start at 0 (collision risk).
        """
        service = ConnectorService(mock_session)

        # Must have a high starting counter to avoid collisions with existing data
        assert service.source_id_counter >= 100000

    @pytest.mark.asyncio
    async def test_counter_init_survives_database_error(self, mock_session):
        """
        Counter initialization must not crash on database errors.
        This is critical - a DB error during init shouldn't break the service.
        """
        from sqlalchemy.exc import SQLAlchemyError

        service = ConnectorService(mock_session, search_space_id=1)
        mock_session.execute = AsyncMock(side_effect=SQLAlchemyError("DB error"))

        # Must not raise
        await service.initialize_counter()

        # Must have a usable counter value
        assert service.source_id_counter >= 1

    @pytest.mark.asyncio
    async def test_counter_init_without_search_space_is_no_op(self, mock_session):
        """
        When no search_space_id is provided, counter init should be a no-op.
        Calling the database without a search_space_id would be wasteful.
        """
        service = ConnectorService(mock_session, search_space_id=None)

        await service.initialize_counter()

        # Should NOT have called database
        mock_session.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_counter_continues_from_existing_chunks(self, mock_session):
        """
        Counter must continue from the highest existing source_id + 1.
        Starting lower would cause ID collisions.
        """
        service = ConnectorService(mock_session, search_space_id=1)

        mock_result = MagicMock()
        mock_result.scalar.return_value = 500  # Max existing source_id
        mock_session.execute = AsyncMock(return_value=mock_result)

        await service.initialize_counter()

        # Must be > 500 to avoid collision
        assert service.source_id_counter == 501


class TestSearchResultTransformation:
    """
    Tests validating search result transformation produces correct output structure.
    """

    def test_transform_empty_list_returns_empty(self, mock_session):
        """Empty input must return empty output - not None or error."""
        service = ConnectorService(mock_session)
        result = service._transform_document_results([])

        assert result == []
        assert isinstance(result, list)

    def test_transform_preserves_all_required_fields(self, mock_session):
        """
        Transformation must preserve all fields needed by the frontend.
        Missing fields would break the UI.
        """
        service = ConnectorService(mock_session)

        input_docs = [
            {
                "document_id": 42,
                "title": "Important Doc",
                "document_type": "FILE",
                "metadata": {"url": "https://example.com/doc"},
                "chunks_content": "The actual content",
                "score": 0.87,
            }
        ]

        result = service._transform_document_results(input_docs)

        assert len(result) == 1
        transformed = result[0]

        # All these fields are required by the frontend
        assert "chunk_id" in transformed
        assert "document" in transformed
        assert "content" in transformed
        assert "score" in transformed

        # Nested document structure must be correct
        assert "id" in transformed["document"]
        assert "title" in transformed["document"]
        assert "document_type" in transformed["document"]
        assert "metadata" in transformed["document"]

    def test_transform_uses_chunks_content_over_content(self, mock_session):
        """
        When chunks_content exists, it should be used over content field.
        This ensures full content is returned, not truncated.
        """
        service = ConnectorService(mock_session)

        input_docs = [
            {
                "document_id": 1,
                "title": "Test",
                "document_type": "FILE",
                "metadata": {},
                "content": "Short preview",
                "chunks_content": "Full document content that is much longer",
                "score": 0.8,
            }
        ]

        result = service._transform_document_results(input_docs)

        # Must use chunks_content, not content
        assert result[0]["content"] == "Full document content that is much longer"

    def test_transform_falls_back_to_content_when_no_chunks_content(self, mock_session):
        """
        When chunks_content is missing, fall back to content field.
        Must not error or return empty content.
        """
        service = ConnectorService(mock_session)

        input_docs = [
            {
                "document_id": 1,
                "title": "Test",
                "document_type": "FILE",
                "metadata": {},
                "content": "Fallback content",
                "score": 0.8,
            }
        ]

        result = service._transform_document_results(input_docs)

        assert result[0]["content"] == "Fallback content"


class TestMissingConnectorHandling:
    """
    Tests validating graceful handling when connectors are not configured.
    """

    @pytest.mark.asyncio
    async def test_missing_tavily_connector_returns_empty_not_error(self, mock_session):
        """
        Missing Tavily connector must return empty results, not raise exception.
        This is important - users without the connector shouldn't see errors.
        """
        service = ConnectorService(mock_session, search_space_id=1)

        with patch.object(
            service, "get_connector_by_type", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = None

            result_obj, docs = await service.search_tavily(
                "test query", search_space_id=1
            )

            # Must return valid structure with empty sources
            assert result_obj["type"] == "TAVILY_API"
            assert result_obj["sources"] == []
            assert docs == []
            # No exception should have been raised

    @pytest.mark.asyncio
    async def test_missing_searxng_connector_returns_empty_not_error(self, mock_session):
        """Missing SearxNG connector must return empty results gracefully."""
        service = ConnectorService(mock_session, search_space_id=1)

        with patch.object(
            service, "get_connector_by_type", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = None

            result_obj, docs = await service.search_searxng(
                "test query", search_space_id=1
            )

            assert result_obj["type"] == "SEARXNG_API"
            assert result_obj["sources"] == []

    @pytest.mark.asyncio
    async def test_missing_baidu_connector_returns_empty_not_error(self, mock_session):
        """Missing Baidu connector must return empty results gracefully."""
        service = ConnectorService(mock_session, search_space_id=1)

        with patch.object(
            service, "get_connector_by_type", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = None

            result_obj, docs = await service.search_baidu(
                "test query", search_space_id=1
            )

            assert result_obj["type"] == "BAIDU_SEARCH_API"
            assert result_obj["sources"] == []


class TestSearchResultStructure:
    """
    Tests validating that search results have correct structure.
    """

    @pytest.mark.asyncio
    async def test_crawled_urls_result_has_correct_type(self, mock_session):
        """
        Crawled URL search results must have type "CRAWLED_URL".
        Wrong type would break filtering in the frontend.
        """
        service = ConnectorService(mock_session, search_space_id=1)

        with patch.object(
            service.chunk_retriever, "hybrid_search", new_callable=AsyncMock
        ) as mock_search:
            mock_search.return_value = []

            result_obj, _ = await service.search_crawled_urls(
                "test query", search_space_id=1, top_k=10
            )

            assert result_obj["type"] == "CRAWLED_URL"

    @pytest.mark.asyncio
    async def test_files_result_has_correct_type(self, mock_session):
        """File search results must have type "FILE"."""
        service = ConnectorService(mock_session, search_space_id=1)

        with patch.object(
            service.chunk_retriever, "hybrid_search", new_callable=AsyncMock
        ) as mock_search:
            mock_search.return_value = []

            result_obj, _ = await service.search_files(
                "test query", search_space_id=1, top_k=10
            )

            assert result_obj["type"] == "FILE"

    @pytest.mark.asyncio
    async def test_slack_result_has_correct_type(self, mock_session):
        """Slack search results must have type "SLACK_CONNECTOR"."""
        service = ConnectorService(mock_session, search_space_id=1)

        with patch.object(
            service.chunk_retriever, "hybrid_search", new_callable=AsyncMock
        ) as mock_search:
            mock_search.return_value = []

            result_obj, _ = await service.search_slack(
                "test query", search_space_id=1, top_k=10
            )

            assert result_obj["type"] == "SLACK_CONNECTOR"

    @pytest.mark.asyncio
    async def test_notion_result_has_correct_type(self, mock_session):
        """Notion search results must have type "NOTION_CONNECTOR"."""
        service = ConnectorService(mock_session, search_space_id=1)

        with patch.object(
            service.chunk_retriever, "hybrid_search", new_callable=AsyncMock
        ) as mock_search:
            mock_search.return_value = []

            result_obj, _ = await service.search_notion(
                "test query", search_space_id=1, top_k=10
            )

            assert result_obj["type"] == "NOTION_CONNECTOR"

    @pytest.mark.asyncio
    async def test_github_result_has_correct_type(self, mock_session):
        """GitHub search results must have type "GITHUB_CONNECTOR"."""
        service = ConnectorService(mock_session, search_space_id=1)

        with patch.object(
            service.chunk_retriever, "hybrid_search", new_callable=AsyncMock
        ) as mock_search:
            mock_search.return_value = []

            result_obj, _ = await service.search_github(
                "test query", search_space_id=1, top_k=10
            )

            assert result_obj["type"] == "GITHUB_CONNECTOR"

    @pytest.mark.asyncio
    async def test_youtube_result_has_correct_type(self, mock_session):
        """YouTube search results must have type "YOUTUBE_VIDEO"."""
        service = ConnectorService(mock_session, search_space_id=1)

        with patch.object(
            service.chunk_retriever, "hybrid_search", new_callable=AsyncMock
        ) as mock_search:
            mock_search.return_value = []

            result_obj, _ = await service.search_youtube(
                "test query", search_space_id=1, top_k=10
            )

            assert result_obj["type"] == "YOUTUBE_VIDEO"


class TestSearchModeAffectsRetriever:
    """
    Tests validating that search mode affects which retriever is used.
    """

    @pytest.mark.asyncio
    async def test_documents_mode_uses_document_retriever(self, mock_session):
        """
        DOCUMENTS mode must use document_retriever, not chunk_retriever.
        Using wrong retriever would return wrong result granularity.
        """
        service = ConnectorService(mock_session, search_space_id=1)

        mock_docs = [
            {
                "document_id": 1,
                "title": "Test",
                "document_type": "FILE",
                "metadata": {},
                "chunks_content": "content",
                "score": 0.9,
            }
        ]

        with patch.object(
            service.document_retriever, "hybrid_search", new_callable=AsyncMock
        ) as mock_doc_search:
            mock_doc_search.return_value = mock_docs

            with patch.object(
                service.chunk_retriever, "hybrid_search", new_callable=AsyncMock
            ) as mock_chunk_search:

                await service.search_files(
                    "test query",
                    search_space_id=1,
                    top_k=10,
                    search_mode=SearchMode.DOCUMENTS,
                )

                # Document retriever should have been called
                mock_doc_search.assert_called_once()
                # Chunk retriever should NOT have been called
                mock_chunk_search.assert_not_called()

    @pytest.mark.asyncio
    async def test_chunks_mode_uses_chunk_retriever(self, mock_session):
        """
        Default/CHUNKS mode must use chunk_retriever.
        """
        service = ConnectorService(mock_session, search_space_id=1)

        with patch.object(
            service.chunk_retriever, "hybrid_search", new_callable=AsyncMock
        ) as mock_chunk_search:
            mock_chunk_search.return_value = []

            with patch.object(
                service.document_retriever, "hybrid_search", new_callable=AsyncMock
            ) as mock_doc_search:

                await service.search_files(
                    "test query",
                    search_space_id=1,
                    top_k=10,
                    # Default mode (no search_mode specified)
                )

                # Chunk retriever should have been called
                mock_chunk_search.assert_called_once()
                # Document retriever should NOT have been called
                mock_doc_search.assert_not_called()


class TestSearchResultMetadataExtraction:
    """
    Tests validating that metadata is correctly extracted for different source types.
    """

    @pytest.mark.asyncio
    async def test_crawled_url_extracts_source_as_url(self, mock_session):
        """
        Crawled URL results must extract 'source' from metadata as URL.
        Wrong field would break link navigation.
        """
        service = ConnectorService(mock_session, search_space_id=1)

        mock_chunks = [
            {
                "chunk_id": 1,
                "content": "Page content",
                "document": {
                    "title": "Web Page",
                    "metadata": {"source": "https://example.com/page"},
                },
            }
        ]

        with patch.object(
            service.chunk_retriever, "hybrid_search", new_callable=AsyncMock
        ) as mock_search:
            mock_search.return_value = mock_chunks

            result_obj, _ = await service.search_crawled_urls(
                "test", search_space_id=1, top_k=10
            )

            assert result_obj["sources"][0]["url"] == "https://example.com/page"

    @pytest.mark.asyncio
    async def test_youtube_extracts_video_metadata(self, mock_session):
        """
        YouTube results must extract video_id and other video metadata.
        Missing video_id would break video embedding.
        """
        service = ConnectorService(mock_session, search_space_id=1)

        mock_chunks = [
            {
                "chunk_id": 1,
                "content": "Transcript",
                "document": {
                    "title": "YouTube",
                    "metadata": {
                        "video_title": "Test Video",
                        "video_id": "dQw4w9WgXcQ",
                        "channel_name": "Test Channel",
                    },
                },
            }
        ]

        with patch.object(
            service.chunk_retriever, "hybrid_search", new_callable=AsyncMock
        ) as mock_search:
            mock_search.return_value = mock_chunks

            result_obj, _ = await service.search_youtube(
                "test", search_space_id=1, top_k=10
            )

            source = result_obj["sources"][0]
            assert source["video_id"] == "dQw4w9WgXcQ"
            assert "Test Video" in source["title"]
