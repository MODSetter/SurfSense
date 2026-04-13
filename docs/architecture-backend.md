# Kiến Trúc Hệ Thống: Backend (`surfsense_backend`)

## 1. Tổng Quan
Backend của SurfSense (viết bằng Python 3.12) chịu trách nhiệm chính trong việc xử lý Data Ingestion, Indexing, LLM Orchestration và cung cấp REST APIs cho các Client.

## 2. Công Nghệ Cốt Lõi
- **Môi trường Server**: FastAPI, Uvicorn
- **Database & ORM**: PostgreSQL, SQLAlchemy, Alembic (Migration), pgvector (Vector DB)
- **Task Queue & Background Jobs**: Celery, Redis
- **AI / LLM Framework**: LangChain, LangGraph, LiteLLM
- **Xử lý Dữ liệu**: Unstructured, Docling, Playwright

## 3. Cấu Trúc Mã Nguồn (Directory Structure)
```text
surfsense_backend/app/
├── agents/              # Định nghĩa LangGraph agents / chains để xử lý luồng AI
├── api/routes/          # Chứa các endpoint API (users, chat, documents...)
├── connectors/          # Logic kết nối bên thứ 3 (Google Drive, Slack, Composio)
├── db.py                # Điểm khai báo Core Models của SQLAlchemy
├── etl_pipeline/        # Pipeline trích xuất dữ liệu, chunking text, transform
├── indexing_pipeline/   # Chịu trách nhiệm tạo embedding và push vào VectorDB
├── prompts/             # Template lưu trữ prompt chuẩn cho các luồng LLM
├── schemas/             # Pydantic models (validation cho request/response)
├── services/            # Tầng Business Logic (CRUD, gọi API ngoài)
├── tasks/               # Các Celery task (Background jobs xử lý nặng)
└── utils/               # Các hàm tiện ích (helper functions, formats, parsing)
```

## 4. Pipeline Architecture & Search (Deep Dive)

### 4.1 ETL Pipeline (`etl_pipeline/`)
Chịu trách nhiệm trích xuất văn bản từ nhiều định dạng file khác nhau.
- **Entry point**: `EtlPipelineService.extract()` phân loại file (`classify_file`) thành các nhóm (PLAINTEXT, DIRECT_CONVERT, AUDIO, IMAGE, DOCUMENT).
- **Parsers Tích Hợp**:
  - `docling`: Xử lý PDF/tài liệu phức tạp (via `parse_with_docling`).
  - `unstructured`: Parser thay thế cho tài liệu chung.
  - `llamacloud` / `Azure Document Intelligence`: Dùng làm internal accelerator để tối ưu chi phí/tốc độ.
  - `vision_llm`: Fallback parse ảnh nếu model Vision có sẵn.
  - `audio`: Dùng model transcribe.

### 4.2 Indexing Pipeline (`indexing_pipeline/`)
Chịu trách nhiệm chunking, tính toán embedding, chống trùng lặp và lưu trữ vào Vector DB.
- **State Feedback Tức Thì**: `create_placeholder_documents()` tạo ra các Document "Pending" vào DB ngay khi upload, giúp đồng bộ Zero Sync hiển thị UI lập tức.
- **Deduplication**: Dựa vào `compute_content_hash` và `compute_unique_identifier_hash` để chống duplicate khi document đã tồn tại và không đổi.
- **Chunking & Embedding**: Chạy bất đồng bộ (`asyncio.to_thread`) với hàm `chunk_text()` (có hỗ trợ riêng cho code chunking) và `embed_texts()` (chạy qua LiteLLM/OpenAI).
- **Concurrency Control**: Hàm `index_batch_parallel()` dùng `asyncio.Semaphore` để giới hạn số luồng (mặc định 4) tránh rate-limit từ APIs.

### 4.3 Retriever & Hybrid Search (`retriever/`)
Kết hợp sức mạnh Full-text search của Postgres và Vector search của `pgvector`.
- **Hybrid Search Flow (`chunks_hybrid_search.py`)**: 
  - Tính toán tsvector/tsquery (Keyword Search) và L2 Distance / Cosine Similarity `Chunk.embedding.op("<=>")` (Semantic Search).
  - Sử dụng chung RRF (Reciprocal Rank Fusion) ở cấp database (bằng CTE) để cho điểm `1.0 / (k + rank)`.
  - Phân trang & giới hạn: Fetch một số chunk nhất định mỗi document bằng `ROW_NUMBER()` trong subquery, tăng performance khi đọc những file dài/nhiều chunk.

## 5. Patterns Hiện Có
- **Tiêm Phụ Thuộc (Dependency Injection)**: Backend chia nhỏ logic theo các Service Class (`services/`, `EtlPipelineService`, `IndexingPipelineService`) sau đó inject vào Router thông qua `Depends()`. 
- **Bất Đồng Bộ (Asynchronous Operations)**:
  - Database Call: Sử dụng `asyncpg` và session async từ SQLAlchemy.
  - Xử lý nặng (Compute-Bound): Offload qua `asyncio.to_thread()` (VD: chunking, embedding generation).
- **Tách Biệt Task Queue**: Các thao tác Indexing bulk hoặc crawl dữ liệu qua Playwright đều được push qua Redis để Celery worker processing.

## 6. Deployment Info
Dự án được triển khai bằng Docker (có `docker-compose.yml` đi kèm cho Dev Environment chạy đủ bộ FastAPI, Postgres (pg17 vector), Redis, Celery Worker, Zero-Cache cache sync daemon).
