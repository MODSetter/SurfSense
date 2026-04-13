# Hướng Dẫn Tạo Custom Connectors cho SurfSense

## Tổng Quan

Bạn **hoàn toàn có thể** tạo custom connectors để kết nối đến các API bên ngoài như DexScreener, DefiLlama để phân tích token crypto. SurfSense có kiến trúc connector rất linh hoạt và dễ mở rộng.

## Kiến Trúc Connector

Mỗi connector trong SurfSense bao gồm 3 phần chính:

### 1. **Connector Class** (`app/connectors/`)
- Xử lý logic kết nối đến API bên ngoài
- Fetch và transform data
- Format data thành markdown để indexing

### 2. **API Routes** (`app/routes/`)
- Endpoint để add/delete/test connector
- Lưu config vào database
- Xác thực user

### 3. **Database Schema** (`app/db.py`)
- Định nghĩa connector type trong `SearchSourceConnectorType` enum
- Lưu trữ config (API keys, settings) trong `SearchSourceConnector` table

## Ví Dụ: Tạo DexScreener Connector

### Bước 1: Tạo Connector Class

Tạo file `/Users/mac_1/Documents/GitHub/SurfSense/surfsense_backend/app/connectors/dexscreener_connector.py`:

```python
"""
DexScreener Connector Module

A module for fetching token data and analytics from DexScreener API.
"""

from typing import Any
import requests
from datetime import datetime


class DexScreenerConnector:
    """Class for retrieving token data from DexScreener."""

    def __init__(self, api_key: str | None = None):
        """
        Initialize the DexScreenerConnector class.

        Args:
            api_key: DexScreener API key (optional for public endpoints)
        """
        self.api_key = api_key
        self.base_url = "https://api.dexscreener.com/latest"

    def set_api_key(self, api_key: str) -> None:
        """Set the DexScreener API key."""
        self.api_key = api_key

    def get_headers(self) -> dict[str, str]:
        """Get headers for DexScreener API requests."""
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def search_pairs(
        self, query: str
    ) -> tuple[list[dict[str, Any]], str | None]:
        """
        Search for trading pairs by token address or symbol.

        Args:
            query: Token address or symbol to search

        Returns:
            Tuple containing (pairs list, error message or None)
        """
        try:
            url = f"{self.base_url}/dex/search"
            params = {"q": query}
            
            response = requests.get(
                url, 
                headers=self.get_headers(), 
                params=params,
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                pairs = data.get("pairs", [])
                return pairs, None
            else:
                return [], f"API request failed with status {response.status_code}"

        except Exception as e:
            return [], f"Error searching pairs: {str(e)}"

    def get_token_pairs(
        self, token_address: str
    ) -> tuple[list[dict[str, Any]], str | None]:
        """
        Get all pairs for a specific token address.

        Args:
            token_address: Token contract address

        Returns:
            Tuple containing (pairs list, error message or None)
        """
        try:
            url = f"{self.base_url}/dex/tokens/{token_address}"
            
            response = requests.get(
                url, 
                headers=self.get_headers(),
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                pairs = data.get("pairs", [])
                return pairs, None
            else:
                return [], f"API request failed with status {response.status_code}"

        except Exception as e:
            return [], f"Error fetching token pairs: {str(e)}"

    def get_pair_by_address(
        self, pair_address: str
    ) -> tuple[dict[str, Any] | None, str | None]:
        """
        Get detailed information about a specific pair.

        Args:
            pair_address: Pair contract address

        Returns:
            Tuple containing (pair data dict, error message or None)
        """
        try:
            url = f"{self.base_url}/dex/pairs/{pair_address}"
            
            response = requests.get(
                url, 
                headers=self.get_headers(),
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                pair = data.get("pair")
                return pair, None
            else:
                return None, f"API request failed with status {response.status_code}"

        except Exception as e:
            return None, f"Error fetching pair: {str(e)}"

    def format_pair_to_markdown(self, pair: dict[str, Any]) -> str:
        """
        Convert a trading pair to markdown format for indexing.

        Args:
            pair: The pair object from DexScreener API

        Returns:
            Markdown string representation of the pair
        """
        # Extract basic info
        chain_id = pair.get("chainId", "Unknown")
        dex_id = pair.get("dexId", "Unknown")
        pair_address = pair.get("pairAddress", "")
        
        # Token info
        base_token = pair.get("baseToken", {})
        quote_token = pair.get("quoteToken", {})
        
        base_name = base_token.get("name", "Unknown")
        base_symbol = base_token.get("symbol", "Unknown")
        quote_name = quote_token.get("name", "Unknown")
        quote_symbol = quote_token.get("symbol", "Unknown")
        
        # Price and volume
        price_native = pair.get("priceNative", "N/A")
        price_usd = pair.get("priceUsd", "N/A")
        volume_24h = pair.get("volume", {}).get("h24", "N/A")
        liquidity_usd = pair.get("liquidity", {}).get("usd", "N/A")
        
        # Price changes
        price_change_5m = pair.get("priceChange", {}).get("m5", "N/A")
        price_change_1h = pair.get("priceChange", {}).get("h1", "N/A")
        price_change_24h = pair.get("priceChange", {}).get("h24", "N/A")
        
        # Build markdown
        markdown = f"# {base_symbol}/{quote_symbol} Trading Pair\n\n"
        
        markdown += f"**Chain:** {chain_id}\n"
        markdown += f"**DEX:** {dex_id}\n"
        markdown += f"**Pair Address:** `{pair_address}`\n\n"
        
        markdown += "## Token Information\n\n"
        markdown += f"### Base Token: {base_name} ({base_symbol})\n"
        markdown += f"- **Address:** `{base_token.get('address', 'N/A')}`\n\n"
        
        markdown += f"### Quote Token: {quote_name} ({quote_symbol})\n"
        markdown += f"- **Address:** `{quote_token.get('address', 'N/A')}`\n\n"
        
        markdown += "## Market Data\n\n"
        markdown += f"- **Price (Native):** {price_native}\n"
        markdown += f"- **Price (USD):** ${price_usd}\n"
        markdown += f"- **24h Volume:** ${volume_24h}\n"
        markdown += f"- **Liquidity (USD):** ${liquidity_usd}\n\n"
        
        markdown += "## Price Changes\n\n"
        markdown += f"- **5 minutes:** {price_change_5m}%\n"
        markdown += f"- **1 hour:** {price_change_1h}%\n"
        markdown += f"- **24 hours:** {price_change_24h}%\n\n"
        
        # Add URL if available
        url = pair.get("url")
        if url:
            markdown += f"**DexScreener URL:** {url}\n\n"
        
        # Add timestamp
        markdown += f"*Data fetched at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n"
        
        return markdown

    def get_all_token_data(
        self, token_addresses: list[str]
    ) -> tuple[list[str], str | None]:
        """
        Fetch and format data for multiple tokens.

        Args:
            token_addresses: List of token contract addresses

        Returns:
            Tuple containing (list of markdown documents, error message or None)
        """
        documents = []
        errors = []

        for address in token_addresses:
            pairs, error = self.get_token_pairs(address)
            
            if error:
                errors.append(f"Error for {address}: {error}")
                continue
            
            for pair in pairs:
                markdown_doc = self.format_pair_to_markdown(pair)
                documents.append(markdown_doc)

        error_msg = "; ".join(errors) if errors else None
        return documents, error_msg
```

