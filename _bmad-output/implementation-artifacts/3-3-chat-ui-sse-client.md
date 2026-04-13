# Story 3.3: Giao diện Khung Chat & Tiếp nhận Streaming (Chat UI & SSE Client)

**Status:** done
**Epic:** Epic 3
**Story Key:** `3-3-chat-ui-sse-client`

## 📖 Story Requirements (Context & PRD)
> This section maps directly to the original Product Requirements Document and Epics definition.

As a Người dùng,
I want thấy AI gõ từng chữ một vào màn hình chat kèm format Markdown đàng hoàng,
So that tôi không phải mòn mỏi nhìn biểu tượng Loading như các web đời cũ.
**Acceptance Criteria:**
**Given** tôi vừa bấm gửi câu hỏi "Ping"
**When** Next.js client mở luồng SSE kết nối về FastAPI
**Then** tin nhắn được append dần lên UI mượt mà với hoạt ảnh <150ms
**And** render được định dạng Markdown cơ bản (Bold, List, Code block) một cách trơn tru, không xộc xệch nhảy dòng khó chịu.

## 🏗️ Architecture & Technical Guardrails
> Critical instructions for the development agent based on the project's established architecture.

### Technical Requirements
- Language/Framework: React, Next.js (TypeScript) for Web; FastAPI (Python) for Backend.
- Database: Prisma/Supabase.
- Strict Type checking must be enforced. No `any` types.

### Code Organization
This story is currently marked as `done`. Implementation should target the following components/files:

- `surfsense_web/components/public-chat-snapshots/public-chat-snapshot-row.tsx`
- `surfsense_web/components/chat-comments/comment-panel-container/comment-panel-container.tsx`
- `surfsense_backend/app/agents/new_chat/checkpointer.py`
- `surfsense_web/components/chat-comments/comment-item/types.ts`
- `surfsense_backend/app/agents/new_chat/tools/google_calendar/create_event.py`
- `surfsense_backend/app/routes/public_chat_routes.py`
- `surfsense_web/components/chat-comments/comment-composer/comment-composer.tsx`
- `surfsense_web/components/public-chat/public-chat-not-found.tsx`

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

