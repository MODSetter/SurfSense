"""
Tests for the blocknote_converter utility module.

These tests validate:
1. Empty/invalid input is handled gracefully (returns None, not crash)
2. API failures don't crash the application
3. Response structure is correctly parsed
4. Network errors are properly handled
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import httpx

# Skip these tests if app dependencies aren't installed
pytest.importorskip("yaml")

from app.utils.blocknote_converter import (
    convert_markdown_to_blocknote,
    convert_blocknote_to_markdown,
)


class TestMarkdownToBlocknoteInputValidation:
    """
    Tests validating input handling for markdown to BlockNote conversion.
    """

    @pytest.mark.asyncio
    async def test_empty_string_returns_none(self):
        """
        Empty markdown must return None, not error.
        This is a common edge case when content hasn't been written yet.
        """
        result = await convert_markdown_to_blocknote("")
        assert result is None

    @pytest.mark.asyncio
    async def test_whitespace_only_returns_none(self):
        """
        Whitespace-only content should be treated as empty.
        Spaces, tabs, newlines alone don't constitute content.
        """
        test_cases = ["   ", "\t\t", "\n\n", "  \n  \t  "]

        for whitespace in test_cases:
            result = await convert_markdown_to_blocknote(whitespace)
            assert result is None, f"Expected None for whitespace: {repr(whitespace)}"

    @pytest.mark.asyncio
    async def test_very_short_content_returns_fallback(self):
        """
        Very short content should return a fallback document.
        Content too short to convert meaningfully should still return something.
        """
        result = await convert_markdown_to_blocknote("x")

        assert result is not None
        assert isinstance(result, list)
        assert len(result) > 0
        # Fallback document should be a paragraph
        assert result[0]["type"] == "paragraph"


class TestMarkdownToBlocknoteNetworkResilience:
    """
    Tests validating network error handling.
    The converter should never crash on network issues.
    """

    @pytest.mark.asyncio
    @patch("app.utils.blocknote_converter.httpx.AsyncClient")
    @patch("app.utils.blocknote_converter.config")
    async def test_timeout_returns_none_not_exception(
        self, mock_config, mock_client_class
    ):
        """
        Network timeout must return None, not raise exception.
        Timeouts are common and shouldn't crash the application.
        """
        mock_config.NEXT_FRONTEND_URL = "http://localhost:3000"

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("Timeout"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()
        mock_client_class.return_value = mock_client

        # Long enough content to trigger API call
        result = await convert_markdown_to_blocknote(
            "# Heading\n\nThis is a paragraph with enough content."
        )

        assert result is None  # Not an exception

    @pytest.mark.asyncio
    @patch("app.utils.blocknote_converter.httpx.AsyncClient")
    @patch("app.utils.blocknote_converter.config")
    async def test_server_error_returns_none_not_exception(
        self, mock_config, mock_client_class
    ):
        """
        HTTP 5xx errors must return None, not raise exception.
        Server errors shouldn't crash the caller.
        """
        mock_config.NEXT_FRONTEND_URL = "http://localhost:3000"

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(
            side_effect=httpx.HTTPStatusError(
                "Server error",
                request=MagicMock(),
                response=mock_response,
            )
        )
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()
        mock_client_class.return_value = mock_client

        result = await convert_markdown_to_blocknote(
            "# Heading\n\nThis is a paragraph with enough content."
        )

        assert result is None

    @pytest.mark.asyncio
    @patch("app.utils.blocknote_converter.httpx.AsyncClient")
    @patch("app.utils.blocknote_converter.config")
    async def test_connection_error_returns_none(self, mock_config, mock_client_class):
        """
        Connection errors (server unreachable) must return None.
        """
        mock_config.NEXT_FRONTEND_URL = "http://localhost:3000"

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()
        mock_client_class.return_value = mock_client

        result = await convert_markdown_to_blocknote(
            "# Heading\n\nThis is a paragraph with enough content."
        )

        assert result is None


class TestMarkdownToBlocknoteSuccessfulConversion:
    """
    Tests for successful conversion scenarios.
    """

    @pytest.mark.asyncio
    @patch("app.utils.blocknote_converter.httpx.AsyncClient")
    @patch("app.utils.blocknote_converter.config")
    async def test_successful_conversion_returns_document(
        self, mock_config, mock_client_class
    ):
        """
        Successful API response should return the BlockNote document.
        """
        mock_config.NEXT_FRONTEND_URL = "http://localhost:3000"

        expected_document = [{"type": "paragraph", "content": [{"text": "Test"}]}]

        mock_response = MagicMock()
        mock_response.json.return_value = {"blocknote_document": expected_document}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()
        mock_client_class.return_value = mock_client

        result = await convert_markdown_to_blocknote(
            "# This is a heading\n\nThis is a paragraph with enough content."
        )

        assert result == expected_document

    @pytest.mark.asyncio
    @patch("app.utils.blocknote_converter.httpx.AsyncClient")
    @patch("app.utils.blocknote_converter.config")
    async def test_empty_api_response_returns_none(
        self, mock_config, mock_client_class
    ):
        """
        If API returns null/empty document, function should return None.
        """
        mock_config.NEXT_FRONTEND_URL = "http://localhost:3000"

        mock_response = MagicMock()
        mock_response.json.return_value = {"blocknote_document": None}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()
        mock_client_class.return_value = mock_client

        result = await convert_markdown_to_blocknote(
            "# Heading\n\nSome content that is long enough."
        )

        assert result is None


class TestBlocknoteToMarkdownInputValidation:
    """
    Tests validating input handling for BlockNote to markdown conversion.
    """

    @pytest.mark.asyncio
    async def test_none_document_returns_none(self):
        """None input must return None, not crash."""
        result = await convert_blocknote_to_markdown(None)
        assert result is None

    @pytest.mark.asyncio
    async def test_empty_dict_returns_none(self):
        """Empty dict should be treated as no content."""
        result = await convert_blocknote_to_markdown({})
        assert result is None

    @pytest.mark.asyncio
    async def test_empty_list_returns_none(self):
        """Empty list should be treated as no content."""
        result = await convert_blocknote_to_markdown([])
        assert result is None


class TestBlocknoteToMarkdownNetworkResilience:
    """
    Tests validating network error handling for BlockNote to markdown.
    """

    @pytest.mark.asyncio
    @patch("app.utils.blocknote_converter.httpx.AsyncClient")
    @patch("app.utils.blocknote_converter.config")
    async def test_timeout_returns_none(self, mock_config, mock_client_class):
        """Timeout must return None, not exception."""
        mock_config.NEXT_FRONTEND_URL = "http://localhost:3000"

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("Timeout"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()
        mock_client_class.return_value = mock_client

        blocknote_doc = [{"type": "paragraph", "content": []}]
        result = await convert_blocknote_to_markdown(blocknote_doc)

        assert result is None

    @pytest.mark.asyncio
    @patch("app.utils.blocknote_converter.httpx.AsyncClient")
    @patch("app.utils.blocknote_converter.config")
    async def test_server_error_returns_none(self, mock_config, mock_client_class):
        """HTTP errors must return None, not exception."""
        mock_config.NEXT_FRONTEND_URL = "http://localhost:3000"

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(
            side_effect=httpx.HTTPStatusError(
                "Server error",
                request=MagicMock(),
                response=mock_response,
            )
        )
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()
        mock_client_class.return_value = mock_client

        blocknote_doc = [{"type": "paragraph", "content": []}]
        result = await convert_blocknote_to_markdown(blocknote_doc)

        assert result is None


class TestBlocknoteToMarkdownSuccessfulConversion:
    """
    Tests for successful BlockNote to markdown conversion.
    """

    @pytest.mark.asyncio
    @patch("app.utils.blocknote_converter.httpx.AsyncClient")
    @patch("app.utils.blocknote_converter.config")
    async def test_successful_conversion_returns_markdown(
        self, mock_config, mock_client_class
    ):
        """Successful conversion should return markdown string."""
        mock_config.NEXT_FRONTEND_URL = "http://localhost:3000"

        expected_markdown = "# Converted Heading\n\nParagraph text."

        mock_response = MagicMock()
        mock_response.json.return_value = {"markdown": expected_markdown}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()
        mock_client_class.return_value = mock_client

        blocknote_doc = [
            {"type": "heading", "content": [{"type": "text", "text": "Test"}]}
        ]
        result = await convert_blocknote_to_markdown(blocknote_doc)

        assert result == expected_markdown

    @pytest.mark.asyncio
    @patch("app.utils.blocknote_converter.httpx.AsyncClient")
    @patch("app.utils.blocknote_converter.config")
    async def test_null_markdown_response_returns_none(
        self, mock_config, mock_client_class
    ):
        """If API returns null markdown, function should return None."""
        mock_config.NEXT_FRONTEND_URL = "http://localhost:3000"

        mock_response = MagicMock()
        mock_response.json.return_value = {"markdown": None}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()
        mock_client_class.return_value = mock_client

        blocknote_doc = [{"type": "paragraph", "content": []}]
        result = await convert_blocknote_to_markdown(blocknote_doc)

        assert result is None

    @pytest.mark.asyncio
    @patch("app.utils.blocknote_converter.httpx.AsyncClient")
    @patch("app.utils.blocknote_converter.config")
    async def test_list_document_is_handled(self, mock_config, mock_client_class):
        """
        List documents (multiple blocks) should be handled correctly.
        """
        mock_config.NEXT_FRONTEND_URL = "http://localhost:3000"

        expected_markdown = "- Item 1\n- Item 2"

        mock_response = MagicMock()
        mock_response.json.return_value = {"markdown": expected_markdown}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()
        mock_client_class.return_value = mock_client

        blocknote_doc = [
            {
                "type": "bulletListItem",
                "content": [{"type": "text", "text": "Item 1"}],
            },
            {
                "type": "bulletListItem",
                "content": [{"type": "text", "text": "Item 2"}],
            },
        ]
        result = await convert_blocknote_to_markdown(blocknote_doc)

        assert result == expected_markdown