### Bước 2: Thêm Connector Type vào Database

Sửa file `/Users/mac_1/Documents/GitHub/SurfSense/surfsense_backend/app/db.py`:

```python
class SearchSourceConnectorType(str, Enum):
    # ... existing connectors ...
    DEXSCREENER_CONNECTOR = "DEXSCREENER_CONNECTOR"
    DEFILLAMA_CONNECTOR = "DEFILLAMA_CONNECTOR"
```

### Bước 3: Tạo API Routes

Tạo file `/Users/mac_1/Documents/GitHub/SurfSense/surfsense_backend/app/routes/dexscreener_add_connector_route.py`:

```python
import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db import (
    SearchSourceConnector,
    SearchSourceConnectorType,
    User,
    get_async_session,
)
from app.users import current_active_user

logger = logging.getLogger(__name__)

router = APIRouter()


class AddDexScreenerConnectorRequest(BaseModel):
    """Request model for adding a DexScreener connector."""

    api_key: str | None = Field(None, description="DexScreener API key (optional)")
    space_id: int = Field(..., description="Search space ID")
    token_addresses: list[str] = Field(
        default_factory=list,
        description="List of token addresses to track"
    )


@router.post("/connectors/dexscreener/add")
async def add_dexscreener_connector(
    request: AddDexScreenerConnectorRequest,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    """
    Add a new DexScreener connector for the authenticated user.

    Args:
        request: The request containing DexScreener config and space_id
        user: Current authenticated user
        session: Database session

    Returns:
        Success message and connector details

    Raises:
        HTTPException: If connector already exists or validation fails
    """
    try:
        # Check if a DexScreener connector already exists
        result = await session.execute(
            select(SearchSourceConnector).filter(
                SearchSourceConnector.search_space_id == request.space_id,
                SearchSourceConnector.user_id == user.id,
                SearchSourceConnector.connector_type
                == SearchSourceConnectorType.DEXSCREENER_CONNECTOR,
            )
        )
        existing_connector = result.scalars().first()

        config = {
            "token_addresses": request.token_addresses,
        }
        if request.api_key:
            config["api_key"] = request.api_key

        if existing_connector:
            # Update existing connector
            existing_connector.config = config
            existing_connector.is_indexable = True
            await session.commit()
            await session.refresh(existing_connector)

            logger.info(
                f"Updated existing DexScreener connector for user {user.id}"
            )

            return {
                "message": "DexScreener connector updated successfully",
                "connector_id": existing_connector.id,
                "connector_type": "DEXSCREENER_CONNECTOR",
            }

        # Create new DexScreener connector
        db_connector = SearchSourceConnector(
            name="DexScreener Token Tracker",
            connector_type=SearchSourceConnectorType.DEXSCREENER_CONNECTOR,
            config=config,
            search_space_id=request.space_id,
            user_id=user.id,
            is_indexable=True,
        )

        session.add(db_connector)
        await session.commit()
        await session.refresh(db_connector)

        logger.info(
            f"Successfully created DexScreener connector for user {user.id}"
        )

        return {
            "message": "DexScreener connector added successfully",
            "connector_id": db_connector.id,
            "connector_type": "DEXSCREENER_CONNECTOR",
        }

    except IntegrityError as e:
        await session.rollback()
        logger.error(f"Database integrity error: {str(e)}")
        raise HTTPException(
            status_code=409,
            detail="A DexScreener connector already exists for this user.",
        ) from e
    except Exception as e:
        await session.rollback()
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to add DexScreener connector: {str(e)}",
        ) from e


@router.delete("/connectors/dexscreener")
async def delete_dexscreener_connector(
    space_id: int,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    """Delete the DexScreener connector."""
    try:
        result = await session.execute(
            select(SearchSourceConnector).filter(
                SearchSourceConnector.search_space_id == space_id,
                SearchSourceConnector.user_id == user.id,
                SearchSourceConnector.connector_type
                == SearchSourceConnectorType.DEXSCREENER_CONNECTOR,
            )
        )
        connector = result.scalars().first()

        if not connector:
            raise HTTPException(
                status_code=404,
                detail="DexScreener connector not found.",
            )

        await session.delete(connector)
        await session.commit()

        return {"message": "DexScreener connector deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete DexScreener connector: {str(e)}",
        ) from e


@router.get("/connectors/dexscreener/test")
async def test_dexscreener_connector(
    space_id: int,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    """Test the DexScreener connector."""
    try:
        # Get the connector
        result = await session.execute(
            select(SearchSourceConnector).filter(
                SearchSourceConnector.search_space_id == space_id,
                SearchSourceConnector.user_id == user.id,
                SearchSourceConnector.connector_type
                == SearchSourceConnectorType.DEXSCREENER_CONNECTOR,
            )
        )
        connector = result.scalars().first()

        if not connector:
            raise HTTPException(
                status_code=404,
                detail="DexScreener connector not found.",
            )

        # Import and test
        from app.connectors.dexscreener_connector import DexScreenerConnector

        api_key = connector.config.get("api_key")
        dex = DexScreenerConnector(api_key=api_key)

        # Test with a sample search
        pairs, error = dex.search_pairs("WETH")
        
        if error:
            raise HTTPException(
                status_code=400,
                detail=f"Failed to connect to DexScreener: {error}",
            )

        return {
            "message": "DexScreener connector is working correctly",
            "sample_pairs_count": len(pairs),
            "tracked_tokens": connector.config.get("token_addresses", []),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to test DexScreener connector: {str(e)}",
        ) from e
```

