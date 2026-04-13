"""Unit tests for DexScreener connector."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import httpx

from app.connectors.dexscreener_connector import DexScreenerConnector


class TestDexScreenerConnector:
    """Test cases for DexScreenerConnector class."""

    def test_init_creates_connector(self):
        """Test that connector initializes correctly."""
        connector = DexScreenerConnector()
        assert connector.base_url == "https://api.dexscreener.com/latest/dex"
        assert connector.rate_limit_delay == 0.2

    @pytest.mark.asyncio
    async def test_make_request_success(self, mock_pair_data):
        """Test successful API request."""
        connector = DexScreenerConnector()

        with patch("httpx.AsyncClient.get") as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_pair_data
            mock_get.return_value = mock_response

            result = await connector.make_request("/dex/tokens/ethereum/0x123")

            assert result == mock_pair_data
            mock_get.assert_called_once()

    @pytest.mark.asyncio
    async def test_make_request_with_retry_on_429(self, mock_pair_data):
        """Test that connector retries on rate limit (429)."""
        connector = DexScreenerConnector()

        with patch("httpx.AsyncClient.get") as mock_get:
            # First call returns 429, second call succeeds
            mock_response_429 = MagicMock()
            mock_response_429.status_code = 429

            mock_response_200 = MagicMock()
            mock_response_200.status_code = 200
            mock_response_200.json.return_value = mock_pair_data

            # Mock the responses
            mock_get.side_effect = [mock_response_429, mock_response_200]

            with patch("asyncio.sleep", return_value=None):  # Skip actual sleep
                result = await connector.make_request("/dex/tokens/ethereum/0x123")

            assert result == mock_pair_data
            assert mock_get.call_count == 2

    @pytest.mark.asyncio
    async def test_make_request_timeout(self):
        """Test that connector handles timeout errors."""
        connector = DexScreenerConnector()

        with patch("httpx.AsyncClient.get") as mock_get:
            mock_get.side_effect = httpx.TimeoutException("Request timeout")

            with pytest.raises(Exception, match="Request timeout"):
                await connector.make_request("/dex/tokens/ethereum/0x123")

    @pytest.mark.asyncio
    async def test_make_request_network_error(self):
        """Test that connector handles network errors."""
        connector = DexScreenerConnector()

        with patch("httpx.AsyncClient.get") as mock_get:
            mock_get.side_effect = httpx.NetworkError("Network error")

            with pytest.raises(Exception, match="Network error"):
                await connector.make_request("/dex/tokens/ethereum/0x123")

    @pytest.mark.asyncio
    async def test_get_token_pairs_success(self, mock_pair_data):
        """Test successful token pairs retrieval."""
        connector = DexScreenerConnector()

        # get_token_pairs returns a tuple (pairs, error)
        with patch.object(
            connector, "make_request", return_value=mock_pair_data
        ) as mock_request:
            pairs, error = await connector.get_token_pairs("ethereum", "0x123")

            assert pairs == mock_pair_data["pairs"]
            assert error is None
            mock_request.assert_called_once_with("tokens/ethereum/0x123")

    @pytest.mark.asyncio
    async def test_get_token_pairs_no_data(self):
        """Test handling of empty response."""
        connector = DexScreenerConnector()

        with patch.object(connector, "make_request", return_value={"pairs": None}):
            pairs, error = await connector.get_token_pairs("ethereum", "0x123")

            assert pairs == []
            assert error is not None

    def test_format_pair_to_markdown(self, mock_pair_data):
        """Test markdown formatting of pair data."""
        connector = DexScreenerConnector()
        pair = mock_pair_data["pairs"][0]

        markdown = connector.format_pair_to_markdown(pair, "WETH")

        # Verify key sections are present (actual format is "# WETH/USDC Trading Pair")
        assert "# WETH/USDC Trading Pair" in markdown
        assert "## Price Information" in markdown
        assert "## Trading Volume" in markdown
        assert "## Market Metrics" in markdown  # New section
        assert "## Liquidity" in markdown
        assert "## Transactions (24h)" in markdown
        assert "WETH" in markdown
        assert "USD Coin" in markdown or "USDC" in markdown
        assert "$2500.00" in markdown
        # Verify new metrics are present
        assert "6h Volume" in markdown
        assert "1h Volume" in markdown
        assert "Market Cap" in markdown
        assert "FDV (Fully Diluted Valuation)" in markdown

    def test_format_pair_to_markdown_missing_fields(self):
        """Test markdown formatting with missing optional fields."""
        connector = DexScreenerConnector()
        minimal_pair = {
            "chainId": "ethereum",
            "dexId": "uniswap",
            "pairAddress": "0x123",
            "baseToken": {"symbol": "WETH", "name": "Wrapped Ether"},
            "quoteToken": {"symbol": "USDC", "name": "USD Coin"},
        }

        markdown = connector.format_pair_to_markdown(minimal_pair, "WETH")

        # Should handle missing fields gracefully (actual format is "# WETH/USDC Trading Pair")
        assert "# WETH/USDC Trading Pair" in markdown
        assert "WETH" in markdown
        assert "N/A" in markdown

    @pytest.mark.asyncio
    async def test_rate_limit_delay(self):
        """Test rate limiting delay calculation."""
        connector = DexScreenerConnector()

        # Simulate rapid requests
        import time

        connector.last_request_time = time.time()

        with patch("asyncio.sleep") as mock_sleep:
            await connector._rate_limit_delay()
            # Should call sleep since last request was recent
            assert mock_sleep.called
