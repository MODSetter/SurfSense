# Story 1.1: DexScreener Connector Integration

## 📋 Story Overview

**Story ID**: 1.1  
**Story Title**: DexScreener Connector Integration  
**Epic**: SurfSense Connectors Enhancement  
**Priority**: High  
**Status**: ✅ Implementation Complete (2026-02-01)  
**Created**: 2026-01-31  

## 🎯 User Story

**As a** SurfSense user tracking cryptocurrency markets  
**I want** to connect my DexScreener data to SurfSense  
**So that** I can search and chat with AI about my tracked trading pairs and token data

## 📝 Description

Implement a custom connector for DexScreener API that allows users to:
1. Configure tracked tokens across multiple blockchain networks
2. Automatically index trading pair data (prices, volume, liquidity, etc.)
3. Search and retrieve indexed crypto market data
4. Use AI chat with context from DexScreener trading pairs

This connector will integrate with SurfSense's existing connector architecture, following the established patterns from Luma, Slack, and other connectors.

## ✅ Acceptance Criteria

### AC1: Connector Configuration ✅
- [x] User can add DexScreener connector via API endpoint
- [x] User can configure multiple tokens to track (up to 50)
- [x] Each token config includes: chain ID, token address, optional name
- [x] User can update connector configuration
- [x] User can delete connector
- [x] Configuration is persisted in database

### AC2: API Integration ✅
- [x] Connector successfully calls DexScreener API endpoints
- [x] Handles rate limits (300 req/min) appropriately
- [x] Implements retry logic with exponential backoff
- [x] Validates API responses
- [x] Handles API errors gracefully (network failures, invalid data, etc.)

### AC3: Data Indexing ✅
- [x] Fetches trading pairs for all configured tokens
- [x] Converts pair data to markdown format with all key metrics:
  - Token information (names, symbols, addresses)
  - Price data (USD, native, 24h changes)
  - Volume metrics (24h, 6h, 1h)
  - Liquidity information
  - Market cap and FDV
  - Transaction counts
- [x] Generates unique identifier hash for each pair
- [x] Generates content hash to detect changes
- [x] Creates document chunks for vector search
- [x] Generates embeddings using configured LLM
- [x] Stores documents in database with proper metadata
- [x] Updates existing documents when content changes
- [x] Skips unchanged documents

### AC4: Periodic Indexing ✅
- [x] Indexing task is registered with Celery
- [x] Periodic scheduler triggers indexing (default: 60 min interval)
- [x] Manual indexing can be triggered via API
- [x] Last indexed timestamp is updated after successful indexing
- [x] Indexing errors are logged properly
- [x] Failed indexing doesn't block future attempts

### AC5: Search Integration ✅
- [x] Indexed DexScreener data appears in search results
- [x] Documents are searchable by:
  - Token names and symbols
  - Pair addresses
  - Chain IDs
  - DEX names
  - Price ranges
  - Volume metrics
- [x] Search results include relevant metadata
- [x] Vector search returns semantically similar pairs

### AC6: AI Chat Integration ✅
- [x] AI chat can access DexScreener data as context
- [x] Chat responses include relevant trading pair information
- [x] Citations link to DexScreener URLs
- [x] Metadata is properly formatted in chat responses

## 🏗️ Technical Implementation

### Database Schema Changes

**File**: `app/db.py`

```python
class SearchSourceConnectorType(str, Enum):
    # ... existing types
    DEXSCREENER_CONNECTOR = "DEXSCREENER_CONNECTOR"

class DocumentType(str, Enum):
    # ... existing types
    DEXSCREENER_CONNECTOR = "DEXSCREENER_CONNECTOR"
```

### Components to Implement

#### 1. Connector Class
**File**: `app/connectors/dexscreener_connector.py`

**Methods**:
- `__init__()` - Initialize connector (no API key needed)
- `make_request(endpoint, params)` - Generic API request handler
- `search_pairs(query)` - Search for trading pairs
- `get_token_pairs(chain_id, token_address)` - Get all pairs for a token
- `get_pair_by_address(chain_id, pair_address)` - Get specific pair details
- `get_multiple_tokens(chain_id, token_addresses)` - Batch query tokens
- `format_pair_to_markdown(pair)` - Convert pair data to markdown