### Bước 4: Đăng Ký Routes

Sửa file `/Users/mac_1/Documents/GitHub/SurfSense/surfsense_backend/app/main.py`:

```python
# Import route
from app.routes import dexscreener_add_connector_route

# Add to app
app.include_router(
    dexscreener_add_connector_route.router,
    prefix="/api",
    tags=["connectors"]
)
```

### Bước 5: Tạo Indexing Logic

Tạo file để xử lý indexing tự động:

```python
# app/connectors/dexscreener_indexer.py

from app.connectors.dexscreener_connector import DexScreenerConnector
from app.db import SearchSourceConnector
import logging

logger = logging.getLogger(__name__)


async def index_dexscreener_data(connector: SearchSourceConnector):
    """
    Index data from DexScreener connector.
    
    This function will be called periodically by the indexing service.
    """
    try:
        config = connector.config
        api_key = config.get("api_key")
        token_addresses = config.get("token_addresses", [])
        
        if not token_addresses:
            logger.warning(f"No token addresses configured for connector {connector.id}")
            return []
        
        # Initialize connector
        dex = DexScreenerConnector(api_key=api_key)
        
        # Fetch data for all tracked tokens
        documents, error = dex.get_all_token_data(token_addresses)
        
        if error:
            logger.error(f"Error indexing DexScreener data: {error}")
            return []
        
        logger.info(f"Successfully indexed {len(documents)} documents from DexScreener")
        return documents
        
    except Exception as e:
        logger.error(f"Error in DexScreener indexing: {str(e)}", exc_info=True)
        return []
```

