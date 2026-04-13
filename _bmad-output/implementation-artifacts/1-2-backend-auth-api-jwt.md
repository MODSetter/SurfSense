# Story 1.2: Triển khai Backend API Xác thực & JWT (Backend Auth API & JWT)

**Status:** done
**Epic:** Epic 1
**Story Key:** `1-2-backend-auth-api-jwt`

## 📖 Story Requirements (Context & PRD)
> This section maps directly to the original Product Requirements Document and Epics definition.

As a Người dùng,
I want gọi API an toàn để tạo tài khoản, đăng nhập và lấy mã Token (JWT),
So that hệ thống xác thực được danh tính của tôi và kích hoạt RLS (Row-level Security) bảo vệ dữ liệu trên Database Postgres.
**Acceptance Criteria:**
**Given** thông tin đăng nhập hợp lệ
**When** gửi request tới endpoint liên quan `/api/v1/auth/login`
**Then** hệ thống trả về mã JWT chứa userID hợp lệ, bọc trong cấu trúc Wrapper chuẩn `{ "data": {"token": "xxx"}, "error": null, "meta": null }`
**And** Cấu hình Row-Level Security (RLS) cơ bản cho bảng dữ liệu (người này không query được dữ liệu của người kia).

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

