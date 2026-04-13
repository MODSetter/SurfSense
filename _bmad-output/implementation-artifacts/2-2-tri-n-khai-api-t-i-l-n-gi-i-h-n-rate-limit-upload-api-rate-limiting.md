# Story 2.2: Triển khai API Tải lên & Giới hạn Rate Limit (Upload API & Rate Limiting)

**Status:** done

## PRD Requirements
As a Kỹ sư Backend,
I want xây dựng endpoint FastAPI cho việc upload tài liệu kèm cơ chế Rate Limit,
So that server tiếp nhận an toàn và ngăn chặn upload spam quá mức hệ thống cho phép.
**Acceptance Criteria:**
**Given** người dùng đăng nhập hợp lệ
**When** đính kèm file và gửi POST tới `/api/v1/documents`
**Then** hệ thống check user token, lưu file vô Storage, tạo record ở DB với status 'Queue', và trigger đẩy task vào Celery
**And** nếu user push liên tục quá mức quy định (token/hạn mức tải), API sẽ trả về lỗi `429 Too Many Requests` bọc trong error format chuẩn.

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
