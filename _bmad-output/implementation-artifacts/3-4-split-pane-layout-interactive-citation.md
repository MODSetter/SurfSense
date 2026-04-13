# Story 3.4: Kiến trúc Split-Pane & Tương tác Trích dẫn (Split-Pane Layout & Interactive Citation)

**Status:** done
**Epic:** Epic 3
**Story Key:** `3-4-split-pane-layout-interactive-citation`

## 📖 Story Requirements (Context & PRD)
> This section maps directly to the original Product Requirements Document and Epics definition.

As a Người dùng,
I want đọc khung chat ở một bên và văn bản gốc ở bên cạnh trên cùng 1 màn hình, bấm vào thẻ [1] ở chat là bên kia nhảy text tương ứng,
So that tôi có thể đối chiếu thông tin AI "bịa" hay "thật" ngay lập tức mà không phải tìm mỏi mắt.
**Acceptance Criteria:**
**Given** UI chia 2 bên (Split-Pane - bằng react-resizable-panels) - Chat trái, Doc phải (UX-DR3)
**When** AI trả lời xong có đính kèm cite `[1]`, tôi click vào `[1]`
**Then** bảng Document tự động đổi sang file tương ứng và auto-scroll + highlight dải vàng đúng dòng text đó (UX-DR4).

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

