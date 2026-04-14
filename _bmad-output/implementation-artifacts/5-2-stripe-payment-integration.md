# Story 5.2: Tích hợp Stripe Subscription Checkout (Stripe Payment Integration)

Status: ready-for-dev

## Story

As a Người dùng,
I want bấm "Nâng cấp" và được chuyển tới trang thanh toán an toàn,
so that tôi có thể điền thông tin thẻ tín dụng mà không sợ bị lộ dữ liệu trên máy chủ của SurfSense.

## Acceptance Criteria

1. Khi User bấm thanh toán, BE gọi API Stripe lấy `sessionId` với **`mode='subscription'`** (recurring billing, không phải one-time payment).
2. Hệ thống redirect User an toàn qua cổng Stripe Hosted Checkout.
3. Sau thanh toán thành công, user được redirect về app với subscription activated.

## As-Is (Code hiện tại)

| Component | Hiện trạng | File |
|-----------|-----------|------|
| Checkout Endpoint | **Đã tồn tại** nhưng chỉ hỗ trợ `mode='payment'` (one-time page packs) | `surfsense_backend/app/routes/stripe_routes.py` line ~205 |
| Checkout Request Schema | `CreateCheckoutSessionRequest(search_space_id, quantity)` — cho page packs | `stripe_routes.py` |
| Stripe Client | **Đã tồn tại** — `get_stripe_client()`, config từ env vars | `stripe_routes.py` |
| Success/Cancel URLs | **Đã tồn tại** — `_get_checkout_urls()` | `stripe_routes.py` |
| Stripe Config | `STRIPE_SECRET_KEY`, `STRIPE_PRICE_ID`, `STRIPE_WEBHOOK_SECRET` đã có | `config.py` |
| User ↔ Stripe mapping | **Không có** `stripe_customer_id` trên User model | `db.py` |

**Gap:** Cần thêm endpoint subscription checkout **mới** (giữ endpoint page purchase cũ nếu muốn). Cần `stripe_customer_id` để Stripe quản lý recurring billing.

## Tasks / Subtasks

- [ ] Task 1: Thêm `stripe_customer_id` vào User (Backend DB)
  - [ ] Subtask 1.1: Alembic migration thêm column `stripe_customer_id` (String, nullable, unique, indexed) vào `User`.
  - [ ] Subtask 1.2: Tạo helper function `get_or_create_stripe_customer(user)` — nếu `stripe_customer_id` null → gọi `stripe.customers.create(email=user.email)` → lưu ID vào DB.

- [ ] Task 2: Tạo Subscription Checkout Endpoint (Backend)
  - [ ] Subtask 2.1: Tạo endpoint `POST /api/v1/stripe/create-subscription-checkout`.
  - [ ] Subtask 2.2: Request body: `{ "plan_id": "pro_monthly" | "pro_yearly" }`.
  - [ ] Subtask 2.3: Map `plan_id` → Stripe Price ID từ env vars (`STRIPE_PRO_MONTHLY_PRICE_ID`, `STRIPE_PRO_YEARLY_PRICE_ID`). Tuyệt đối **không nhận price từ frontend** — phòng tránh giả mạo giá.
  - [ ] Subtask 2.4: Gọi `stripe.checkout.sessions.create(mode='subscription', customer=stripe_customer_id, ...)`.
  - [ ] Subtask 2.5: Trả về `{ "checkout_url": "https://checkout.stripe.com/..." }`.

- [ ] Task 3: Kết nối Frontend với Endpoint mới
  - [ ] Subtask 3.1: Từ `pricing-section.tsx`, nút "Upgrade to Pro" gọi `POST /api/v1/stripe/create-subscription-checkout` với `plan_id`.
  - [ ] Subtask 3.2: Redirect đến `checkout_url`.
  - [ ] Subtask 3.3: Xử lý success return URL — hiển thị toast "Subscription activated!"

## Dev Notes

### Giữ song song PAYG và Subscription?
Endpoint page purchase cũ (`create-checkout-session` với `mode='payment'`) có thể giữ nguyên. Endpoint subscription mới chạy song song. Quyết định business logic.

### Security
- Giá `stripe_price_id` map ở **backend env vars** (`STRIPE_PRO_MONTHLY_PRICE_ID`, `STRIPE_PRO_YEARLY_PRICE_ID`).
- Frontend chỉ gửi `plan_id` (string enum), backend resolve ra Stripe Price ID.

### Stripe Customer
Khi tạo subscription checkout, **bắt buộc** phải có `customer` parameter. Stripe dùng customer ID để quản lý recurring billing, invoices, payment methods. Nên create Stripe customer ngay khi user đăng ký hoặc lần đầu checkout.

### Webhook (xem Story 5.3)
Sau checkout, Stripe sẽ gửi `checkout.session.completed` → webhook handler cần detect `mode='subscription'` và activate subscription trên DB.

### References
- `surfsense_backend/app/routes/stripe_routes.py` — endpoint PAYG hiện tại (tham khảo pattern)
- Stripe Subscription Checkout docs: https://stripe.com/docs/billing/subscriptions/build-subscriptions
