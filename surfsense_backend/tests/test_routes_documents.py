"""
Tests for documents routes.
Tests API endpoints with mocked database sessions and authentication.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import HTTPException

from app.routes.documents_routes import (
    create_documents,
    read_documents,
    search_documents,
    read_document,
    update_document,
    delete_document,
    get_document_type_counts,
    get_document_by_chunk_id,
)
from app.schemas import DocumentsCreate, DocumentUpdate
from app.db import DocumentType


class TestCreateDocuments:
    """Tests for the create_documents endpoint."""

    @pytest.mark.asyncio
    async def test_create_documents_invalid_type(self):
        """Test creating documents with invalid type."""
        mock_session = AsyncMock()
        mock_session.rollback = AsyncMock()
        mock_user = MagicMock()
        mock_user.id = "user-123"
        
        # Use a type that triggers the else branch
        request = DocumentsCreate(
            search_space_id=1,
            document_type=DocumentType.FILE,  # Not EXTENSION or YOUTUBE_VIDEO
            content=[],
        )
        
        with patch("app.routes.documents_routes.check_permission") as mock_check:
            mock_check.return_value = None
            
            with pytest.raises(HTTPException) as exc_info:
                await create_documents(
                    request=request,
                    session=mock_session,
                    user=mock_user,
                )
            
            assert exc_info.value.status_code == 400


class TestReadDocuments:
    """Tests for the read_documents endpoint."""

    @pytest.mark.asyncio
    async def test_read_documents_with_search_space_filter(self):
        """Test reading documents filtered by search space."""
        mock_session = AsyncMock()
        mock_user = MagicMock()
        mock_user.id = "user-123"
        
        # Mock query results
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result.scalars.return_value = mock_scalars
        mock_result.scalar.return_value = 0
        mock_session.execute = AsyncMock(return_value=mock_result)
        
        with patch("app.routes.documents_routes.check_permission") as mock_check:
            mock_check.return_value = None
            
            result = await read_documents(
                skip=0,
                page=None,
                page_size=50,
                search_space_id=1,
                document_types=None,
                session=mock_session,
                user=mock_user,
            )
            
            assert result.items == []
            assert result.total == 0

    @pytest.mark.asyncio
    async def test_read_documents_with_type_filter(self):
        """Test reading documents filtered by type."""
        mock_session = AsyncMock()
        mock_user = MagicMock()
        mock_user.id = "user-123"
        
        # Mock query results
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result.scalars.return_value = mock_scalars
        mock_result.scalar.return_value = 0
        mock_session.execute = AsyncMock(return_value=mock_result)
        
        with patch("app.routes.documents_routes.check_permission") as mock_check:
            mock_check.return_value = None
            
            result = await read_documents(
                skip=0,
                page=None,
                page_size=50,
                search_space_id=1,
                document_types="EXTENSION,FILE",
                session=mock_session,
                user=mock_user,
            )
            
            assert result.items == []

    @pytest.mark.asyncio
    async def test_read_documents_all_search_spaces(self):
        """Test reading documents from all accessible search spaces."""
        mock_session = AsyncMock()
        mock_user = MagicMock()
        mock_user.id = "user-123"
        
        # Mock query results
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result.scalars.return_value = mock_scalars
        mock_result.scalar.return_value = 0
        mock_session.execute = AsyncMock(return_value=mock_result)
        
        result = await read_documents(
            skip=0,
            page=None,
            page_size=50,
            search_space_id=None,
            document_types=None,
            session=mock_session,
            user=mock_user,
        )
        
        assert result.items == []


class TestSearchDocuments:
    """Tests for the search_documents endpoint."""

    @pytest.mark.asyncio
    async def test_search_documents_by_title(self):
        """Test searching documents by title."""
        mock_session = AsyncMock()
        mock_user = MagicMock()
        mock_user.id = "user-123"
        
        # Mock query results
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result.scalars.return_value = mock_scalars
        mock_result.scalar.return_value = 0
        mock_session.execute = AsyncMock(return_value=mock_result)
        
        with patch("app.routes.documents_routes.check_permission") as mock_check:
            mock_check.return_value = None
            
            result = await search_documents(
                title="test",
                skip=0,
                page=None,
                page_size=50,
                search_space_id=1,
                document_types=None,
                session=mock_session,
                user=mock_user,
            )
            
            assert result.items == []
            assert result.total == 0


class TestReadDocument:
    """Tests for the read_document endpoint."""

    @pytest.mark.asyncio
    async def test_read_document_not_found(self):
        """Test reading non-existent document."""
        mock_session = AsyncMock()
        mock_user = MagicMock()
        mock_user.id = "user-123"
        
        # Mock empty result
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.first.return_value = None
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute = AsyncMock(return_value=mock_result)
        
        with pytest.raises(HTTPException) as exc_info:
            await read_document(
                document_id=999,
                session=mock_session,
                user=mock_user,
            )
        
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_read_document_success(self):
        """Test successful document reading."""
        from datetime import datetime
        
        mock_session = AsyncMock()
        mock_user = MagicMock()
        mock_user.id = "user-123"
        
        # Mock existing document
        mock_document = MagicMock()
        mock_document.id = 1
        mock_document.title = "Test Document"
        mock_document.document_type = DocumentType.FILE
        mock_document.document_metadata = {}
        mock_document.content = "Test content"
        mock_document.created_at = datetime.now()  # Must be a datetime
        mock_document.search_space_id = 1
        
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.first.return_value = mock_document
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute = AsyncMock(return_value=mock_result)
        
        with patch("app.routes.documents_routes.check_permission") as mock_check:
            mock_check.return_value = None
            
            result = await read_document(
                document_id=1,
                session=mock_session,
                user=mock_user,
            )
            
            assert result.id == 1
            assert result.title == "Test Document"


class TestUpdateDocument:
    """Tests for the update_document endpoint."""

    @pytest.mark.asyncio
    async def test_update_document_not_found(self):
        """Test updating non-existent document."""
        mock_session = AsyncMock()
        mock_user = MagicMock()
        mock_user.id = "user-123"
        
        # Mock empty result
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.first.return_value = None
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.rollback = AsyncMock()
        
        # DocumentUpdate requires document_type, content, and search_space_id
        update_data = DocumentUpdate(
            document_type=DocumentType.FILE,
            content="Updated content",
            search_space_id=1
        )
        
        with pytest.raises(HTTPException) as exc_info:
            await update_document(
                document_id=999,
                document_update=update_data,
                session=mock_session,
                user=mock_user,
            )
        
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_update_document_success(self):
        """Test successful document update."""
        from datetime import datetime
        
        mock_session = AsyncMock()
        mock_user = MagicMock()
        mock_user.id = "user-123"
        
        # Mock existing document
        mock_document = MagicMock()
        mock_document.id = 1
        mock_document.title = "Old Title"
        mock_document.document_type = DocumentType.FILE
        mock_document.document_metadata = {}
        mock_document.content = "Test content"
        mock_document.created_at = datetime.now()
        mock_document.search_space_id = 1
        
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.first.return_value = mock_document
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.commit = AsyncMock()
        mock_session.refresh = AsyncMock()
        
        # DocumentUpdate requires document_type, content, and search_space_id
        update_data = DocumentUpdate(
            document_type=DocumentType.FILE,
            content="New content",
            search_space_id=1
        )
        
        with patch("app.routes.documents_routes.check_permission") as mock_check:
            mock_check.return_value = None
            
            _result = await update_document(
                document_id=1,
                document_update=update_data,
                session=mock_session,
                user=mock_user,
            )
            
            assert mock_session.commit.called


class TestDeleteDocument:
    """Tests for the delete_document endpoint."""

    @pytest.mark.asyncio
    async def test_delete_document_not_found(self):
        """Test deleting non-existent document."""
        mock_session = AsyncMock()
        mock_user = MagicMock()
        mock_user.id = "user-123"
        
        # Mock empty result
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.first.return_value = None
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.rollback = AsyncMock()
        
        with pytest.raises(HTTPException) as exc_info:
            await delete_document(
                document_id=999,
                session=mock_session,
                user=mock_user,
            )
        
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_document_success(self):
        """Test successful document deletion."""
        mock_session = AsyncMock()
        mock_user = MagicMock()
        mock_user.id = "user-123"
        
        # Mock existing document
        mock_document = MagicMock()
        mock_document.id = 1
        mock_document.search_space_id = 1
        
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.first.return_value = mock_document
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.delete = AsyncMock()
        mock_session.commit = AsyncMock()
        
        with patch("app.routes.documents_routes.check_permission") as mock_check:
            mock_check.return_value = None
            
            result = await delete_document(
                document_id=1,
                session=mock_session,
                user=mock_user,
            )
            
            assert result["message"] == "Document deleted successfully"
            assert mock_session.delete.called


class TestGetDocumentTypeCounts:
    """Tests for the get_document_type_counts endpoint."""

    @pytest.mark.asyncio
    async def test_get_document_type_counts_success(self):
        """Test getting document type counts."""
        mock_session = AsyncMock()
        mock_user = MagicMock()
        mock_user.id = "user-123"
        
        # Mock query result
        mock_result = MagicMock()
        mock_result.all.return_value = [("FILE", 5), ("EXTENSION", 3)]
        mock_session.execute = AsyncMock(return_value=mock_result)
        
        with patch("app.routes.documents_routes.check_permission") as mock_check:
            mock_check.return_value = None
            
            result = await get_document_type_counts(
                search_space_id=1,
                session=mock_session,
                user=mock_user,
            )
            
            assert result == {"FILE": 5, "EXTENSION": 3}


class TestGetDocumentByChunkId:
    """Tests for the get_document_by_chunk_id endpoint."""

    @pytest.mark.asyncio
    async def test_get_document_by_chunk_id_chunk_not_found(self):
        """Test getting document when chunk doesn't exist."""
        mock_session = AsyncMock()
        mock_user = MagicMock()
        mock_user.id = "user-123"
        
        # Mock empty chunk result
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.first.return_value = None
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute = AsyncMock(return_value=mock_result)
        
        with pytest.raises(HTTPException) as exc_info:
            await get_document_by_chunk_id(
                chunk_id=999,
                session=mock_session,
                user=mock_user,
            )
        
        assert exc_info.value.status_code == 404
        assert "Chunk" in exc_info.value.detail
