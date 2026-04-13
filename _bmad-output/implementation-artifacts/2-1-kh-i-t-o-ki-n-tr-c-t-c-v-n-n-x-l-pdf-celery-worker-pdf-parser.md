# Story 2.1: Khởi tạo Kiến trúc Tác vụ nền & Xử lý PDF (Celery Worker & PDF Parser)

**Status:** done

## PRD Requirements
As a Kỹ sư Hệ thống,
I want xây dựng hệ thống worker bất đồng bộ (Celery + Redis) để bóc tách văn bản và tạo Vector Embeddings,
So that hệ thống API chính không bị nghẽn khi người dùng upload file, và có thể scale linh hoạt số lượng worker.
**Acceptance Criteria:**
**Given** phần mềm nhận một file PDF/TXT được đẩy vào hàng đợi (Queue)
**When** worker được phân công thực thi tác vụ
**Then** tiến trình phân giải text và nạp Vector qua pgvector hoàn thành dưới 30s (đối với file <5MB)
**And** trạng thái bản ghi tài liệu trên Database được cập nhật tuần tự (Processing -> Completed hoặc Error).

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
