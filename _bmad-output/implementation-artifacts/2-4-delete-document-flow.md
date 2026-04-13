# Story 2.4: API và Giao diện Xóa tài liệu khỏi Workspace (Delete Document Flow)

**Status:** done
**Epic:** Epic 2
**Story Key:** `2-4-delete-document-flow`

## 📖 Story Requirements (Context & PRD)
> This section maps directly to the original Product Requirements Document and Epics definition.

As a Người dùng,
I want chọn một tài liệu cũ và xóa hoàn toàn,
So that không gian lưu trữ được dọn dẹp và AI sẽ không bao giờ truy cập nội dung đó nữa.
**Acceptance Criteria:**
**Given** người dùng đang có tài liệu hiển thị trên danh sách
**When** người dùng click icon "Xoá" file
**Then** dữ liệu tài liệu lập tức bị loại bỏ khỏi giao diện UI do cơ chế optimism update của Zero
**And** trên Database, bản ghi bị xoá hoặc mark deleted, kèm theo việc dọn dẹp các Vectors rác liên quan trong background.
Người dùng có trải nghiệm truy vấn kho tài liệu "không độ trễ" (Instant Action) thông qua chat. Kết quả được stream về theo thời gian thực như một trợ lý xịn, tích hợp hệ thống Split-pane tinh tế để đối chiếu thẳng với Nguồn trích dẫn.
**FRs covered:** FR5, FR6, FR7

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

