"""
DexScreener Connector Module

A module for retrieving cryptocurrency trading pair data from DexScreener API.
Allows fetching pair information for tracked tokens across multiple blockchain networks.
"""

import asyncio
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class DexScreenerConnector:
    """Class for retrieving trading pair data from DexScreener API."""

    def __init__(self):
        """
        Initialize the DexScreenerConnector class.
        
        Note: DexScreener API is public and doesn't require authentication.
        """
        self.base_url = "https://api.dexscreener.com"
        self.rate_limit_delay = 0.2  # 200ms delay between requests to respect rate limits
        
    async def make_request(
        self, 
        endpoint: str, 
        max_retries: int = 3
    ) -> dict[str, Any] | None:
        """
        Make an async request to the DexScreener API with retry logic.
        
        Args:
            endpoint: API endpoint path (without base URL)
            max_retries: Maximum number of retry attempts for failed requests
            
        Returns:
            Response data from the API, or None if request fails
            
        Raises:
            Exception: If the API request fails after all retries
        """
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        
        for attempt in range(max_retries):
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.get(url)
                    
                    if response.status_code == 200:
                        # Add delay to respect rate limits
                        await self._rate_limit_delay()
                        return response.json()
                    elif response.status_code == 429:
                        # Rate limit exceeded - exponential backoff
                        wait_time = (2 ** attempt) * 1.0  # 1s, 2s, 4s
                        logger.warning(f"Rate limit exceeded. Waiting {wait_time}s before retry...")
                        await asyncio.sleep(wait_time)
                        continue
                    elif response.status_code == 404:
                        # Token/pair not found - return None instead of raising
                        logger.info(f"Token not found: {endpoint}")
                        return None
                    else:
                        raise Exception(
                            f"API request failed with status code {response.status_code}: {response.text}"
                        )
                        
            except httpx.TimeoutException:
                if attempt < max_retries - 1:
                    logger.warning(f"Request timeout. Retrying... (attempt {attempt + 1}/{max_retries})")
                    continue
                else:
                    raise Exception(f"Request timeout after {max_retries} attempts")
            except httpx.RequestError as e:
                if attempt < max_retries - 1:
                    logger.warning(f"Network error: {e}. Retrying... (attempt {attempt + 1}/{max_retries})")
                    continue
                else:
                    raise Exception(f"Network error after {max_retries} attempts: {e}") from e
        
        return None
    
    async def _rate_limit_delay(self):
        """Add delay to respect API rate limits (300 req/min = ~200ms between requests)."""
        import asyncio
        await asyncio.sleep(self.rate_limit_delay)
    
    async def get_token_pairs(
        self, 
        chain_id: str, 
        token_address: str
    ) -> tuple[list[dict[str, Any]], str | None]:
        """
        Fetch all trading pairs for a specific token on a blockchain.
        
        Args:
            chain_id: Blockchain identifier (e.g., 'ethereum', 'bsc', 'polygon')
            token_address: Token contract address (0x format)
            
        Returns:
            Tuple containing (list of pairs, error message or None)
        """
        try:
            endpoint = f"token-pairs/v1/{chain_id}/{token_address}"
            response = await self.make_request(endpoint)
            
            if response is None:
                return [], f"Token not found: {chain_id}/{token_address}"
            
            # DexScreener API returns {"pairs": [...]} or {"pairs": null}
            if isinstance(response, dict):
                pairs = response.get("pairs", [])
            else:
                # Fallback if API returns list directly (shouldn't happen)
                pairs = response if isinstance(response, list) else []
            
            if not pairs:
                return [], f"No trading pairs found for {chain_id}/{token_address}"
            
            return pairs, None
            
        except Exception as e:
            return [], f"Error fetching pairs for {chain_id}/{token_address}: {e!s}"

    
    def format_pair_to_markdown(
        self, 
        pair: dict[str, Any], 
        token_name: str | None = None
    ) -> str:
        """
        Convert a trading pair to markdown format.
        
        Args:
            pair: The pair object from DexScreener API
            token_name: Optional custom name for the token
            
        Returns:
            Markdown string representation of the trading pair
        """
        # Extract pair details
        pair_address = pair.get("pairAddress", "Unknown")
        chain_id = pair.get("chainId", "Unknown")
        dex_id = pair.get("dexId", "Unknown")
        url = pair.get("url", "")
        
        # Extract token information
        base_token = pair.get("baseToken", {})
        quote_token = pair.get("quoteToken", {})
        
        base_symbol = base_token.get("symbol", "Unknown")
        base_name = token_name or base_token.get("name", "Unknown")
        quote_symbol = quote_token.get("symbol", "Unknown")
        
        # Extract price and volume data
        price_native = pair.get("priceNative", "N/A")
        price_usd = pair.get("priceUsd", "N/A")
        
        # Extract liquidity data
        liquidity = pair.get("liquidity", {})
        liquidity_usd = liquidity.get("usd", 0)
        
        # Extract volume data
        volume = pair.get("volume", {})
        volume_24h = volume.get("h24", 0)
        volume_6h = volume.get("h6", 0)
        volume_1h = volume.get("h1", 0)
        
        # Extract price change data
        price_change = pair.get("priceChange", {})
        price_change_24h = price_change.get("h24", 0)
        
        # Extract market cap and FDV
        market_cap = pair.get("marketCap", 0)
        fdv = pair.get("fdv", 0)
        
        # Extract transaction counts
        txns = pair.get("txns", {})
        txns_24h = txns.get("h24", {})
        buys_24h = txns_24h.get("buys", 0)
        sells_24h = txns_24h.get("sells", 0)
        
        # Build markdown content
        markdown_content = f"# {base_symbol}/{quote_symbol} Trading Pair\n\n"
        
        if token_name:
            markdown_content += f"**Token:** {base_name} ({base_symbol})\n"
        
        markdown_content += f"**Chain:** {chain_id}\n"
        markdown_content += f"**DEX:** {dex_id}\n"
        markdown_content += f"**Pair Address:** `{pair_address}`\n\n"
        
        # Add price information
        markdown_content += "## Price Information\n\n"
        markdown_content += f"- **Price (USD):** ${price_usd}\n"
        markdown_content += f"- **Price (Native):** {price_native} {quote_symbol}\n"
        markdown_content += f"- **24h Change:** {price_change_24h:+.2f}%\n\n"
        
        # Add liquidity information
        markdown_content += "## Liquidity\n\n"
        markdown_content += f"- **Total Liquidity:** ${liquidity_usd:,.2f}\n\n"
        
        # Add volume information
        markdown_content += "## Trading Volume\n\n"
        markdown_content += f"- **24h Volume:** ${volume_24h:,.2f}\n"
        markdown_content += f"- **6h Volume:** ${volume_6h:,.2f}\n"
        markdown_content += f"- **1h Volume:** ${volume_1h:,.2f}\n\n"
        
        # Add market metrics
        markdown_content += "## Market Metrics\n\n"
        markdown_content += f"- **Market Cap:** ${market_cap:,.2f}\n"
        markdown_content += f"- **FDV (Fully Diluted Valuation):** ${fdv:,.2f}\n\n"
        
        # Add transaction information
        markdown_content += "## Transactions (24h)\n\n"
        markdown_content += f"- **Buys:** {buys_24h}\n"
        markdown_content += f"- **Sells:** {sells_24h}\n"
        markdown_content += f"- **Total:** {buys_24h + sells_24h}\n\n"
        
        # Add link to DexScreener
        if url:
            markdown_content += f"**View on DexScreener:** {url}\n\n"
        
        return markdown_content


# Example usage (uncomment to use):
"""
import asyncio

async def main():
    connector = DexScreenerConnector()
    
    # Example: Fetch WETH pairs on Ethereum
    chain = "ethereum"
    address = "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"
    
    pairs, error = await connector.get_token_pairs(chain, address)
    
    if error:
        print(f"Error: {error}")
    else:
        print(f"Found {len(pairs)} pairs for WETH")
        
        # Format first pair to markdown
        if pairs:
            markdown = connector.format_pair_to_markdown(pairs[0], "Wrapped Ether")
            print("\nSample Pair in Markdown:\n")
            print(markdown)

if __name__ == "__main__":
    asyncio.run(main())
"""
