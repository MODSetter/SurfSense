"""
Real-time cryptocurrency data tools for the SurfSense agent.

This module provides tools for fetching LIVE crypto data directly from DexScreener API.
These tools complement the RAG-based search_knowledge_base tool:
- RAG (search_knowledge_base): Historical context, trends, analysis from indexed data
- Real-time tools: Current prices, live market data

The AI agent decides which to use based on the query:
- "What's the current price of BULLA?" → get_live_token_price (real-time)
- "How has BULLA performed this week?" → search_knowledge_base (RAG)
- "Analyze BULLA for me" → Both (RAG for context + real-time for current data)
"""

import hashlib
import logging
from typing import Any

from langchain_core.tools import tool

from app.connectors.dexscreener_connector import DexScreenerConnector

logger = logging.getLogger(__name__)


def generate_token_id(chain: str, address: str) -> str:
    """Generate a unique ID for a token query."""
    hash_val = hashlib.md5(f"{chain}:{address}".encode()).hexdigest()[:12]
    return f"token-{hash_val}"


def create_get_live_token_price_tool():
    """
    Factory function to create the get_live_token_price tool.
    
    This tool fetches REAL-TIME price data directly from DexScreener API.
    Use this when users ask for current/live prices.
    
    Returns:
        A configured tool function for fetching live token prices.
    """

    @tool
    async def get_live_token_price(
        chain: str,
        token_address: str,
        token_symbol: str | None = None,
    ) -> dict[str, Any]:
        """
        Get the LIVE/CURRENT price of a cryptocurrency token from DexScreener.
        
        Use this tool when the user asks for:
        - Current price: "What's the price of BULLA right now?"
        - Live data: "Show me live price for SOL"
        - Real-time info: "What's WETH trading at?"
        
        DO NOT use this for historical analysis - use search_knowledge_base instead.
        
        Args:
            chain: Blockchain network (e.g., 'solana', 'ethereum', 'base', 'bsc')
            token_address: The token's contract address
            token_symbol: Optional token symbol for display (e.g., 'BULLA', 'SOL')
        
        Returns:
            Dictionary with live price data including:
            - price_usd: Current price in USD
            - price_change_24h: 24-hour price change percentage
            - price_change_1h: 1-hour price change percentage
            - volume_24h: 24-hour trading volume
            - liquidity_usd: Total liquidity in USD
            - market_cap: Market capitalization
            - dex: DEX where the best liquidity is found
            - pair_url: Link to DexScreener chart
        """
        token_id = generate_token_id(chain, token_address)
        
        try:
            # Initialize DexScreener connector
            connector = DexScreenerConnector()
            
            # Fetch live data from API
            pairs, error = await connector.get_token_pairs(chain, token_address)
            
            if error:
                logger.warning(f"[get_live_token_price] Error: {error}")
                return {
                    "id": token_id,
                    "kind": "live_token_price",
                    "chain": chain,
                    "token_address": token_address,
                    "token_symbol": token_symbol,
                    "error": error,
                }
            
            if not pairs:
                return {
                    "id": token_id,
                    "kind": "live_token_price",
                    "chain": chain,
                    "token_address": token_address,
                    "token_symbol": token_symbol,
                    "error": f"No trading pairs found for {token_symbol or token_address} on {chain}",
                }
            
            # Get the best pair (highest liquidity)
            best_pair = max(pairs, key=lambda p: float(p.get("liquidity", {}).get("usd", 0) or 0))
            
            # Extract data from best pair
            base_token = best_pair.get("baseToken", {})
            price_change = best_pair.get("priceChange", {})
            volume = best_pair.get("volume", {})
            liquidity = best_pair.get("liquidity", {})
            
            return {
                "id": token_id,
                "kind": "live_token_price",
                "chain": chain,
                "token_address": token_address,
                "token_symbol": token_symbol or base_token.get("symbol", "Unknown"),
                "token_name": base_token.get("name", "Unknown"),
                "price_usd": best_pair.get("priceUsd", "N/A"),
                "price_native": best_pair.get("priceNative", "N/A"),
                "price_change_5m": price_change.get("m5", 0),
                "price_change_1h": price_change.get("h1", 0),
                "price_change_6h": price_change.get("h6", 0),
                "price_change_24h": price_change.get("h24", 0),
                "volume_24h": volume.get("h24", 0),
                "volume_6h": volume.get("h6", 0),
                "volume_1h": volume.get("h1", 0),
                "liquidity_usd": liquidity.get("usd", 0),
                "market_cap": best_pair.get("marketCap", 0),
                "fdv": best_pair.get("fdv", 0),
                "dex": best_pair.get("dexId", "Unknown"),
                "pair_address": best_pair.get("pairAddress", ""),
                "pair_url": best_pair.get("url", ""),
                "total_pairs": len(pairs),
                "data_source": "DexScreener API (Real-time)",
            }
            
        except Exception as e:
            error_message = str(e)
            logger.error(f"[get_live_token_price] Error fetching {chain}/{token_address}: {error_message}")
            return {
                "id": token_id,
                "kind": "live_token_price",
                "chain": chain,
                "token_address": token_address,
                "token_symbol": token_symbol,
                "error": f"Failed to fetch live price: {error_message[:100]}",
            }

    return get_live_token_price


