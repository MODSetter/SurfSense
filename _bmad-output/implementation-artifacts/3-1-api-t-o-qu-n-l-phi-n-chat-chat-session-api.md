# Story 3.1: API Tạo & Quản lý Phiên Chat (Chat Session API)

**Status:** done

## PRD Requirements
As a Người dùng,
I want tạo một phiên trò chuyện (chat session) mới với AI,
So that tôi có thể bắt đầu một định mức hội thoại mới, tách bạch hoàn toàn với các chủ đề cũ.
**Acceptance Criteria:**
**Given** cửa sổ Chat
**When** tôi chọn lệnh "New Chat" hoặc nhập thẳng vào input đầu tiên
**Then** hệ thống tạo một "Session" ID mới trên Database và lưu tin nhắn đầu tiên của user (FR5, FR6)
**And** trả về data qua REST API theo wrapper chuẩn để client chốt phiên làm việc.

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
