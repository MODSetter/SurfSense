# Story 4.3: Tích hợp Chỉ báo Trạng thái Mạng Toàn Cục (Global Network & Sync Indicators)

**Status:** done
**Epic:** Epic 4
**Story Key:** `4-3-global-network-sync-indicators`

## 📖 Story Requirements (Context & PRD)
> This section maps directly to the original Product Requirements Document and Epics definition.

As a Người dùng,
I want thấy một icon nhỏ hoặc dải màu trực quan cho biết App đang Online, Offline, hay Syncing,
So that tôi chủ động biết ứng dụng có đang "sống" và "khớp nối" dữ liệu với đám mây hay không (FR11).
**Acceptance Criteria:**
**Given** app đang khởi chạy bình thường
**When** trạng thái kết nối mạng của Zero Client hoặc Browser thay đổi
**Then** Header hoặc góc dưới màn hình cập nhật icon (Xanh: Connected / Vàng: Syncing / Đỏ/Xám: Offline)
**And** thiết kế phải hòa hợp với bộ màu ZinC/Slate đã chọn, tuyệt đối không dùng thông báo (alert) nhảy ập vào mặt người dùng.
Hệ thống biến từ một ứng dụng tĩnh thành một nền tảng SaaS thương mại thông qua tích hợp thanh toán Stripe. Người dùng có thể xem bảng giá, chọn gói cước phù hợp, thanh toán an toàn và hệ thống tự động kiểm soát quota sử dụng dựa trên gói đăng ký, đảm bảo mô hình kinh doanh bền vững.
**FRs covered:** FR15, FR16, FR17

## 🏗️ Architecture & Technical Guardrails
> Critical instructions for the development agent based on the project's established architecture.

### Technical Requirements
- Language/Framework: React, Next.js (TypeScript) for Web; FastAPI (Python) for Backend.
- Database: Prisma/Supabase.
- Strict Type checking must be enforced. No `any` types.

### Code Organization
This story is currently marked as `done`. Implementation should target the following components/files:

- `surfsense_backend/app/utils/refresh_tokens.py`
- `surfsense_web/app/public/[token]/page.tsx`
- `surfsense_backend/app/routes/circleback_webhook_route.py`
- `surfsense_web/components/TokenHandler.tsx`
- `surfsense_backend/app/schemas/stripe.py`
- `surfsense_backend/app/services/page_limit_service.py`
- `surfsense_web/components/assistant-ui/connector-popup/components/periodic-sync-config.tsx`
- `surfsense_backend/app/services/dropbox/kb_sync_service.py`

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