#### 2. Indexer
**File**: `app/tasks/connector_indexers/dexscreener_indexer.py`

**Function**: `async def index_dexscreener_pairs(session, connector_id, search_space_id, user_id, start_date=None, end_date=None, update_last_indexed=True)`

**Required Imports**:
```python
from .base import (
    check_document_by_unique_identifier,
    check_duplicate_document_by_hash,
    get_connector_by_id,
    get_current_timestamp,
    logger,
    update_connector_last_indexed,
)
```


**Logic**:
1. Get connector from database
2. Extract token configuration from `connector.config.get("tokens")`
3. Initialize DexScreener connector
4. For each tracked token:
   - Fetch all trading pairs
   - For each pair:
     - Format to markdown
     - Generate hashes
     - Check if document exists
     - Create or update document
     - Batch commit every 10 documents
5. Update last_indexed_at timestamp
6. Log success/failure


#### 3. API Routes
**File**: `app/routes/dexscreener_add_connector_route.py`

**Endpoints**:
- `POST /connectors/dexscreener/add` - Add/update connector
- `DELETE /connectors/dexscreener` - Delete connector
- `GET /connectors/dexscreener/test` - Test API connection

#### 4. Celery Task
**File**: `app/tasks/celery_tasks/connector_tasks.py`

**Task**: `index_dexscreener_pairs_task(connector_id, search_space_id, user_id, start_date, end_date)`

**Note**: Requires both the Celery task wrapper and async helper function:
- `@celery_app.task(bind=True)` decorator on `index_dexscreener_pairs_task`
- `async def _index_dexscreener_pairs(...)` helper that creates session and calls indexer

#### 5. Scheduler Integration
**File**: `app/utils/periodic_scheduler.py`

**Mappings**:
Add to `CONNECTOR_TASK_MAP` dictionary:
```python
SearchSourceConnectorType.DEXSCREENER_CONNECTOR: "index_dexscreener_pairs"
```

#### 6. Routes Registration
**File**: `app/routes/__init__.py`

Import and include `dexscreener_add_connector_router`

#### 7. Indexer Export
**File**: `app/tasks/connector_indexers/__init__.py`

Export `index_dexscreener_pairs`

## 🔗 Dependencies

### External APIs
- **DexScreener API**: `https://api.dexscreener.com`
  - No authentication required
  - Rate limit: 300 requests/minute
  - Free tier available

### Internal Dependencies
- `httpx` - HTTP client for API requests
- `app.utils.document_converters` - Document processing utilities
- `app.services.llm_service` - LLM for embeddings and summaries
- `app.services.task_logging_service` - Task logging
- SQLAlchemy models and sessions
- Celery for background tasks

## 📊 Data Model

### Connector Config Schema
```json
{
  "tokens": [
    {
      "chain": "solana",
      "address": "So11111111111111111111111111111111111111112",
      "name": "Wrapped SOL"
    },
    {
      "chain": "ethereum",
      "address": "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
      "name": "Wrapped ETH"
    }
  ]
}
```

### Document Metadata Schema
```json
{
  "pair_address": "string",
  "chain_id": "string",
  "dex_id": "string",
  "base_token_symbol": "string",
  "base_token_address": "string",
  "quote_token_symbol": "string",
  "quote_token_address": "string",
  "price_usd": "string",
  "price_native": "string",
  "volume_h24": "number",
  "liquidity_usd": "number",
  "market_cap": "number",
  "fdv": "number",
  "url": "string",
  "indexed_at": "string (ISO 8601)"
}
```

## 🧪 Testing Strategy

### Unit Tests
- [ ] Test `DexScreenerConnector` API methods
- [ ] Test markdown formatting logic
- [ ] Test error handling for API failures
- [ ] Test rate limit handling
- [ ] Test data validation

### Integration Tests
- [ ] Test full indexing flow
- [ ] Test connector CRUD operations
- [ ] Test periodic scheduling
- [ ] Test search integration
- [ ] Test AI chat context retrieval

### Manual Testing
1. Add connector with test tokens
2. Verify API test endpoint works
3. Trigger manual indexing
4. Check database for created documents
5. Search for indexed pairs
6. Use AI chat to query trading data
7. Verify periodic indexing runs
8. Test connector update and deletion

## ⚠️ Edge Cases & Error Handling

