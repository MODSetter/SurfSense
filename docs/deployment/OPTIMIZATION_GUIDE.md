# SurfSense Backend Performance Optimization Guide

## Analysis Scope

This guide covers performance optimization opportunities identified in the SurfSense backend:

- Database query patterns and N+1 issues
- Caching opportunities and repeated operations
- Async/parallel execution patterns
- Memory usage and data loading patterns
- API response optimization and payload sizes

## Critical Findings (11 Issues)

### Critical Issues (>1 second impact)

#### 1. N+1 Query Pattern - Document Chunk Fetching

**Location:** `app/agents/researcher/nodes.py:354-362`

**Impact:** 10 documents = 11 queries instead of 2

**Fix:** Use `selectinload(Document.chunks)` in query

**Expected Improvement:** 500ms-2000ms per request

#### 2. Duplicate Count Queries - Pagination

**Location:** `app/routes/documents_routes.py:191-207, 295-312`

**Impact:** 2 separate table scans per paginated request

**Fix:** Use window function `func.count().over()`

**Expected Improvement:** 100-200ms per request

#### 3. Large Payload - Full Document Content in List Views

**Location:** `app/routes/documents_routes.py:222-237, 327-342`

**Impact:** 50 documents × 100KB each = 5MB+ responses

**Fix:** Create DocumentSummary schema without content field

**Expected Improvement:** Bandwidth reduction of 95%, 200-500ms latency

### High Impact Issues (100-500ms impact)

#### 4. Missing Database Indexes

**Location:** `app/db.py` (model definitions)

**Missing:** `search_space_id`, `document_id`, `user_id` indexes

**Impact:** Full table scans on common queries

**Fix:** Add 6 composite indexes

**Expected Improvement:** 200-400ms on large datasets

#### 5. NullPool Connection Pooling

**Locations:** All `celery_tasks/*` files (4 files)

**Impact:** 100-500ms per connection for Celery tasks

**Fix:** Replace NullPool with `QueuePool(pool_size=10)`

**Expected Improvement:** 50-200ms per background task

#### 6. Memory Bloat - Unlimited Pagination

**Location:** `app/routes/documents_routes.py:217-222`

**Impact:** `page_size=-1` can load 100,000+ documents into memory

**Fix:** Set `max_page_size=1000` limit (✅ **Already implemented**)

**Expected Improvement:** Prevents OOM, saves 100MB+ memory

### Medium Impact Issues (50-200ms impact)

#### 7. Missing Embedding Model Cache

**Location:** `app/retriver/chunks_hybrid_search.py:37-38`

**Impact:** Model initialization overhead on every search

**Fix:** Implement singleton cache with `asyncio.Lock()`

**Expected Improvement:** 50-100ms per search

#### 8. No Query Reformulation Caching

**Location:** `app/services/query_service.py:16-98`

**Impact:** LLM API calls (2-5 seconds) for identical queries

**Fix:** Add QueryCache with 1-hour TTL

**Expected Improvement:** Cache hits save 2-5 seconds

#### 9. Sequential Connector Searches

**Location:** `app/agents/researcher/nodes.py:260+`

**Impact:** 5 connectors × 1s = 5s instead of 1s

**Fix:** Use `asyncio.gather(*search_tasks)`

**Expected Improvement:** 4-5 seconds if 5 connectors used

#### 10. Inefficient Response Serialization

**Location:** `app/routes/documents_routes.py:224-239`

**Impact:** Manual field-by-field object construction

**Fix:** Use `DocumentRead.model_validate()` or direct DB objects

**Expected Improvement:** 20-50ms on large responses

### Low Impact Issues (<50ms impact)

#### 11. Connector Config Not Cached

**Location:** `app/services/connector_service.py:286-288+`

**Impact:** Database query on each connector lookup

**Fix:** Add connector cache with 5-minute TTL

**Expected Improvement:** 10-30ms per search

## Implementation Priority Roadmap

### Phase 1 - Critical (Estimated Impact: 1-3 seconds)

