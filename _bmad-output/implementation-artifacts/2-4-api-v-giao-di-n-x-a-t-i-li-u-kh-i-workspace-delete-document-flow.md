# Story 2.4: API và Giao diện Xóa tài liệu khỏi Workspace (Delete Document Flow)

**Status:** done

## PRD Requirements
As a Người dùng,
I want chọn một tài liệu cũ và xóa hoàn toàn,
So that không gian lưu trữ được dọn dẹp và AI sẽ không bao giờ truy cập nội dung đó nữa.
**Acceptance Criteria:**
**Given** người dùng đang có tài liệu hiển thị trên danh sách
**When** người dùng click icon "Xoá" file
**Then** dữ liệu tài liệu lập tức bị loại bỏ khỏi giao diện UI do cơ chế optimism update của Zero
**And** trên Database, bản ghi bị xoá hoặc mark deleted, kèm theo việc dọn dẹp các Vectors rác liên quan trong background.
Người dùng có trải nghiệm truy vấn kho tài liệu "không độ trễ" (Instant Action) thông qua chat. Kết quả được stream về theo thời gian thực như một trợ lý xịn, tích hợp hệ thống Split-pane tinh tế để đối chiếu thẳng với Nguồn trích dẫn.
**FRs covered:** FR5, FR6, FR7

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
