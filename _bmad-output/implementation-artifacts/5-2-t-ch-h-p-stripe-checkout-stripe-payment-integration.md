# Story 5.2: Tích hợp Stripe Checkout (Stripe Payment Integration)

Status: ready-for-dev

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a Người dùng,
I want bấm "Nâng cấp" và được chuyển tới trang thanh toán an toàn,
so that tôi có thể điền thông tin thẻ tín dụng mà không sợ bị lộ dữ liệu trên máy chủ của SurfSense.

## Acceptance Criteria

1. Khi User bấm thanh toán, BE gọi API Stripe lấy `sessionId` của Stripe Checkout (Chế độ Subscription / Recurring Mode, không phải Chế độ Mua đứt OTP).
2. Hệ thống redirect User an toàn qua cổng Stripe được Hosted trực tiếp bởi Stripe Server.

## Tasks / Subtasks

- [ ] Task 1: Nâng cấp `stripe_routes.py`
  - [ ] Subtask 1.1: Bổ sung Endpoint POST `/api/v1/stripe/create-subscription-checkout`. 
  - [ ] Subtask 1.2: Phân tích `plan_id` từ Request body hoặc User, cấu hình `mode='subscription'` trong dict truyền cho thư viện Stripe (thay vì chế độ `payment` cũ).
- [ ] Task 2: Liên kết Action Nút ở UI
  - [ ] Subtask 2.1: Ở `Pricing` Component, xử lý `onClick` bằng cách submit POST form request tới API mới, bắt `checkout_url` và route trình duyệt tới URL đó bằng thẻ A hoặc JS `window.location.href`.

## Dev Notes

### Relevant Architecture Patterns & Constraints
- Codebase hiện có `surfsense_backend/app/routes/stripe_routes.py` nhưng ĐANG GẮN code Payment Intent cho Token "Page Purchase" One-time 1 lần. DEV cần lưu ý CẤU HÌNH LẠI để route mới sinh này phục vụ riêng cho gói Subscription hàng tháng (Gửi theo CustomerID nếu User đã bind).
- Security: Giá `stripe_price_id` bắt buộc phải map và define ở Back-End environment variable (Vd `STRIPE_PRO_PLAN_ID`), tuyệt đối không chấp nhận param `price` từ Header gửi lên (Phòng tránh giả mạo giá tiền).

### Project Structure Notes
- Module thay đổi:
  - `surfsense_backend/app/routes/stripe_routes.py`
  - `surfsense_web/src/pages/pricing/page.tsx`

### References
- [Epic 5.2 - Subscriptions]

## Dev Agent Record

### Agent Model Used
Antigravity Claude 3.5 Sonnet Engine

### File List
- `surfsense_backend/app/routes/stripe_routes.py`