1. **Fix N+1 Query Pattern (Issue #1)**
   - Use `selectinload` for chunks

2. **Combine Pagination Count Queries (Issue #2)**
   - Implement window functions

3. **Split Document List/Detail Schemas (Issue #3)**
   - Create `DocumentSummary` vs `DocumentRead`

### Phase 2 - High (Estimated Impact: 300-600ms)

4. **Add Database Indexes (Issue #4)**
   - 6 new composite indexes

5. **Fix Celery Connection Pooling (Issue #5)**
   - Replace NullPool with QueuePool

6. **Limit Pagination Memory (Issue #6)** ✅ **Already implemented**
   - `max_page_size=1000`

### Phase 3 - Medium (Estimated Impact: 200-400ms)

7. **Add Embedding Model Cache (Issue #7)**
   - Singleton with lock

8. **Implement Query Reformulation Cache (Issue #8)**
   - LLM result caching

9. **Parallelize Connector Searches (Issue #9)**
   - Use `asyncio.gather`

10. **Optimize Response Serialization (Issue #10)**
    - Use `model_validate`

### Phase 4 - Low (Estimated Impact: 30-50ms)

11. **Add Connector Config Cache (Issue #11)**
    - 5-minute TTL cache

## Files Requiring Changes

### Highest Priority Files

1. `app/agents/researcher/nodes.py` - N+1 fix, parallelization
2. `app/routes/documents_routes.py` - Pagination, payloads, schemas
3. `app/db.py` - Missing indexes
4. `app/tasks/celery_tasks/*.py` (4 files) - Connection pooling

### High Priority Files

5. `app/retriver/chunks_hybrid_search.py` - Caching
6. `app/services/query_service.py` - Caching
7. `app/services/connector_service.py` - Caching

### Medium Priority Files

8. `app/schemas/documents.py` - New summary schema
9. All route files - Response serialization
10. `app/retriver/documents_hybrid_search.py` - Consistency

## Key Metrics to Track

### Before Optimization

- Average query time per request: ? ms (enable SQL logging)
- Number of database queries per request: ? (enable query counting)
- Average response payload size: ? KB
- P95 response time: ? ms
- Memory usage at peak: ? MB
- Celery task latency: ? ms

### After Optimization (Target)

- N+1 queries eliminated: 100% reduction
- Pagination latency: 50-100ms (vs current 150-250ms)
- Response size: 90% smaller for list views
- Celery task latency: 50-100ms improvement
- Memory usage: 30-40% reduction
- Overall API latency: 40-50% improvement

## Testing Checklist

### Unit Tests

- [ ] Test `selectinload()` doesn't cause N+1
- [ ] Test window function count queries
- [ ] Test DocumentSummary vs DocumentRead serialization
- [ ] Test pagination limits

### Integration Tests

- [ ] Test `/documents` endpoint with 1000+ documents
- [ ] Test `/documents/search` with various filters
- [ ] Test embedding model caching behavior
- [ ] Test query reformulation caching

### Performance Tests

- [ ] Load test with 100 concurrent users
- [ ] Memory profile with large datasets
- [ ] Database query profiling (count and time)
- [ ] Before/after latency comparison

### Monitoring

- [ ] Enable APM (New Relic, DataDog, etc.)
- [ ] Monitor database query times and counts
- [ ] Track memory usage patterns
- [ ] Monitor cache hit rates

## Estimated Performance Gains

### By Phase

- **Phase 1:** 1-3 seconds improvement
- **Phase 2:** +300-600ms improvement
- **Phase 3:** +200-400ms improvement
- **Phase 4:** +30-50ms improvement

**TOTAL:** ~2-4 seconds improvement per typical request

## Monitoring Performance

### Enable SQL Logging

```python
# In app/db.py
engine = create_async_engine(
    DATABASE_URL,
    echo=True,  # Enable SQL logging
    pool_pre_ping=True
)
```

### Query Profiling

```python
# Add to routes for profiling
import time
import logging

logger = logging.getLogger(__name__)

@router.get("/documents")
async def list_documents():
    start = time.time()
    # ... query logic ...
    elapsed = time.time() - start
    logger.info(f"Query took {elapsed*1000:.2f}ms")
```

### Database Query Analysis

```sql
-- PostgreSQL query stats
SELECT query, calls, total_time, mean_time
FROM pg_stat_statements
ORDER BY total_time DESC
LIMIT 20;
```

## Implementation Examples

### Fixing N+1 Queries

**Before:**
```python
# This causes N+1 queries
documents = await session.execute(select(Document))
for doc in documents:
    chunks = doc.chunks  # Separate query per document!
```

**After:**
```python
# Single query with eager loading
from sqlalchemy.orm import selectinload

documents = await session.execute(
    select(Document).options(selectinload(Document.chunks))
)
```

### Pagination with Window Functions

**Before:**
```python
# Two queries
total = await session.execute(select(func.count(Document.id)))
documents = await session.execute(select(Document).limit(50))
```

**After:**
```python
# Single query with window function
from sqlalchemy import func, over

query = select(
    Document,
    func.count().over().label('total_count')
).limit(50)
```

### Adding Database Indexes

```python
# In app/db.py model definitions
class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    search_space_id = Column(Integer, ForeignKey("search_spaces.id"), index=True)

    # Composite indexes
    __table_args__ = (
        Index('idx_doc_user_search_space', 'user_id', 'search_space_id'),
        Index('idx_doc_created_at', 'created_at'),
    )
```

## Related Documentation

- Full detailed report: `docs/reports/2025-11-performance.md`
- Database maintenance: `docs/deployment/DEPLOYMENT_GUIDE.md`
- Security guidelines: `docs/development/SECURITY.md`

---

**Last Updated:** November 29, 2025
