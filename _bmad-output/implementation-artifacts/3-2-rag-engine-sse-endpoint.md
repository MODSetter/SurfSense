# Story 3.2: Khối RAG Engine & Cổng trả Streaming SSE (RAG Engine & SSE Endpoint)

**Status:** done
**Epic:** Epic 3
**Story Key:** `3-2-rag-engine-sse-endpoint`

## 📖 Story Requirements (Context & PRD)
> This section maps directly to the original Product Requirements Document and Epics definition.

As a Kỹ sư Backend,
I want xây dựng khối RAG query bằng pgvector và đẩy dữ liệu về dạng Server-Sent Events (SSE),
So that AI có thể phản hồi từng chữ một (streaming) ngay khi lấy được ngữ cảnh, và đảm bảo chuẩn NFR-P1 (< 1.5s).
**Acceptance Criteria:**
**Given** backend nhận một câu hỏi của user và Session ID
**When** gọi tới Model AI (ví dụ OpenAI/Gemini) với ngữ cảnh lấy từ VectorDB
**Then** API `/api/v1/chat/stream` trả dòng response trả về dưới định dạng sự kiện SSE (text/event-stream) (FR7)
**And** ký tự đầu tiên (First token) về tới client dưới 1.5s
**And** ở cuối luồng stream trả về đính kèm bộ Metadata (Array các id/đoạn trích dẫn được dùng).

## 🏗️ Architecture & Technical Guardrails
> Critical instructions for the development agent based on the project's established architecture.

### Technical Requirements
- Language/Framework: React, Next.js (TypeScript) for Web; FastAPI (Python) for Backend.
- Database: Prisma/Supabase.
- Strict Type checking must be enforced. No `any` types.

### Code Organization
This story is currently marked as `done`. Implementation should target the following components/files:

- `surfsense_backend/app/connectors/dropbox/client.py`
- `surfsense_backend/app/schemas/incentive_tasks.py`
- `surfsense_backend/app/utils/proxy_config.py`
- `surfsense_web/components/chat-comments/comment-panel-container/comment-panel-container.tsx`
- `surfsense_web/components/tool-ui/write-todos.tsx`
- `surfsense_web/components/shared/image-config-dialog.tsx`
- `surfsense_backend/app/users.py`
- `surfsense_web/components/ui/dropdown-menu.tsx`

### Developer Agent Constraints
1. **No Destructive Refactors**: Extend existing modules when possible.
2. **Context Check**: Always refer back to `task.md` and use Context7 to verify latest SDK usages.
3. **BMad Standard**: Update the sprint status using standard metrics.

## 🧪 Testing & Validation Requirements
- All new endpoints must be tested.
- Frontend components should gracefully degrade.
- Do not introduce regressions into existing user workflows.

## 📈 Completion Status
*(To be updated by the agent when completing this story)*
- Start Date: _____________
- Completion Date: _____________
- Key Files Changed:
  - 

