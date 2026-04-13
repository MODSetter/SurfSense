# Story 5.1: Giao diện Bảng giá & Lựa chọn Gói Cước (Pricing Plan Selection UI)

Status: ready-for-dev

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a Khách hàng tiềm năng,
I want xem một bảng giá rõ ràng về các gói cước (ví dụ: Free, Pro, Team) với quyền lợi tương ứng,
so that tôi biết chính xác số lượng file/tin nhắn mình nhận được trước khi quyết định nâng cấp hoặc duy trì để quản lý ví (Wallet/Token) của mình.

## Acceptance Criteria

1. UI hiển thị các mức giá (monthly/yearly) rõ ràng cùng các bullets tính năng.
2. Thiết kế áp dụng chuẩn UX-DR1 (Dark mode, Base Zinc, Accent Indigo) hiện có của app.
3. Kèm theo hiệu ứng hover mượt mà cho các Pricing Cards (<150ms delay).
4. Phân bổ ít nhất 2 gói cước (Free, Pro) gắn liền với Limit.

## Tasks / Subtasks

- [ ] Task 1: Dựng Page Route Pricing (Frontend)
  - [ ] Subtask 1.1: Tạo Component `/src/pages/pricing/page.tsx` (app router tuỳ cấu hình Next.js hoặc Vite App).
  - [ ] Subtask 1.2: Sử dụng thư viện `framer-motion` (nếu có sẵn) hoặc Tailwind Utilities (`transition-all duration-150`) để thoả mãn Animation criteria.
- [ ] Task 2: Data cấu hình Static Pricing (Frontend)
  - [ ] Subtask 2.1: Cấu trúc Object Constant cho Gói "Free" (Limits: 10 docs, 50 LLM messages/day).
  - [ ] Subtask 2.2: Cấu trúc Object Constant cho Gói "Pro" (Limits: 100 docs, 1000 LLM messages/day).
- [ ] Task 3: Liên kết Nút "Upgrade" (Frontend)
  - [ ] Subtask 3.1: Nút nâng cấp sẽ chèn hàm mock gọi `/api/v1/stripe/checkout` (Endpoint này sẽ được làm chi tiết ở story 5.2).

## Dev Notes

### Relevant Architecture Patterns & Constraints
- **State Management & Data Retrieval:** Vì UI Pricing khá tĩnh, hãy triển khai bằng cấu trúc Const Typescript thay vì gọi DB ở màn đầu tiên nhằm tối ưu tốc độ load.
- Chú ý đến Graceful degradation: Nếu user Offline, màn pricing vẫn load được Static Data, nhưng disable nút "Purchase" để tránh lỗi Network Request.

### Project Structure Notes
- Module thay đổi:
  - `surfsense_web/src/pages/pricing/page.tsx` (hoặc tương đương tuỳ thư mục routes).
  - `surfsense_web/src/constants/billing.ts` (Lưu định mức cước).

### References
- [Epic 5 - Commercialization & Account Limits].

## Dev Agent Record

### Agent Model Used
Antigravity Claude 3.5 Sonnet Engine

### File List
- `surfsense_web/src/pages/pricing...`
