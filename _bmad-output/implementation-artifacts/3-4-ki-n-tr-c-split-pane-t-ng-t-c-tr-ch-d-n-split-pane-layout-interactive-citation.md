# Story 3.4: Kiến trúc Split-Pane & Tương tác Trích dẫn (Split-Pane Layout & Interactive Citation)

**Status:** done

## PRD Requirements
As a Người dùng,
I want đọc khung chat ở một bên và văn bản gốc ở bên cạnh trên cùng 1 màn hình, bấm vào thẻ [1] ở chat là bên kia nhảy text tương ứng,
So that tôi có thể đối chiếu thông tin AI "bịa" hay "thật" ngay lập tức mà không phải tìm mỏi mắt.
**Acceptance Criteria:**
**Given** UI chia 2 bên (Split-Pane - bằng react-resizable-panels) - Chat trái, Doc phải (UX-DR3)
**When** AI trả lời xong có đính kèm cite `[1]`, tôi click vào `[1]`
**Then** bảng Document tự động đổi sang file tương ứng và auto-scroll + highlight dải vàng đúng dòng text đó (UX-DR4).

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
