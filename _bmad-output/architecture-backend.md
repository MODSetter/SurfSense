# Kiến Trúc Backend

## Tổng Quan
Backend của SurfSense là một ứng dụng **Python FastAPI** mạnh mẽ, được thiết kế cho các quy trình làm việc agentic hiệu suất cao. Nó đóng vai trò là hệ thống thần kinh trung ương, điều phối RAG (Retrieval-Augmented Generation), quản lý bộ nhớ của agent (agent memory), và xử lý tương tác với các mô hình ngôn ngữ lớn (LLMs).

## Các Thành Phần Cốt Lõi

### 1. Framework AI Agent (DeepAgents & LangGraph)
- **DeepAgents**: Framework tùy chỉnh để xây dựng các AI agents tự chủ (autonomous agents).
- **LangGraph**: Quản lý StateGraph (đồ thị trạng thái) và quy trình điều phối cho các suy luận phức tạp, nhiều bước.
- **Workflow**: Người dùng gửi truy vấn -> LangGraph xác định ý định (Routing) -> Kích hoạt các Agents cụ thể (Search Agent, Coding Agent, v.v.).

### 2. Dịch Vụ Dữ Liệu (Data Services)
- **Primary Database**: **Postgres** (với extension `pgvector`) lưu trữ:
    - Dữ liệu người dùng & ứng dụng.
    - Vector Embeddings cho tìm kiếm ngữ nghĩa (semantic search).
    - Lịch sử chat và phiên làm việc.
- **ORM**: **SQLAlchemy (Async)** dùng cho các tương tác cơ sở dữ liệu quan hệ.
- **Caching/Queue**: **Redis** dùng cho hàng đợi tác vụ (Celery broker) và caching phản hồi ngắn hạn.

### 3. Hệ Thống Tìm Kiếm & RAG
- **Vector Store**: Sử dụng `pgvector` để lưu trữ embeddings của tài liệu.
- **Retriever**: Logic tùy chỉnh trong `app/retriever/` để lấy ngữ cảnh (fetches context) dựa trên sự tương đồng (similarity) và metadata filtering.
- **Ingestion Pipeline**: Celery workers xử lý việc tải tài liệu từ nguồn bên ngoài, chia nhỏ văn bản (chunking), tạo embedding, và lưu trữ.

### 4. Kết Nối Ứng Dụng Ngoài (Connectors)
- **Kiến Trúc**: Modular adapter pattern.
- **Hỗ trợ**: Slack, Google Drive, Notion, GitHub, v.v. (30+ integrations).
- **Cơ chế**: Webhooks hoặc định kỳ polling (thực hiện bởi Celery beats).

## Luồng Dữ Liệu (Data Flow)

1. **Request**: Client (Web/Extension) gửi REST request tới FastAPI Endpoints.
2. **Auth**: Middleware xác thực JWT/OAuth token.
3. **Controller**: Route handler (`app/routes/`) nhận request, gọi Service layer.
4. **Processing**:
    - Nếu là tác vụ nhanh (CRUD): Xử lý trực tiếp với DB.
    - Nếu là tác vụ AI: Đẩy vào LangGraph runner để streaming phản hồi.
    - Nếu là tác vụ dài (Ingestion): Đẩy job vào Redis queue cho Celery.
5. **Response**: Trả về JSON hoặc Streaming Response (SSE).

## Critical RAG Pipeline Fix (Feb 2026)

### DexScreener Connector Integration

**Issue Discovered**: DexScreener connector was successfully implemented and indexed data into `search_space_id = 7`, but the LLM could not retrieve this data when users asked about crypto prices.

**Root Cause**: Missing connector mapping in `_CONNECTOR_TYPE_TO_SEARCHABLE` dictionary.

**File**: `surfsense_backend/app/agents/new_chat/chat_deepagent.py`

**The Problem**:
```python
# BEFORE (Missing mapping)
_CONNECTOR_TYPE_TO_SEARCHABLE = {
    "GMAIL": "GMAIL",
    "GOOGLE_DRIVE_CONNECTOR": "GOOGLE_DRIVE",
    "SLACK_CONNECTOR": "SLACK",
    # ... other connectors ...
    # ❌ DEXSCREENER_CONNECTOR was MISSING
}
```

**Impact**:
1. `connector_service.get_available_connectors()` returned DexScreener connector type
2. `_map_connectors_to_searchable_types()` could not find mapping → ignored DexScreener
3. LLM's tool description didn't mention DexScreener as available
4. LLM never searched DexScreener data, responded "can't see price data"

