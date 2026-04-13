# Story 2.1: Khởi tạo Kiến trúc Tác vụ nền & Xử lý PDF (Celery Worker & PDF Parser)

**Status:** done
**Epic:** Epic 2
**Story Key:** `2-1-celery-worker-pdf-parser`

## 📖 Story Requirements (Context & PRD)
> This section maps directly to the original Product Requirements Document and Epics definition.

As a Kỹ sư Hệ thống,
I want xây dựng hệ thống worker bất đồng bộ (Celery + Redis) để bóc tách văn bản và tạo Vector Embeddings,
So that hệ thống API chính không bị nghẽn khi người dùng upload file, và có thể scale linh hoạt số lượng worker.
**Acceptance Criteria:**
**Given** phần mềm nhận một file PDF/TXT được đẩy vào hàng đợi (Queue)
**When** worker được phân công thực thi tác vụ
**Then** tiến trình phân giải text và nạp Vector qua pgvector hoàn thành dưới 30s (đối với file <5MB)
**And** trạng thái bản ghi tài liệu trên Database được cập nhật tuần tự (Processing -> Completed hoặc Error).

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