## Ví Dụ: DefiLlama Connector

Tương tự, bạn có thể tạo DefiLlama connector:

```python
# app/connectors/defillama_connector.py

"""
DefiLlama Connector Module

A module for fetching DeFi protocol data and TVL analytics from DefiLlama API.
"""

from typing import Any
import requests
from datetime import datetime


class DefiLlamaConnector:
    """Class for retrieving DeFi data from DefiLlama."""

    def __init__(self):
        """Initialize the DefiLlamaConnector class."""
        self.base_url = "https://api.llama.fi"

    def get_protocol(
        self, protocol_slug: str
    ) -> tuple[dict[str, Any] | None, str | None]:
        """
        Get detailed information about a specific protocol.

        Args:
            protocol_slug: Protocol slug (e.g., "uniswap", "aave")

        Returns:
            Tuple containing (protocol data dict, error message or None)
        """
        try:
            url = f"{self.base_url}/protocol/{protocol_slug}"
            response = requests.get(url, timeout=10)

            if response.status_code == 200:
                return response.json(), None
            else:
                return None, f"API request failed with status {response.status_code}"

        except Exception as e:
            return None, f"Error fetching protocol: {str(e)}"

    def get_tvl_history(
        self, protocol_slug: str
    ) -> tuple[list[dict[str, Any]], str | None]:
        """
        Get TVL history for a protocol.

        Args:
            protocol_slug: Protocol slug

        Returns:
            Tuple containing (TVL history list, error message or None)
        """
        protocol_data, error = self.get_protocol(protocol_slug)
        
        if error:
            return [], error
        
        tvl_history = protocol_data.get("tvl", [])
        return tvl_history, None

    def get_all_protocols(self) -> tuple[list[dict[str, Any]], str | None]:
        """
        Get list of all protocols with basic info.

        Returns:
            Tuple containing (protocols list, error message or None)
        """
        try:
            url = f"{self.base_url}/protocols"
            response = requests.get(url, timeout=10)

            if response.status_code == 200:
                return response.json(), None
            else:
                return [], f"API request failed with status {response.status_code}"

        except Exception as e:
            return [], f"Error fetching protocols: {str(e)}"

    def get_chain_tvl(
        self, chain: str
    ) -> tuple[dict[str, Any] | None, str | None]:
        """
        Get TVL for a specific chain.

        Args:
            chain: Chain name (e.g., "Ethereum", "BSC")

        Returns:
            Tuple containing (chain TVL data, error message or None)
        """
        try:
            url = f"{self.base_url}/tvl/{chain}"
            response = requests.get(url, timeout=10)

            if response.status_code == 200:
                return response.json(), None
            else:
                return None, f"API request failed with status {response.status_code}"

        except Exception as e:
            return None, f"Error fetching chain TVL: {str(e)}"

    def format_protocol_to_markdown(self, protocol: dict[str, Any]) -> str:
        """
        Convert protocol data to markdown format.

        Args:
            protocol: Protocol data from DefiLlama API

        Returns:
            Markdown string representation
        """
        name = protocol.get("name", "Unknown Protocol")
        slug = protocol.get("slug", "")
        symbol = protocol.get("symbol", "N/A")
        
        # TVL data
        tvl = protocol.get("tvl", 0)
        chain_tvls = protocol.get("chainTvls", {})
        
        # Categories and chains
        category = protocol.get("category", "N/A")
        chains = protocol.get("chains", [])
        
        # Build markdown
        markdown = f"# {name}\n\n"
        
        if symbol != "N/A":
            markdown += f"**Symbol:** {symbol}\n"
        
        markdown += f"**Category:** {category}\n"
        markdown += f"**Slug:** `{slug}`\n\n"
        
        markdown += "## Total Value Locked (TVL)\n\n"
        markdown += f"**Current TVL:** ${tvl:,.2f}\n\n"
        
        if chains:
            markdown += "### TVL by Chain\n\n"
            for chain in chains:
                chain_tvl = chain_tvls.get(chain, 0)
                markdown += f"- **{chain}:** ${chain_tvl:,.2f}\n"
            markdown += "\n"
        
        # Description
        description = protocol.get("description")
        if description:
            markdown += f"## Description\n\n{description}\n\n"
        
        # Links
        url = protocol.get("url")
        twitter = protocol.get("twitter")
        
        if url or twitter:
            markdown += "## Links\n\n"
            if url:
                markdown += f"- **Website:** {url}\n"
            if twitter:
                markdown += f"- **Twitter:** https://twitter.com/{twitter}\n"
            markdown += "\n"
        
        markdown += f"*Data fetched at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n"
        
        return markdown
```

