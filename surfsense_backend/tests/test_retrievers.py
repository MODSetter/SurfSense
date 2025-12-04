"""
Tests for hybrid search retrievers.
Tests the ChucksHybridSearchRetriever and DocumentHybridSearchRetriever classes.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.retriver.chunks_hybrid_search import ChucksHybridSearchRetriever
from app.retriver.documents_hybrid_search import DocumentHybridSearchRetriever


class TestChunksHybridSearchRetriever:
    """Tests for ChucksHybridSearchRetriever."""

    def test_init(self):
        """Test retriever initialization."""
        mock_session = AsyncMock()
        retriever = ChucksHybridSearchRetriever(mock_session)
        
        assert retriever.db_session == mock_session

    @pytest.mark.asyncio
    async def test_hybrid_search_returns_empty_on_no_results(self):
        """Test hybrid search returns empty list when no results."""
        mock_session = AsyncMock()
        
        # Mock the session to return empty results
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute = AsyncMock(return_value=mock_result)
        
        retriever = ChucksHybridSearchRetriever(mock_session)
        
        with patch.object(retriever, 'hybrid_search', new_callable=AsyncMock) as mock_search:
            mock_search.return_value = []
            
            result = await retriever.hybrid_search(
                query_text="test query",
                top_k=10,
                search_space_id=1,
                document_type="FILE",
            )
            
            assert result == []


class TestDocumentHybridSearchRetriever:
    """Tests for DocumentHybridSearchRetriever."""

    def test_init(self):
        """Test retriever initialization."""
        mock_session = AsyncMock()
        retriever = DocumentHybridSearchRetriever(mock_session)
        
        assert retriever.db_session == mock_session

    @pytest.mark.asyncio
    async def test_hybrid_search_returns_empty_on_no_results(self):
        """Test hybrid search returns empty list when no results."""
        mock_session = AsyncMock()
        
        retriever = DocumentHybridSearchRetriever(mock_session)
        
        with patch.object(retriever, 'hybrid_search', new_callable=AsyncMock) as mock_search:
            mock_search.return_value = []
            
            result = await retriever.hybrid_search(
                query_text="test query",
                top_k=10,
                search_space_id=1,
                document_type="FILE",
            )
            
            assert result == []


class TestRetrieverIntegration:
    """Integration tests for retrievers."""

    def test_chunk_retriever_uses_correct_session(self):
        """Test chunk retriever uses provided session."""
        mock_session = AsyncMock()
        mock_session.id = "test-session"
        
        retriever = ChucksHybridSearchRetriever(mock_session)
        
        assert retriever.db_session.id == "test-session"

    def test_document_retriever_uses_correct_session(self):
        """Test document retriever uses provided session."""
        mock_session = AsyncMock()
        mock_session.id = "test-session"
        
        retriever = DocumentHybridSearchRetriever(mock_session)
        
        assert retriever.db_session.id == "test-session"
