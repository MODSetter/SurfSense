"""
Tests for PageLimitService.

This module tests the page limit service used for tracking user document processing limits.
"""

import os
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.page_limit_service import PageLimitExceededError, PageLimitService


class TestPageLimitExceededError:
    """Tests for PageLimitExceededError exception."""

    def test_default_message(self):
        """Test default error message."""
        error = PageLimitExceededError()
        assert "Page limit exceeded" in str(error)

    def test_custom_message(self):
        """Test custom error message."""
        error = PageLimitExceededError(message="Custom message")
        assert str(error) == "Custom message"

    def test_stores_usage_info(self):
        """Test error stores usage information."""
        error = PageLimitExceededError(
            pages_used=100,
            pages_limit=200,
            pages_to_add=50,
        )
        assert error.pages_used == 100
        assert error.pages_limit == 200
        assert error.pages_to_add == 50

    def test_default_values(self):
        """Test default values are zero."""
        error = PageLimitExceededError()
        assert error.pages_used == 0
        assert error.pages_limit == 0
        assert error.pages_to_add == 0


class TestPageLimitServiceEstimation:
    """Tests for page estimation methods."""

    @pytest.fixture
    def service(self):
        """Create a PageLimitService with mock session."""
        mock_session = AsyncMock()
        return PageLimitService(mock_session)

    def test_estimate_pages_from_elements_with_page_numbers(self, service):
        """Test estimation from elements with page number metadata."""
        elements = []
        for page in [1, 1, 2, 2, 3]:  # 3 unique pages
            elem = MagicMock()
            elem.metadata = {"page_number": page}
            elements.append(elem)
        
        result = service.estimate_pages_from_elements(elements)
        assert result == 3

    def test_estimate_pages_from_elements_by_content_length(self, service):
        """Test estimation from elements by content length."""
        elements = []
        # Create elements with ~4000 chars total (should be 2 pages)
        for i in range(4):
            elem = MagicMock()
            elem.metadata = {}  # No page number
            elem.page_content = "x" * 1000  # 1000 chars each
            elements.append(elem)
        
        result = service.estimate_pages_from_elements(elements)
        assert result == 2  # 4000 / 2000 = 2

    def test_estimate_pages_from_elements_empty_list(self, service):
        """Test estimation from empty elements list returns minimum 1."""
        result = service.estimate_pages_from_elements([])
        # Implementation uses max(1, ...) so minimum is 1
        assert result == 1

    def test_estimate_pages_from_markdown_with_metadata(self, service):
        """Test estimation from markdown documents with page metadata."""
        docs = []
        for page in range(5):
            doc = MagicMock()
            doc.metadata = {"page": page}
            doc.text = "Content"
            docs.append(doc)
        
        result = service.estimate_pages_from_markdown(docs)
        assert result == 5

    def test_estimate_pages_from_markdown_by_content(self, service):
        """Test estimation from markdown by content length."""
        docs = []
        for i in range(2):
            doc = MagicMock()
            doc.metadata = {}
            doc.text = "x" * 4000  # 4000 chars = 2 pages each
            docs.append(doc)
        
        result = service.estimate_pages_from_markdown(docs)
        assert result == 4  # (4000/2000) * 2 = 4

    def test_estimate_pages_from_markdown_empty_list(self, service):
        """Test estimation from empty markdown list."""
        result = service.estimate_pages_from_markdown([])
        assert result == 1  # Minimum 1 page

    def test_estimate_pages_from_content_length(self, service):
        """Test estimation from content length."""
        # 5000 chars should be ~2 pages
        result = service.estimate_pages_from_content_length(5000)
        assert result == 2

    def test_estimate_pages_from_content_length_minimum(self, service):
        """Test minimum of 1 page for small content."""
        result = service.estimate_pages_from_content_length(100)
        assert result == 1

    def test_estimate_pages_from_content_length_zero(self, service):
        """Test zero content length returns 1 page."""
        result = service.estimate_pages_from_content_length(0)
        assert result == 1


