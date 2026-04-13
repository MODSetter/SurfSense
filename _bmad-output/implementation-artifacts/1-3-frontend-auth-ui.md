# Story 1.3: Giao diện Đăng nhập & Tích hợp Token vào Zero-Client (Frontend Auth UI)

**Status:** done
**Epic:** Epic 1
**Story Key:** `1-3-frontend-auth-ui`

## 📖 Story Requirements (Context & PRD)
> This section maps directly to the original Product Requirements Document and Epics definition.

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

## 🏗️ Architecture & Technical Guardrails
> Critical instructions for the development agent based on the project's established architecture.

### Technical Requirements
- Language/Framework: React, Next.js (TypeScript) for Web; FastAPI (Python) for Backend.
- Database: Prisma/Supabase.
- Strict Type checking must be enforced. No `any` types.

### Code Organization
This story is currently marked as `done`. Implementation should target the following components/files:

- `surfsense_backend/app/connectors/dropbox/client.py`
- `surfsense_backend/app/schemas/incentive_tasks.py`
- `surfsense_backend/app/utils/proxy_config.py`
- `surfsense_web/components/chat-comments/comment-panel-container/comment-panel-container.tsx`
- `surfsense_web/components/tool-ui/write-todos.tsx`
- `surfsense_web/components/shared/image-config-dialog.tsx`
- `surfsense_backend/app/users.py`
- `surfsense_web/components/ui/dropdown-menu.tsx`

### Developer Agent Constraints
1. **No Destructive Refactors**: Extend existing modules when possible.
2. **Context Check**: Always refer back to `task.md` and use Context7 to verify latest SDK usages.
3. **BMad Standard**: Update the sprint status using standard metrics.

## 🧪 Testing & Validation Requirements
- All new endpoints must be tested.
- Frontend components should gracefully degrade.
- Do not introduce regressions into existing user workflows.

## 📈 Completion Status
*(To be updated by the agent when completing this story)*
- Start Date: _____________
- Completion Date: _____________
- Key Files Changed:
  - 

