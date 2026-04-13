# Story 1.3: Giao diện Đăng nhập & Tích hợp Token vào Zero-Client (Frontend Auth UI)

**Status:** done

## PRD Requirements
As a Người dùng,
I want sử dụng giao diện trơn tru để đăng ký/đăng nhập,
So that tôi nhận được Token và ngay lập tức kết nối tới hệ thống dữ liệu Local-first an toàn qua Zero Client.
**Acceptance Criteria:**
**Given** tôi đang ở trạng thái khách (Guest) trên UI
**When** tôi điền form đăng nhập thành công
**Then** giao diện lưu token vào cục bộ và tự động khởi tạo instance `ZeroClient` để bắt đầu mở cầu nối WebSockets.
**And** khi tôi nhấn nút "Đăng xuất" (Log Out), hàm `onLogout()` tự động thực thi dọn dẹp sạch (purge) toàn bộ IndexedDB, chặn bảo mật.
**And** Giao diện (Form đăng nhập, nút bấm) ứng dụng quy chuẩn UX-DR1 (Màu Base Zinc/Accent Indigo, font Inter).
Người dùng dễ dàng kéo thả các tệp PDF/TXT lên hệ thống; hệ thống tự động bóc tách dữ liệu mượt mà trong nền mà không làm gián đoạn công việc. Họ nắm rõ tiến độ nạp file và làm chủ khối lượng tài liệu của mình.
**FRs covered:** FR1, FR2, FR3, FR4, FR12, FR13

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
