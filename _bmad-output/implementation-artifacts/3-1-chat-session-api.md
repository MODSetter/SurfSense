# Story 3.1: API Tạo & Quản lý Phiên Chat (Chat Session API)

**Status:** done
**Epic:** Epic 3
**Story Key:** `3-1-chat-session-api`

## 📖 Story Requirements (Context & PRD)
> This section maps directly to the original Product Requirements Document and Epics definition.

As a Người dùng,
I want tạo một phiên trò chuyện (chat session) mới với AI,
So that tôi có thể bắt đầu một định mức hội thoại mới, tách bạch hoàn toàn với các chủ đề cũ.
**Acceptance Criteria:**
**Given** cửa sổ Chat
**When** tôi chọn lệnh "New Chat" hoặc nhập thẳng vào input đầu tiên
**Then** hệ thống tạo một "Session" ID mới trên Database và lưu tin nhắn đầu tiên của user (FR5, FR6)
**And** trả về data qua REST API theo wrapper chuẩn để client chốt phiên làm việc.

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