## Cách Sử Dụng

### 1. Thêm Connector qua API

```bash
# Add DexScreener connector
curl -X POST "http://localhost:8000/api/connectors/dexscreener/add" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "space_id": 1,
    "token_addresses": [
      "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
      "0xdAC17F958D2ee523a2206206994597C13D831ec7"
    ],
    "api_key": "optional_api_key"
  }'
```

### 2. Test Connector

```bash
curl -X GET "http://localhost:8000/api/connectors/dexscreener/test?space_id=1" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### 3. Xóa Connector

```bash
curl -X DELETE "http://localhost:8000/api/connectors/dexscreener?space_id=1" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

## Tích Hợp vào Indexing Pipeline

Để connector tự động index data định kỳ, bạn cần:

1. **Thêm vào Connector Service** (`app/services/connector_service.py`)
2. **Đăng ký indexing task** trong background job scheduler
3. **Cấu hình re-indexing interval** (mặc định 60 phút)

Ví dụ:

```python
# app/services/connector_service.py

async def index_connector_data(connector: SearchSourceConnector):
    """Index data from any connector type."""
    
    if connector.connector_type == SearchSourceConnectorType.DEXSCREENER_CONNECTOR:
        from app.connectors.dexscreener_indexer import index_dexscreener_data
        return await index_dexscreener_data(connector)
    
    elif connector.connector_type == SearchSourceConnectorType.DEFILLAMA_CONNECTOR:
        from app.connectors.defillama_indexer import index_defillama_data
        return await index_defillama_data(connector)
    
    # ... other connector types
```

