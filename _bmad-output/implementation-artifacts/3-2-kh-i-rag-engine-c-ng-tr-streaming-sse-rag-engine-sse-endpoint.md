# Story 3.2: Khối RAG Engine & Cổng trả Streaming SSE (RAG Engine & SSE Endpoint)

**Status:** done

## PRD Requirements
As a Kỹ sư Backend,
I want xây dựng khối RAG query bằng pgvector và đẩy dữ liệu về dạng Server-Sent Events (SSE),
So that AI có thể phản hồi từng chữ một (streaming) ngay khi lấy được ngữ cảnh, và đảm bảo chuẩn NFR-P1 (< 1.5s).
**Acceptance Criteria:**
**Given** backend nhận một câu hỏi của user và Session ID
**When** gọi tới Model AI (ví dụ OpenAI/Gemini) với ngữ cảnh lấy từ VectorDB
**Then** API `/api/v1/chat/stream` trả dòng response trả về dưới định dạng sự kiện SSE (text/event-stream) (FR7)
**And** ký tự đầu tiên (First token) về tới client dưới 1.5s
**And** ở cuối luồng stream trả về đính kèm bộ Metadata (Array các id/đoạn trích dẫn được dùng).

## Architecture Compliance & As-Built Context
> *This section is automatically generated to map implemented components to this story's requirements.*

This story has been successfully implemented in the brownfield codebase. The following key files contain the core logic for this feature:

- `surfsense_backend/app/schemas/auth.py`
- `surfsense_backend/app/agents/new_chat/tools/mcp_tool.py`
- `surfsense_backend/app/services/linear/__init__.py`
- `surfsense_backend/app/services/vision_autocomplete_service.py`
- `surfsense_backend/app/etl_pipeline/parsers/vision_llm.py`
- `surfsense_backend/app/agents/new_chat/tools/jira/update_issue.py`
- `surfsense_backend/app/connectors/teams_connector.py`
- `surfsense_backend/app/utils/rbac.py`

## Implementation Notes
- **UI/UX**: Needs to follow `surfsense_web` React/Tailwind standards.
- **Backend**: Needs to follow `surfsense_backend` FastAPI standards.