### API Errors
- **Rate Limit Exceeded (429)**: Implement exponential backoff, log warning
- **Network Timeout**: Retry with timeout, skip token if persistent
- **Invalid Response**: Log error, skip pair, continue indexing
- **Token Not Found**: Log warning, skip token

### Data Validation
- **Missing pair_address**: Skip pair, log warning
- **Empty markdown content**: Skip pair, log warning
- **Invalid chain_id**: Validate against known chains
- **Malformed token config**: Reject at API level with clear error

### Database Errors
- **Duplicate documents**: Update existing based on content hash
- **Transaction failures**: Rollback, log error, retry
- **Connection issues**: Retry with backoff

### Performance Considerations
- **Large token lists**: Batch commits every 10 documents
- **Slow API responses**: Set reasonable timeout (30s)
- **Memory usage**: Process pairs iteratively, not all at once

## 📈 Success Metrics

### Functional Metrics
- Connector successfully adds/updates/deletes
- API test endpoint returns valid data
- Indexing completes without errors
- Documents searchable within 5 minutes of indexing
- AI chat provides accurate trading pair information

### Performance Metrics
- API response time < 5 seconds for test endpoint
- Indexing time < 2 minutes for 50 tokens (avg 5 pairs each)
- Search latency < 500ms
- Rate limit compliance: 0 violations

### Quality Metrics
- 0 critical bugs in production
- < 1% indexing failure rate
- 100% test coverage for core logic
- All acceptance criteria met

## 🚀 Deployment Plan

### Pre-deployment
1. Review and merge PR
2. Run all tests in CI/CD
3. Database migration (add enum values)
4. Deploy to staging environment
5. Smoke test on staging

### Deployment Steps
1. Deploy backend changes
2. Verify Celery workers pick up new task
3. Verify periodic scheduler includes new connector
4. Monitor logs for errors
5. Test connector addition via API

### Post-deployment
1. Monitor error logs for 24 hours
2. Check indexing task success rate
3. Verify search results quality
4. Gather user feedback

### Rollback Plan
If critical issues occur:
1. Remove connector type from periodic scheduler
2. Disable connector routes
3. Revert database migration if needed
4. Investigate and fix issues
5. Redeploy with fixes

## 📚 Documentation

### User Documentation
- [ ] Add DexScreener to connector list in user guide
- [ ] Document how to add DexScreener connector
- [ ] Explain token configuration format
- [ ] Provide example API requests
- [ ] Document supported chains

### Developer Documentation
- [ ] Add inline code comments
- [ ] Document API endpoints in OpenAPI spec
- [ ] Update connector architecture docs
- [ ] Add troubleshooting guide
- [ ] Document rate limit handling

## 🔐 Security Considerations

- **No API Keys**: DexScreener API is public, no sensitive data to store
- **Input Validation**: Validate chain IDs and token addresses
- **Rate Limiting**: Respect API rate limits to avoid IP bans
- **Data Privacy**: No PII collected or stored
- **Error Messages**: Don't expose internal system details in API responses

## 🎯 Definition of Done

- [ ] All acceptance criteria met
- [ ] Code reviewed and approved
- [ ] Unit tests written and passing
- [ ] Integration tests written and passing
- [ ] Manual testing completed
- [ ] Documentation updated
- [ ] Deployed to staging and tested
- [ ] Deployed to production
- [ ] Monitoring in place
- [ ] User guide updated
- [ ] Story marked as complete

## 📎 Related Documents

- [DexScreener API Documentation](https://docs.dexscreener.com/api/reference)
- [Implementation Plan](./dexscreener-connector-implementation-plan.md)
- [SurfSense Connector Architecture](../../../Documents/GitHub/SurfSense/_bmad-output/connectors-explained.md)
- [Custom Connector Guide](../../../Documents/GitHub/SurfSense/_bmad-output/custom-connector-guide.md)

## 💬 Notes

- DexScreener API is free and doesn't require authentication
- Rate limit of 300 req/min is generous for typical use cases
- Consider implementing priority queue for high-value tokens in future
- May want to add support for custom indexing intervals per token
- Consider adding alerts for significant price changes in future enhancement

---

**Story Created By**: Antigravity AI  
**Date**: 2026-01-31  
**Last Updated**: 2026-01-31