---

## ⚠️ CRITICAL: Enable RAG Retrieval

**This is the most commonly missed step when adding new connectors!**

### The Problem

Even if your connector successfully:
1. ✅ Stores data in the database
2. ✅ Indexes data into vector store
3. ✅ Shows up in the UI

The LLM **WILL NOT** be able to retrieve this data unless you add the connector to the RAG mapping.

### The Fix

**File:** `surfsense_backend/app/agents/new_chat/chat_deepagent.py`

**Add your connector to `_CONNECTOR_TYPE_TO_SEARCHABLE`:**

```python
_CONNECTOR_TYPE_TO_SEARCHABLE = {
    "GMAIL": "GMAIL",
    "GOOGLE_DRIVE_CONNECTOR": "GOOGLE_DRIVE",
    "SLACK_CONNECTOR": "SLACK",
    "NOTION_CONNECTOR": "NOTION",
    # ... other connectors ...
    
    # ✅ ADD YOUR NEW CONNECTOR HERE
    "DEXSCREENER_CONNECTOR": "DEXSCREENER_CONNECTOR",
    "YOUR_CONNECTOR": "YOUR_CONNECTOR",  # Example
}
```

### Why This Matters

This mapping is used by `_map_connectors_to_searchable_types()` to:
1. Build the list of available search spaces for the LLM
2. Include connector types in the tool description
3. Enable the LLM to search your connector's data

**Without this mapping:**
- LLM won't know your connector exists
- LLM can't search your indexed data
- Users will get "I don't have access to that data" responses

### Verification

After adding the mapping, test with a user query:

```bash
# Example for DexScreener
curl -X POST http://localhost:8000/api/chat \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "message": "What is the current price of WETH?",
    "space_id": 7
  }'
```

**Expected:** LLM retrieves data and provides answer with citations.

**If failed:** Check that:
1. Connector is in `_CONNECTOR_TYPE_TO_SEARCHABLE`
2. Connector type matches exactly (case-sensitive)
3. Data is indexed in the correct `search_space_id`

---

## Best Practices

### 1. **Error Handling**
- Luôn return tuple `(data, error)` để dễ xử lý
- Log errors chi tiết để debug
- Graceful degradation khi API fail

### 2. **Rate Limiting**
- Respect API rate limits
- Implement exponential backoff
- Cache data khi có thể

### 3. **Data Formatting**
- Format data thành markdown rõ ràng
- Include metadata (timestamps, sources)
- Structured format để vector search hiệu quả

### 4. **Security**
- Encrypt API keys trong database
- Validate user input
- Implement proper authentication

### 5. **Performance**
- Async/await cho I/O operations
- Batch requests khi có thể
- Optimize indexing frequency

## Kết Luận

Với kiến trúc connector linh hoạt của SurfSense, bạn có thể:

✅ Kết nối đến **bất kỳ API nào** (DexScreener, DefiLlama, CoinGecko, etc.)
✅ Tự động **index và search** data từ nhiều nguồn
✅ **Customize** logic fetch và format data
✅ **Scale** dễ dàng với nhiều connectors

Connector system cho phép bạn biến SurfSense thành một **unified search platform** cho mọi loại data - từ emails, documents đến crypto analytics!
