# Story 1.2: Triển khai Backend API Xác thực & JWT (Backend Auth API & JWT)

**Status:** done

## PRD Requirements
As a Người dùng,
I want gọi API an toàn để tạo tài khoản, đăng nhập và lấy mã Token (JWT),
So that hệ thống xác thực được danh tính của tôi và kích hoạt RLS (Row-level Security) bảo vệ dữ liệu trên Database Postgres.
**Acceptance Criteria:**
**Given** thông tin đăng nhập hợp lệ
**When** gửi request tới endpoint liên quan `/api/v1/auth/login`
**Then** hệ thống trả về mã JWT chứa userID hợp lệ, bọc trong cấu trúc Wrapper chuẩn `{ "data": {"token": "xxx"}, "error": null, "meta": null }`
**And** Cấu hình Row-Level Security (RLS) cơ bản cho bảng dữ liệu (người này không query được dữ liệu của người kia).

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
