# Story 2.2: Triển khai API Tải lên & Giới hạn Rate Limit (Upload API & Rate Limiting)

**Status:** done
**Epic:** Epic 2
**Story Key:** `2-2-upload-api-rate-limiting`

## 📖 Story Requirements (Context & PRD)
> This section maps directly to the original Product Requirements Document and Epics definition.

As a Kỹ sư Backend,
I want xây dựng endpoint FastAPI cho việc upload tài liệu kèm cơ chế Rate Limit,
So that server tiếp nhận an toàn và ngăn chặn upload spam quá mức hệ thống cho phép.
**Acceptance Criteria:**
**Given** người dùng đăng nhập hợp lệ
**When** đính kèm file và gửi POST tới `/api/v1/documents`
**Then** hệ thống check user token, lưu file vô Storage, tạo record ở DB với status 'Queue', và trigger đẩy task vào Celery
**And** nếu user push liên tục quá mức quy định (token/hạn mức tải), API sẽ trả về lỗi `429 Too Many Requests` bọc trong error format chuẩn.

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

