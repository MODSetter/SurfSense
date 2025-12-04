"""
Tests for document_converters utility module.

This module tests the document conversion functions including
content hash generation, markdown conversion, and chunking utilities.
"""

import hashlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.db import DocumentType
from app.utils.document_converters import (
    convert_chunks_to_langchain_documents,
    convert_document_to_markdown,
    convert_element_to_markdown,
    generate_content_hash,
    generate_unique_identifier_hash,
)


class TestGenerateContentHash:
    """Tests for generate_content_hash function."""

    def test_generates_sha256_hash(self):
        """Test that function generates SHA-256 hash."""
        content = "Test content"
        search_space_id = 1
        result = generate_content_hash(content, search_space_id)
        
        # Verify it's a valid SHA-256 hash (64 hex characters)
        assert len(result) == 64
        assert all(c in "0123456789abcdef" for c in result)

    def test_combines_content_and_search_space_id(self):
        """Test that hash is generated from combined data."""
        content = "Test content"
        search_space_id = 1
        
        # Manually compute expected hash
        combined_data = f"{search_space_id}:{content}"
        expected_hash = hashlib.sha256(combined_data.encode("utf-8")).hexdigest()
        
        result = generate_content_hash(content, search_space_id)
        assert result == expected_hash

    def test_different_content_produces_different_hash(self):
        """Test that different content produces different hashes."""
        hash1 = generate_content_hash("Content 1", 1)
        hash2 = generate_content_hash("Content 2", 1)
        assert hash1 != hash2

    def test_different_search_space_produces_different_hash(self):
        """Test that different search space ID produces different hashes."""
        hash1 = generate_content_hash("Same content", 1)
        hash2 = generate_content_hash("Same content", 2)
        assert hash1 != hash2

    def test_same_input_produces_same_hash(self):
        """Test that same input always produces same hash."""
        content = "Consistent content"
        search_space_id = 42
        
        hash1 = generate_content_hash(content, search_space_id)
        hash2 = generate_content_hash(content, search_space_id)
        assert hash1 == hash2

    def test_empty_content(self):
        """Test with empty content."""
        result = generate_content_hash("", 1)
        assert len(result) == 64  # Still produces valid hash

    def test_unicode_content(self):
        """Test with unicode content."""
        result = generate_content_hash("こんにちは世界 🌍", 1)
        assert len(result) == 64


class TestGenerateUniqueIdentifierHash:
    """Tests for generate_unique_identifier_hash function."""

    def test_generates_sha256_hash(self):
        """Test that function generates SHA-256 hash."""
        result = generate_unique_identifier_hash(
            DocumentType.SLACK_CONNECTOR,
            "message123",
            1,
        )
        assert len(result) == 64
        assert all(c in "0123456789abcdef" for c in result)

    def test_combines_all_parameters(self):
        """Test that hash is generated from all parameters."""
        doc_type = DocumentType.SLACK_CONNECTOR
        unique_id = "message123"
        search_space_id = 42
        
        # Manually compute expected hash
        combined_data = f"{doc_type.value}:{unique_id}:{search_space_id}"
        expected_hash = hashlib.sha256(combined_data.encode("utf-8")).hexdigest()
        
        result = generate_unique_identifier_hash(doc_type, unique_id, search_space_id)
        assert result == expected_hash

    def test_different_document_types_produce_different_hashes(self):
        """Test different document types produce different hashes."""
        hash1 = generate_unique_identifier_hash(DocumentType.SLACK_CONNECTOR, "id123", 1)
        hash2 = generate_unique_identifier_hash(DocumentType.NOTION_CONNECTOR, "id123", 1)
        assert hash1 != hash2

    def test_different_identifiers_produce_different_hashes(self):
        """Test different identifiers produce different hashes."""
        hash1 = generate_unique_identifier_hash(DocumentType.SLACK_CONNECTOR, "id123", 1)
        hash2 = generate_unique_identifier_hash(DocumentType.SLACK_CONNECTOR, "id456", 1)
        assert hash1 != hash2

    def test_integer_identifier(self):
        """Test with integer unique identifier."""
        result = generate_unique_identifier_hash(DocumentType.JIRA_CONNECTOR, 12345, 1)
        assert len(result) == 64

    def test_float_identifier(self):
        """Test with float unique identifier (e.g., Slack timestamps)."""
        result = generate_unique_identifier_hash(
            DocumentType.SLACK_CONNECTOR,
            1234567890.123456,
            1,
        )
        assert len(result) == 64

    def test_consistency(self):
        """Test that same inputs always produce same hash."""
        params = (DocumentType.GITHUB_CONNECTOR, "pr-123", 5)
        
        hash1 = generate_unique_identifier_hash(*params)
        hash2 = generate_unique_identifier_hash(*params)
        assert hash1 == hash2


