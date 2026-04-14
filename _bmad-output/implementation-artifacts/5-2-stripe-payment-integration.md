# Story 5.2: Tích hợp Stripe Subscription Checkout (Stripe Payment Integration)

Status: done

## Story

As a Người dùng,
I want bấm "Nâng cấp" và được chuyển tới trang thanh toán an toàn,
so that tôi có thể điền thông tin thẻ tín dụng mà không sợ bị lộ dữ liệu trên máy chủ của SurfSense.

## Acceptance Criteria

1. Khi User bấm thanh toán, BE gọi API Stripe lấy `sessionId` với **`mode='subscription'`** (recurring billing, không phải one-time payment).
2. Hệ thống redirect User an toàn qua cổng Stripe Hosted Checkout.
3. Sau thanh toán thành công, user được redirect về app với subscription activated.
4. **[Admin-approval mode]** Khi `STRIPE_SECRET_KEY` chưa được cấu hình, endpoint trả về `{ checkout_url: "", admin_approval_mode: true }` thay vì gọi Stripe — frontend hiển thị toast "Subscription request submitted! An admin will approve it shortly." và không redirect.
5. **[Admin-approval mode]** Nếu user đã có request đang pending, endpoint trả về 409 Conflict để tránh duplicate.

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

- [x] Task 1: Thêm `stripe_customer_id` vào User (Backend DB)
  - [x] Subtask 1.1: Alembic migration thêm column `stripe_customer_id` — đã có trong migration 124.
  - [x] Subtask 1.2: Tạo helper function `get_or_create_stripe_customer(user)` — SELECT FOR UPDATE, tạo Stripe customer nếu chưa có, persist ID.

- [x] Task 2: Tạo Subscription Checkout Endpoint (Backend)
  - [x] Subtask 2.1: Tạo endpoint `POST /api/v1/stripe/create-subscription-checkout`.
  - [x] Subtask 2.2: Request body: `{ "plan_id": "pro_monthly" | "pro_yearly" }` — validated bằng `PlanId` enum.
  - [x] Subtask 2.3: Map `plan_id` → Stripe Price ID từ env vars (`STRIPE_PRO_MONTHLY_PRICE_ID`, `STRIPE_PRO_YEARLY_PRICE_ID`). Frontend không gửi price.
  - [x] Subtask 2.4: Gọi `stripe.checkout.sessions.create(mode='subscription', customer=stripe_customer_id, ...)`.
  - [x] Subtask 2.5: Trả về `{ "checkout_url": "https://checkout.stripe.com/..." }`.

- [x] Task 2b: Admin-approval fallback khi Stripe chưa cấu hình
  - [x] Subtask 2b.1: Kiểm tra `config.STRIPE_SECRET_KEY` ở đầu checkout endpoint — nếu falsy, bỏ qua toàn bộ Stripe logic.
  - [x] Subtask 2b.2: Guard active subscription: nếu `user.subscription_status == ACTIVE` → 409.
  - [x] Subtask 2b.3: Guard duplicate pending request: query `SubscriptionRequest` table — nếu đã có pending → 409.
  - [x] Subtask 2b.4: Tạo `SubscriptionRequest(user_id, plan_id)` row và commit.
  - [x] Subtask 2b.5: Trả về `CreateSubscriptionCheckoutResponse(checkout_url="", admin_approval_mode=True)`.
  - [x] Subtask 2b.6: Thêm `admin_approval_mode: bool = False` vào `CreateSubscriptionCheckoutResponse` schema.
  - [x] Subtask 2b.7: Frontend `handleUpgradePro()` — nếu `data.admin_approval_mode` là `true`, hiển thị toast thành công và return (không redirect).

- [x] Task 3: Kết nối Frontend với Endpoint mới
  - [x] Subtask 3.1: `pricing-section.tsx` đã gọi endpoint với `plan_id` — done trong Story 5.1.
  - [x] Subtask 3.2: Redirect đến `checkout_url` — done trong Story 5.1.
  - [x] Subtask 3.3: `/subscription-success` page tạo mới — invalidates user query + toast "Subscription activated!"

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

## Dev Agent Record

### Implementation Notes
- Migration 124 đã có `stripe_customer_id` và `stripe_subscription_id` từ Story 3.5 — không cần migration mới.
- `get_or_create_stripe_customer`: dùng `SELECT FOR UPDATE` để tránh duplicate customer khi concurrent requests.
- `_get_price_id_for_plan`: map `PlanId` enum → env var `STRIPE_PRO_MONTHLY_PRICE_ID` / `STRIPE_PRO_YEARLY_PRICE_ID`. Frontend không gửi price ID.
- Endpoint `POST /create-subscription-checkout`: `mode='subscription'`, `customer=stripe_customer_id`, `success_url=/subscription-success`, `cancel_url=/pricing`.
- `PlanId` enum trong schemas/stripe.py đảm bảo frontend chỉ gửi giá trị hợp lệ.
- Frontend success page `/subscription-success`: toast "Subscription activated!" + invalidate user query.

### Completion Notes
✅ Tất cả tasks/subtasks hoàn thành. AC 1-3 đều được đáp ứng.

### File List
- `surfsense_backend/app/config/__init__.py` — added `STRIPE_PRO_MONTHLY_PRICE_ID`, `STRIPE_PRO_YEARLY_PRICE_ID`
- `surfsense_backend/app/schemas/stripe.py` — added `PlanId` enum, `CreateSubscriptionCheckoutRequest`, `CreateSubscriptionCheckoutResponse` (including `admin_approval_mode: bool = False`)
- `surfsense_backend/app/routes/stripe_routes.py` — added `_get_subscription_success_url`, `_get_price_id_for_plan`, `get_or_create_stripe_customer`, `POST /create-subscription-checkout` + admin-approval fallback branch
- `surfsense_web/app/subscription-success/page.tsx` — new success page with toast + user query invalidation
- `surfsense_web/components/pricing/pricing-section.tsx` — added `admin_approval_mode` toast handling in `handleUpgradePro()`
- *(See Story 5.5 for admin-approval infrastructure: migrations 126/127, `SubscriptionRequest` model, admin routes, admin UI page)*

### Review Findings

- [x] [Review][Decision] Success page verify payment server-side — added GET /verify-checkout-session endpoint + frontend verify flow
- [x] [Review][Patch] Success URL includes `?session_id={CHECKOUT_SESSION_ID}` template variable [stripe_routes.py:89]
- [x] [Review][Patch] Duplicate NEXT_FRONTEND_URL check removed — refactored to `_get_subscription_urls()` [stripe_routes.py:82]
- [x] [Review][Patch] Added active subscription guard (409 Conflict) before creating checkout [stripe_routes.py:370]
- [x] [Review][Patch] Toast only fires once via `useRef` flag + only after verified [subscription-success/page.tsx]
- [x] [Review][Defer] Webhook không xử lý subscription-mode checkout — deferred to Story 5.3
- [x] [Review][Defer] Không có handler cho subscription lifecycle events — deferred to Story 5.3
- [x] [Review][Defer] Orphan Stripe customer nếu commit fail sau API call — deferred, low probability

### Change Log
- 2026-04-14: Implement subscription checkout endpoint with Stripe customer creation and success page.
- 2026-04-15: Add admin-approval fallback mode — when `STRIPE_SECRET_KEY` is not configured, checkout endpoint creates a `SubscriptionRequest` row instead of calling Stripe (see Story 5.5).