def create_get_live_token_data_tool():
    """
    Factory function to create the get_live_token_data tool.

    This tool fetches comprehensive REAL-TIME market data from DexScreener API.
    Use this when users want detailed current market information.

    Returns:
        A configured tool function for fetching live token market data.
    """

    @tool
    async def get_live_token_data(
        chain: str,
        token_address: str,
        token_symbol: str | None = None,
        include_all_pairs: bool = False,
    ) -> dict[str, Any]:
        """
        Get comprehensive LIVE market data for a cryptocurrency token.

        Use this tool when the user asks for:
        - Detailed market info: "Show me full market data for BULLA"
        - Trading activity: "What's the trading volume for SOL?"
        - Liquidity info: "How much liquidity does WETH have?"
        - Transaction counts: "How many buys/sells for this token?"

        This returns more detailed data than get_live_token_price.
        For historical trends and analysis, use search_knowledge_base instead.

        Args:
            chain: Blockchain network (e.g., 'solana', 'ethereum', 'base', 'bsc')
            token_address: The token's contract address
            token_symbol: Optional token symbol for display
            include_all_pairs: If True, include data from all trading pairs

        Returns:
            Dictionary with comprehensive market data including:
            - All price data from get_live_token_price
            - Transaction counts (buys/sells in 24h, 6h, 1h)
            - All trading pairs (if include_all_pairs=True)
            - Aggregated volume across all pairs
        """
        token_id = generate_token_id(chain, token_address)

        try:
            # Initialize DexScreener connector
            connector = DexScreenerConnector()

            # Fetch live data from API
            pairs, error = await connector.get_token_pairs(chain, token_address)

            if error:
                logger.warning(f"[get_live_token_data] Error: {error}")
                return {
                    "id": token_id,
                    "kind": "live_token_data",
                    "chain": chain,
                    "token_address": token_address,
                    "token_symbol": token_symbol,
                    "error": error,
                }

            if not pairs:
                return {
                    "id": token_id,
                    "kind": "live_token_data",
                    "chain": chain,
                    "token_address": token_address,
                    "token_symbol": token_symbol,
                    "error": f"No trading pairs found for {token_symbol or token_address} on {chain}",
                }

            # Get the best pair (highest liquidity)
            best_pair = max(pairs, key=lambda p: float(p.get("liquidity", {}).get("usd", 0) or 0))

            # Extract data from best pair
            base_token = best_pair.get("baseToken", {})
            price_change = best_pair.get("priceChange", {})
            volume = best_pair.get("volume", {})
            liquidity = best_pair.get("liquidity", {})
            txns = best_pair.get("txns", {})

            # Calculate aggregated stats across all pairs
            total_volume_24h = sum(float(p.get("volume", {}).get("h24", 0) or 0) for p in pairs)
            total_liquidity = sum(float(p.get("liquidity", {}).get("usd", 0) or 0) for p in pairs)
            total_buys_24h = sum(p.get("txns", {}).get("h24", {}).get("buys", 0) or 0 for p in pairs)
            total_sells_24h = sum(p.get("txns", {}).get("h24", {}).get("sells", 0) or 0 for p in pairs)

            result = {
                "id": token_id,
                "kind": "live_token_data",
                "chain": chain,
                "token_address": token_address,
                "token_symbol": token_symbol or base_token.get("symbol", "Unknown"),
                "token_name": base_token.get("name", "Unknown"),
                # Price data
                "price_usd": best_pair.get("priceUsd", "N/A"),
                "price_native": best_pair.get("priceNative", "N/A"),
                "price_change_5m": price_change.get("m5", 0),
                "price_change_1h": price_change.get("h1", 0),
                "price_change_6h": price_change.get("h6", 0),
                "price_change_24h": price_change.get("h24", 0),
                # Volume data (best pair)
                "volume_24h": volume.get("h24", 0),
                "volume_6h": volume.get("h6", 0),
                "volume_1h": volume.get("h1", 0),
                "volume_5m": volume.get("m5", 0),
                # Liquidity
                "liquidity_usd": liquidity.get("usd", 0),
                "liquidity_base": liquidity.get("base", 0),
                "liquidity_quote": liquidity.get("quote", 0),
                # Market metrics
                "market_cap": best_pair.get("marketCap", 0),
                "fdv": best_pair.get("fdv", 0),
                # Transaction counts (best pair)
                "txns_24h_buys": txns.get("h24", {}).get("buys", 0),
                "txns_24h_sells": txns.get("h24", {}).get("sells", 0),
                "txns_6h_buys": txns.get("h6", {}).get("buys", 0),
                "txns_6h_sells": txns.get("h6", {}).get("sells", 0),
                "txns_1h_buys": txns.get("h1", {}).get("buys", 0),
                "txns_1h_sells": txns.get("h1", {}).get("sells", 0),
                # Aggregated stats (all pairs)
                "total_volume_24h_all_pairs": total_volume_24h,
                "total_liquidity_all_pairs": total_liquidity,
                "total_buys_24h_all_pairs": total_buys_24h,
                "total_sells_24h_all_pairs": total_sells_24h,
                # DEX info
                "dex": best_pair.get("dexId", "Unknown"),
                "pair_address": best_pair.get("pairAddress", ""),
                "pair_url": best_pair.get("url", ""),
                "pair_created_at": best_pair.get("pairCreatedAt"),
                # Metadata
                "total_pairs": len(pairs),
                "data_source": "DexScreener API (Real-time)",
            }

            # Include all pairs if requested
            if include_all_pairs and len(pairs) > 1:
                result["all_pairs"] = [
                    {
                        "dex": p.get("dexId"),
                        "pair_address": p.get("pairAddress"),
                        "quote_symbol": p.get("quoteToken", {}).get("symbol"),
                        "price_usd": p.get("priceUsd"),
                        "liquidity_usd": p.get("liquidity", {}).get("usd", 0),
                        "volume_24h": p.get("volume", {}).get("h24", 0),
                        "url": p.get("url"),
                    }
                    for p in sorted(pairs, key=lambda x: float(x.get("liquidity", {}).get("usd", 0) or 0), reverse=True)[:10]
                ]

            return result

        except Exception as e:
            error_message = str(e)
            logger.error(f"[get_live_token_data] Error fetching {chain}/{token_address}: {error_message}")
            return {
                "id": token_id,
                "kind": "live_token_data",
                "chain": chain,
                "token_address": token_address,
                "token_symbol": token_symbol,
                "error": f"Failed to fetch live data: {error_message[:100]}",
            }

    return get_live_token_data