**The Fix**:
```python
# AFTER (Fixed)
_CONNECTOR_TYPE_TO_SEARCHABLE = {
    "GMAIL": "GMAIL",
    "GOOGLE_DRIVE_CONNECTOR": "GOOGLE_DRIVE",
    "SLACK_CONNECTOR": "SLACK",
    # ... other connectors ...
    "DEXSCREENER_CONNECTOR": "DEXSCREENER_CONNECTOR",  # ✅ Added
}
```

**Verification**:
- User query: *"What's the current price of WETH?"*
- LLM successfully retrieved: ~$2,442 USD with DexScreener citations
- Citations linked to indexed trading pairs with metadata (chain, DEX, liquidity, volume)

**Lesson Learned**: When adding new connectors, **ALWAYS** update the `_CONNECTOR_TYPE_TO_SEARCHABLE` mapping to enable RAG retrieval. This is a critical step that's easy to miss during implementation.

---

## Connector Architecture Pattern

### Adding New Connectors (Best Practices)

Khi thêm connector mới, cần update **4 locations**:

1. **Connector Class** (`app/connectors/`)
   - Implement data fetching logic
   - Format data to markdown for indexing

2. **Database Enum** (`app/db.py`)
   - Add to `SearchSourceConnectorType` enum

3. **API Routes** (`app/routes/`)
   - Create add/delete/test endpoints

4. **RAG Mapping** (`app/agents/new_chat/chat_deepagent.py`) ⚠️ **CRITICAL**
   - Add to `_CONNECTOR_TYPE_TO_SEARCHABLE` dictionary
   - **Failure to do this = LLM cannot access connector data**

---

## Hybrid Crypto Data Architecture (Feb 2026)

### Vấn Đề: Data Freshness cho Crypto

Kiến trúc Connector ban đầu sử dụng **periodic indexing** (5-60 phút) để index data từ DexScreener vào database. Điều này phù hợp cho:
- ✅ Phân tích lịch sử, xu hướng
- ✅ Research & context
- ❌ **KHÔNG** phù hợp cho real-time price queries

### Giải Pháp: Hybrid Approach (RAG + Real-time)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         USER QUERY                                      │
│                    "Phân tích BULLA cho tôi"                            │
└─────────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      AI AGENT (LangGraph)                               │
│                                                                         │
│   Quyết định dùng tool nào dựa trên intent:                             │
│                                                                         │
│   ┌─────────────────────────┐    ┌─────────────────────────────────┐   │
│   │  RAG Tools              │    │  Real-time Tools                │   │
│   │  (Indexed Data)         │    │  (Live API Calls)               │   │
│   ├─────────────────────────┤    ├─────────────────────────────────┤   │
│   │ search_knowledge_base   │    │ get_live_token_price            │   │
│   │                         │    │ get_live_token_data             │   │
│   │ • Xu hướng lịch sử      │    │ • Giá hiện tại                  │   │
│   │ • Phân tích quá khứ     │    │ • Volume live                   │   │
│   │ • Context & tin tức     │    │ • Giao dịch real-time           │   │
│   └─────────────────────────┘    └─────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
```

### Real-time Tools Implementation

**File**: `surfsense_backend/app/agents/new_chat/tools/crypto_realtime.py`

| Tool | Mô tả | Use Case |
|------|-------|----------|
| `get_live_token_price` | Lấy giá real-time từ DexScreener API | "Giá SOL bây giờ?" |
| `get_live_token_data` | Lấy full market data (price, volume, txns) | "Volume giao dịch BULLA?" |

**Đặc điểm**:
- Gọi trực tiếp DexScreener API (không qua indexed data)
- Không cần dependencies (`requires=[]`)
- Trả về data với `data_source: "DexScreener API (Real-time)"`

### Khi Nào AI Dùng Tool Nào?

| Query Type | Tool | Ví dụ |
|------------|------|-------|
| Giá hiện tại | `get_live_token_price` | "Giá BULLA bây giờ là bao nhiêu?" |
| Market data live | `get_live_token_data` | "Volume giao dịch SOL thế nào?" |
| Phân tích lịch sử | `search_knowledge_base` | "BULLA tuần này như thế nào?" |
| Phân tích tổng hợp | **Cả hai** | "Phân tích BULLA cho tôi" |

### Frontend Tool-UI Components

**Files**:
- `surfsense_web/components/tool-ui/crypto/live-token-price.tsx`
- `surfsense_web/components/tool-ui/crypto/live-token-data.tsx`

Các components này render kết quả từ real-time tools trong chat interface với:
- Badge "Real-time" để phân biệt với RAG data
- Price change indicators (5m, 1h, 6h, 24h)
- Transaction activity bar (buys vs sells)
- Link đến DexScreener chart

---