class TestPageEstimationFromFile:
    """Tests for estimate_pages_before_processing method."""

    @pytest.fixture
    def service(self):
        """Create a PageLimitService with mock session."""
        mock_session = AsyncMock()
        return PageLimitService(mock_session)

    def test_file_not_found(self, service):
        """Test error when file doesn't exist."""
        with pytest.raises(ValueError, match="File not found"):
            service.estimate_pages_before_processing("/nonexistent/file.pdf")

    def test_text_file_estimation(self, service):
        """Test estimation for text files."""
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            # Write ~6000 bytes (2 pages at 3000 bytes/page)
            f.write(b"x" * 6000)
            f.flush()
            
            try:
                result = service.estimate_pages_before_processing(f.name)
                assert result == 2
            finally:
                os.unlink(f.name)

    def test_small_text_file(self, service):
        """Test minimum 1 page for small files."""
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            f.write(b"small")
            f.flush()
            
            try:
                result = service.estimate_pages_before_processing(f.name)
                assert result == 1
            finally:
                os.unlink(f.name)

    def test_markdown_file_estimation(self, service):
        """Test estimation for markdown files."""
        with tempfile.NamedTemporaryFile(suffix=".md", delete=False) as f:
            # Need at least 6000 bytes for 2 pages (3000 bytes per page)
            f.write(b"# Title\n" + b"x" * 6000)
            f.flush()
            
            try:
                result = service.estimate_pages_before_processing(f.name)
                assert result == 2
            finally:
                os.unlink(f.name)

    def test_image_file_estimation(self, service):
        """Test image files return 1 page."""
        for ext in [".jpg", ".png", ".gif", ".bmp"]:
            with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as f:
                f.write(b"fake image data" * 1000)
                f.flush()
                
                try:
                    result = service.estimate_pages_before_processing(f.name)
                    assert result == 1, f"Expected 1 page for {ext}"
                finally:
                    os.unlink(f.name)

    def test_word_doc_estimation(self, service):
        """Test estimation for Word documents."""
        with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
            # Write ~100KB (2 pages at 50KB/page)
            f.write(b"x" * (100 * 1024))
            f.flush()
            
            try:
                result = service.estimate_pages_before_processing(f.name)
                assert result == 2
            finally:
                os.unlink(f.name)

    def test_presentation_estimation(self, service):
        """Test estimation for presentation files."""
        with tempfile.NamedTemporaryFile(suffix=".pptx", delete=False) as f:
            # Write ~400KB (2 slides at 200KB/slide)
            f.write(b"x" * (400 * 1024))
            f.flush()
            
            try:
                result = service.estimate_pages_before_processing(f.name)
                assert result == 2
            finally:
                os.unlink(f.name)

    def test_spreadsheet_estimation(self, service):
        """Test estimation for spreadsheet files."""
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
            # Write ~200KB (2 sheets at 100KB/sheet)
            f.write(b"x" * (200 * 1024))
            f.flush()
            
            try:
                result = service.estimate_pages_before_processing(f.name)
                assert result == 2
            finally:
                os.unlink(f.name)

    def test_html_file_estimation(self, service):
        """Test estimation for HTML files."""
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as f:
            f.write(b"<html><body>" + b"x" * 5980 + b"</body></html>")
            f.flush()
            
            try:
                result = service.estimate_pages_before_processing(f.name)
                assert result == 2  # ~6000 / 3000 = 2
            finally:
                os.unlink(f.name)

    def test_unknown_extension(self, service):
        """Test estimation for unknown file types."""
        with tempfile.NamedTemporaryFile(suffix=".xyz", delete=False) as f:
            # Write ~160KB (2 pages at 80KB/page)
            f.write(b"x" * (160 * 1024))
            f.flush()
            
            try:
                result = service.estimate_pages_before_processing(f.name)
                assert result == 2
            finally:
                os.unlink(f.name)

    def test_pdf_estimation_fallback(self, service):
        """Test PDF estimation falls back when pypdf fails."""
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            # Write invalid PDF data (will fail to parse)
            f.write(b"not a real pdf" * 10000)  # ~140KB
            f.flush()
            
            try:
                result = service.estimate_pages_before_processing(f.name)
                # Falls back to size estimation: ~140KB / 100KB = 1 page
                assert result >= 1
            finally:
                os.unlink(f.name)


class TestPageLimitServiceDatabase:
    """Tests for database operations (mocked)."""

    @pytest.fixture
    def mock_user(self):
        """Create a mock user."""
        user = MagicMock()
        user.pages_used = 50
        user.pages_limit = 100
        return user

    @pytest.fixture
    def service(self):
        """Create a PageLimitService with mock session."""
        mock_session = AsyncMock()
        return PageLimitService(mock_session)

    @pytest.mark.asyncio
    async def test_check_page_limit_success(self, service, mock_user):
        """Test check_page_limit succeeds when within limit."""
        # Setup mock to return user data
        mock_result = MagicMock()
        mock_result.first.return_value = (50, 100)  # pages_used, pages_limit
        service.session.execute.return_value = mock_result
        
        has_capacity, pages_used, pages_limit = await service.check_page_limit(
            "user-123",
            estimated_pages=10,
        )
        
        assert has_capacity is True
        assert pages_used == 50
        assert pages_limit == 100

    @pytest.mark.asyncio
    async def test_check_page_limit_exceeds(self, service):
        """Test check_page_limit raises error when would exceed limit."""
        mock_result = MagicMock()
        mock_result.first.return_value = (95, 100)  # Near limit
        service.session.execute.return_value = mock_result
        
        with pytest.raises(PageLimitExceededError) as exc_info:
            await service.check_page_limit("user-123", estimated_pages=10)
        
        assert exc_info.value.pages_used == 95
        assert exc_info.value.pages_limit == 100
        assert exc_info.value.pages_to_add == 10

    @pytest.mark.asyncio
    async def test_check_page_limit_user_not_found(self, service):
        """Test check_page_limit raises error for missing user."""
        mock_result = MagicMock()
        mock_result.first.return_value = None
        service.session.execute.return_value = mock_result
        
        with pytest.raises(ValueError, match="User with ID .* not found"):
            await service.check_page_limit("nonexistent", estimated_pages=1)

    @pytest.mark.asyncio
    async def test_get_page_usage(self, service):
        """Test get_page_usage returns correct values."""
        mock_result = MagicMock()
        mock_result.first.return_value = (75, 500)
        service.session.execute.return_value = mock_result
        
        result = await service.get_page_usage("user-123")
        
        assert result == (75, 500)

    @pytest.mark.asyncio
    async def test_get_page_usage_user_not_found(self, service):
        """Test get_page_usage raises error for missing user."""
        mock_result = MagicMock()
        mock_result.first.return_value = None
        service.session.execute.return_value = mock_result
        
        with pytest.raises(ValueError, match="User with ID .* not found"):
            await service.get_page_usage("nonexistent")