class TestConvertElementToMarkdown:
    """Tests for convert_element_to_markdown function."""

    @pytest.mark.asyncio
    async def test_formula_element(self):
        """Test Formula element conversion."""
        element = MagicMock()
        element.metadata = {"category": "Formula"}
        element.page_content = "E = mc^2"
        
        result = await convert_element_to_markdown(element)
        assert "```math" in result
        assert "E = mc^2" in result

    @pytest.mark.asyncio
    async def test_figure_caption_element(self):
        """Test FigureCaption element conversion."""
        element = MagicMock()
        element.metadata = {"category": "FigureCaption"}
        element.page_content = "Figure 1: Test image"
        
        result = await convert_element_to_markdown(element)
        assert "*Figure:" in result

    @pytest.mark.asyncio
    async def test_narrative_text_element(self):
        """Test NarrativeText element conversion."""
        element = MagicMock()
        element.metadata = {"category": "NarrativeText"}
        element.page_content = "This is a paragraph of text."
        
        result = await convert_element_to_markdown(element)
        assert "This is a paragraph of text." in result
        assert result.endswith("\n\n")

    @pytest.mark.asyncio
    async def test_list_item_element(self):
        """Test ListItem element conversion."""
        element = MagicMock()
        element.metadata = {"category": "ListItem"}
        element.page_content = "Item one"
        
        result = await convert_element_to_markdown(element)
        assert result.startswith("- ")
        assert "Item one" in result

    @pytest.mark.asyncio
    async def test_title_element(self):
        """Test Title element conversion."""
        element = MagicMock()
        element.metadata = {"category": "Title"}
        element.page_content = "Document Title"
        
        result = await convert_element_to_markdown(element)
        assert result.startswith("# ")
        assert "Document Title" in result

    @pytest.mark.asyncio
    async def test_address_element(self):
        """Test Address element conversion."""
        element = MagicMock()
        element.metadata = {"category": "Address"}
        element.page_content = "123 Main St"
        
        result = await convert_element_to_markdown(element)
        assert result.startswith("> ")

    @pytest.mark.asyncio
    async def test_email_address_element(self):
        """Test EmailAddress element conversion."""
        element = MagicMock()
        element.metadata = {"category": "EmailAddress"}
        element.page_content = "test@example.com"
        
        result = await convert_element_to_markdown(element)
        assert "`test@example.com`" in result

    @pytest.mark.asyncio
    async def test_table_element(self):
        """Test Table element conversion."""
        element = MagicMock()
        element.metadata = {"category": "Table", "text_as_html": "<table><tr><td>data</td></tr></table>"}
        element.page_content = "Table content"
        
        result = await convert_element_to_markdown(element)
        assert "```html" in result
        assert "<table>" in result

    @pytest.mark.asyncio
    async def test_header_element(self):
        """Test Header element conversion."""
        element = MagicMock()
        element.metadata = {"category": "Header"}
        element.page_content = "Section Header"
        
        result = await convert_element_to_markdown(element)
        assert result.startswith("## ")

    @pytest.mark.asyncio
    async def test_code_snippet_element(self):
        """Test CodeSnippet element conversion."""
        element = MagicMock()
        element.metadata = {"category": "CodeSnippet"}
        element.page_content = "print('hello')"
        
        result = await convert_element_to_markdown(element)
        assert "```" in result
        assert "print('hello')" in result

    @pytest.mark.asyncio
    async def test_page_number_element(self):
        """Test PageNumber element conversion."""
        element = MagicMock()
        element.metadata = {"category": "PageNumber"}
        element.page_content = "42"
        
        result = await convert_element_to_markdown(element)
        assert "*Page 42*" in result

    @pytest.mark.asyncio
    async def test_page_break_element(self):
        """Test PageBreak element conversion."""
        element = MagicMock()
        element.metadata = {"category": "PageBreak"}
        # PageBreak with content returns horizontal rule
        element.page_content = "page break content"
        
        result = await convert_element_to_markdown(element)
        assert "---" in result

    @pytest.mark.asyncio
    async def test_empty_content(self):
        """Test element with empty content."""
        element = MagicMock()
        element.metadata = {"category": "NarrativeText"}
        element.page_content = ""
        
        result = await convert_element_to_markdown(element)
        assert result == ""

    @pytest.mark.asyncio
    async def test_uncategorized_element(self):
        """Test UncategorizedText element conversion."""
        element = MagicMock()
        element.metadata = {"category": "UncategorizedText"}
        element.page_content = "Some uncategorized text"
        
        result = await convert_element_to_markdown(element)
        assert "Some uncategorized text" in result


class TestConvertDocumentToMarkdown:
    """Tests for convert_document_to_markdown function."""

    @pytest.mark.asyncio
    async def test_converts_multiple_elements(self):
        """Test converting multiple elements."""
        elements = []
        
        # Title element
        title = MagicMock()
        title.metadata = {"category": "Title"}
        title.page_content = "Document Title"
        elements.append(title)
        
        # Narrative text element
        para = MagicMock()
        para.metadata = {"category": "NarrativeText"}
        para.page_content = "This is a paragraph."
        elements.append(para)
        
        result = await convert_document_to_markdown(elements)
        
        assert "# Document Title" in result
        assert "This is a paragraph." in result

    @pytest.mark.asyncio
    async def test_empty_elements(self):
        """Test with empty elements list."""
        result = await convert_document_to_markdown([])
        assert result == ""

    @pytest.mark.asyncio
    async def test_preserves_order(self):
        """Test that element order is preserved."""
        elements = []
        
        for i in range(3):
            elem = MagicMock()
            elem.metadata = {"category": "NarrativeText"}
            elem.page_content = f"Paragraph {i}"
            elements.append(elem)
        
        result = await convert_document_to_markdown(elements)
        
        # Check order is preserved
        pos0 = result.find("Paragraph 0")
        pos1 = result.find("Paragraph 1")
        pos2 = result.find("Paragraph 2")
        
        assert pos0 < pos1 < pos2


