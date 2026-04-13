# Story 4.2: Giao diện Phân rã Ân hạn khi ngắt mạng (Graceful Degradation Offline UI)

**Status:** done

## PRD Requirements
As a Người dùng,
I want hệ thống tự động khóa các tính năng cần internet như "Chat/Gửi tin/Upload" khi tôi mất wifi,
So that tôi không bị văng lỗi hay hiện màn hình đơ cứng, thay vào đó vẫn thong dong đọc nội dung cũ (NFR-R1).
**Acceptance Criteria:**
**Given** người dùng cấu hình ngắt mạng cố ý hoặc đột ngột mất wifi
**When** họ đang mở app
**Then** giao diện tự động bật mode Graceful Degradation: Input chat bị disable, nút Upload file bị mờ (muted xám)
**And** người dùng vẫn có thể click đọc văn bản trên màn Split-Pane thoăn thoắt không trễ (UX-DR6).

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
