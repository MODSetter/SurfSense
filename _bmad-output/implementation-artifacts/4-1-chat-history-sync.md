# Story 4.1: Đồng bộ Danh sách Phiên Chat & Lịch sử Tin nhắn (Chat History Sync)

**Status:** done
**Epic:** Epic 4
**Story Key:** `4-1-chat-history-sync`

## 📖 Story Requirements (Context & PRD)
> This section maps directly to the original Product Requirements Document and Epics definition.

As a Người dùng,
I want danh sách lịch sử các phiên chat và tin nhắn bên trong tự động đồng bộ xuống máy tôi qua Zero-client,
So that tôi mở app lên là thấy ngay lập tức lịch sử cũ (FR8, FR9) và đọc liên tiếp không cần chờ load từ internet (FR10).
**Acceptance Criteria:**
**Given** thiết bị của tôi đã từng kết nối mạng trước đó
**When** tôi chọn một Session cũ (như hôm qua) trong Sidebar
**Then** hệ thống query trực tiếp từ IndexedDB cục bộ qua thư viện `@rocicorp/zero` và móc lên UI
**And** thời gian data mới từ server đẩy cập nhật xuống dưới Local Storage luôn đảm bảo dưới 3s (NFR-P2).

## 🏗️ Architecture & Technical Guardrails
> Critical instructions for the development agent based on the project's established architecture.

### Technical Requirements
- Language/Framework: React, Next.js (TypeScript) for Web; FastAPI (Python) for Backend.
- Database: Prisma/Supabase.
- Strict Type checking must be enforced. No `any` types.

### Code Organization
This story is currently marked as `done`. Implementation should target the following components/files:

*(Files to be determined during implementation)*

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

