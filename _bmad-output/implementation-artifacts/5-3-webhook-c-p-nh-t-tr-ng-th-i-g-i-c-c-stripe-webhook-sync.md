# Story 5.3: Webhook & Cập nhật Trạng thái Gói cước (Stripe Webhook Sync)

Status: ready-for-dev

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a Kỹ sư Hệ thống,
I want backend tự động hứng Webhook từ Stripe mỗi khi có thanh toán thành công, gia hạn, hoặc hủy gói,
so that database được cập nhật trạng thái Subscription của user (Active/Canceled) mà không cần can thiệp thủ công.

## Acceptance Criteria

1. Backend bắt được Event Type qua HTTP POST.
2. Kiểm tra chính xác Webhook-Signature tránh Event giả.
3. Update trạng thái (Status, Expiry date, Plan_id) vào User record tương ứng trên Database Postgres.

## Tasks / Subtasks

- [ ] Task 1: Dựng Webhook Route
  - [ ] Subtask 1.1: Tạo Route `/api/v1/stripe/webhook` (đã có route cũ dành cho Page Purchase, xem ở `stripe_routes.py` line 281). 
  - [ ] Subtask 1.2: Code logic giải mãi Signature.
- [ ] Task 2: Listen Subscription Events
  - [ ] Subtask 2.1: Phân tích Webhook Event Type. Lắng nghe ít nhất 2 Event cơ bản: `customer.subscription.updated` và `customer.subscription.deleted`. Xử lý và fetch customer ID để map với User nội bộ (có thể dùng `stripe_customer_id` lưu trên bảng `users`).
- [ ] Task 3: Database User Updates
  - [ ] Subtask 3.1: Viết hàm DB handler gọi tới DB để ghi đè `subscription_status` = 'active', set `plan_id`, và cập nhật `token_balance` hàng tháng khi có trigger chu kỳ mới. Cập nhật `users.py` controller.

## Dev Notes

### Relevant Architecture Patterns & Constraints
- **Security Check:** Webhook API endpoint `MUST` parse raw body using `await request.body()`. Nếu FastAPI parse ra Pydantic Object TRƯỚC chữ ký signature thì thư viện Stripe auth sẽ báo lỗi văng Exception.
- **Race Condition in DB:** Do event `checkout.session.completed` và `customer.subscription.created` có thể call webhook cục bộ gần như đồng thời, phải code check Upsert (Ví dụ: set timestamp check updatedAt để tránh data đè lên nhau).

### Project Structure Notes
- Module thay đổi:
  - `surfsense_backend/app/routes/stripe_routes.py`
  - `surfsense_backend/app/db.py`

### References
- [Epic 5.3 - Webhook Sync]

## Dev Agent Record

### Agent Model Used
Antigravity Claude 3.5 Sonnet Engine

### File List
- `surfsense_backend/app/routes/stripe_routes.py`
