# Story 4.1: Đồng bộ Danh sách Phiên Chat & Lịch sử Tin nhắn (Chat History Sync)

**Status:** done

## PRD Requirements
As a Người dùng,
I want danh sách lịch sử các phiên chat và tin nhắn bên trong tự động đồng bộ xuống máy tôi qua Zero-client,
So that tôi mở app lên là thấy ngay lập tức lịch sử cũ (FR8, FR9) và đọc liên tiếp không cần chờ load từ internet (FR10).
**Acceptance Criteria:**
**Given** thiết bị của tôi đã từng kết nối mạng trước đó
**When** tôi chọn một Session cũ (như hôm qua) trong Sidebar
**Then** hệ thống query trực tiếp từ IndexedDB cục bộ qua thư viện `@rocicorp/zero` và móc lên UI
**And** thời gian data mới từ server đẩy cập nhật xuống dưới Local Storage luôn đảm bảo dưới 3s (NFR-P2).

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