class TestConvertChunksToLangchainDocuments:
    """Tests for convert_chunks_to_langchain_documents function."""

    def test_converts_basic_chunks(self):
        """Test converting basic chunk structure."""
        chunks = [
            {
                "chunk_id": 1,
                "content": "This is chunk content",
                "score": 0.95,
                "document": {
                    "id": 10,
                    "title": "Test Document",
                    "document_type": "FILE",
                    "metadata": {"url": "https://example.com"},
                },
            }
        ]
        
        result = convert_chunks_to_langchain_documents(chunks)
        
        assert len(result) == 1
        assert "This is chunk content" in result[0].page_content
        assert result[0].metadata["chunk_id"] == 1
        assert result[0].metadata["document_id"] == 10
        assert result[0].metadata["document_title"] == "Test Document"

    def test_includes_source_id_in_content(self):
        """Test that source_id is included in XML content."""
        chunks = [
            {
                "chunk_id": 1,
                "content": "Test content",
                "score": 0.9,
                "document": {
                    "id": 5,
                    "title": "Doc",
                    "document_type": "FILE",
                    "metadata": {},
                },
            }
        ]
        
        result = convert_chunks_to_langchain_documents(chunks)
        
        assert "<source_id>5</source_id>" in result[0].page_content

    def test_extracts_source_url(self):
        """Test source URL extraction from metadata."""
        chunks = [
            {
                "chunk_id": 1,
                "content": "Content",
                "score": 0.9,
                "document": {
                    "id": 1,
                    "title": "Doc",
                    "document_type": "CRAWLED_URL",
                    "metadata": {"url": "https://example.com/page"},
                },
            }
        ]
        
        result = convert_chunks_to_langchain_documents(chunks)
        
        assert result[0].metadata["source"] == "https://example.com/page"

    def test_extracts_source_url_alternate_key(self):
        """Test source URL extraction with sourceURL key."""
        chunks = [
            {
                "chunk_id": 1,
                "content": "Content",
                "score": 0.9,
                "document": {
                    "id": 1,
                    "title": "Doc",
                    "document_type": "CRAWLED_URL",
                    "metadata": {"sourceURL": "https://example.com/alternate"},
                },
            }
        ]
        
        result = convert_chunks_to_langchain_documents(chunks)
        
        assert result[0].metadata["source"] == "https://example.com/alternate"

    def test_handles_missing_document(self):
        """Test handling chunks without document info."""
        chunks = [
            {
                "chunk_id": 1,
                "content": "Content without document",
                "score": 0.8,
            }
        ]
        
        result = convert_chunks_to_langchain_documents(chunks)
        
        assert len(result) == 1
        assert "Content without document" in result[0].page_content

    def test_prefixes_document_metadata(self):
        """Test document metadata is prefixed."""
        chunks = [
            {
                "chunk_id": 1,
                "content": "Content",
                "score": 0.9,
                "document": {
                    "id": 1,
                    "title": "Doc",
                    "document_type": "FILE",
                    "metadata": {"custom_field": "custom_value"},
                },
            }
        ]
        
        result = convert_chunks_to_langchain_documents(chunks)
        
        assert result[0].metadata["doc_meta_custom_field"] == "custom_value"

    def test_handles_rank_field(self):
        """Test handling of rank field when present."""
        chunks = [
            {
                "chunk_id": 1,
                "content": "Content",
                "score": 0.9,
                "rank": 1,
                "document": {
                    "id": 1,
                    "title": "Doc",
                    "document_type": "FILE",
                    "metadata": {},
                },
            }
        ]
        
        result = convert_chunks_to_langchain_documents(chunks)
        
        assert result[0].metadata["rank"] == 1

    def test_empty_chunks_list(self):
        """Test with empty chunks list."""
        result = convert_chunks_to_langchain_documents([])
        assert result == []

    def test_multiple_chunks(self):
        """Test converting multiple chunks."""
        chunks = [
            {
                "chunk_id": i,
                "content": f"Content {i}",
                "score": 0.9 - (i * 0.1),
                "document": {
                    "id": i,
                    "title": f"Doc {i}",
                    "document_type": "FILE",
                    "metadata": {},
                },
            }
            for i in range(3)
        ]
        
        result = convert_chunks_to_langchain_documents(chunks)
        
        assert len(result) == 3
        for i, doc in enumerate(result):
            assert f"Content {i}" in doc.page_content
