# Story 3.3: Giao diện Khung Chat & Tiếp nhận Streaming (Chat UI & SSE Client)

**Status:** done

## PRD Requirements
As a Người dùng,
I want thấy AI gõ từng chữ một vào màn hình chat kèm format Markdown đàng hoàng,
So that tôi không phải mòn mỏi nhìn biểu tượng Loading như các web đời cũ.
**Acceptance Criteria:**
**Given** tôi vừa bấm gửi câu hỏi "Ping"
**When** Next.js client mở luồng SSE kết nối về FastAPI
**Then** tin nhắn được append dần lên UI mượt mà với hoạt ảnh <150ms
**And** render được định dạng Markdown cơ bản (Bold, List, Code block) một cách trơn tru, không xộc xệch nhảy dòng khó chịu.

## Architecture Compliance & As-Built Context
> *This section is automatically generated to map implemented components to this story's requirements.*

This story has been successfully implemented in the brownfield codebase. The following key files contain the core logic for this feature:

- `surfsense_backend/app/agents/new_chat/utils.py`
- `surfsense_backend/app/schemas/chat_session_state.py`
- `surfsense_backend/app/agents/new_chat/tools/mcp_tool.py`
- `surfsense_backend/app/etl_pipeline/parsers/vision_llm.py`
- `surfsense_backend/app/agents/new_chat/tools/jira/update_issue.py`
- `surfsense_backend/app/routes/public_chat_routes.py`
- `surfsense_backend/app/schemas/new_chat.py`
- `surfsense_backend/app/tasks/chat/stream_new_chat.py`

## Implementation Notes
- **UI/UX**: Needs to follow `surfsense_web` React/Tailwind standards.
- **Backend**: Needs to follow `surfsense_backend` FastAPI standards.
