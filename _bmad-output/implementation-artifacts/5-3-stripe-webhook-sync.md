# Story 5.3: Hardening Stripe Webhook & Purchase History

Status: ready-for-dev

## Context / Correction Note
> **⚠️ Story gốc bị sai hướng.** Story gốc mô tả xử lý `customer.subscription.*` events để sync subscription status — đây là mô hình subscription SaaS, không phải mô hình thực tế của SurfSense. Webhook handler **đã tồn tại** và xử lý đúng event `checkout.session.completed` cho PAYG page packs. Không cần `stripe_customer_id` hay `subscription_status` vì SurfSense không dùng subscription.

## Story

As a Kỹ sư Hệ thống,
I want webhook handler xử lý đầy đủ các trường hợp edge-case của Stripe payment lifecycle,
so that mọi giao dịch đều được ghi nhận chính xác và pages luôn được cộng đúng.

## Actual Architecture (as-is)

**Đã implement và đúng:**
- `POST /api/v1/stripe/webhook` — verify Stripe-Signature, xử lý events:
  - `checkout.session.completed` → `_fulfill_completed_purchase()` → tăng `pages_limit`
  - `checkout.session.async_payment_succeeded` → fulfill
  - `checkout.session.async_payment_failed` → `_mark_purchase_failed()`
  - `checkout.session.expired` → mark failed
- Idempotency guard: `_get_or_create_purchase_from_checkout_session()` dùng DB để tránh double-grant
- `GET /api/v1/stripe/purchases` — lịch sử mua hàng của user
- `GET /api/v1/stripe/status` — check Stripe config status

**Không cần (và không nên thêm):**
- `customer.subscription.*` events — SurfSense không dùng subscription
- `stripe_customer_id` field trên User — không cần cho PAYG flow
- `subscription_status` / `plan_id` columns — không liên quan đến PAYG

**Còn thiếu:**
- Webhook chưa handle `payment_intent.payment_failed` (nếu payment thất bại sau khi session tạo)
- Chưa có notification/email khi purchase thành công (nice-to-have)
- Frontend `/purchases` page chưa có UI hiển thị lịch sử mua

## Acceptance Criteria

1. Khi Stripe gửi `checkout.session.completed`, `PagePurchase.status = COMPLETED` và `user.pages_limit` tăng đúng.
2. Nếu cùng 1 webhook event gửi 2 lần (Stripe retry), hệ thống chỉ grant pages 1 lần (idempotency).
3. Khi Stripe gửi `checkout.session.expired` hoặc `checkout.session.async_payment_failed`, `PagePurchase.status = FAILED`, `pages_limit` không thay đổi.
4. Endpoint `GET /api/v1/stripe/purchases` trả về danh sách purchase history đúng cho user hiện tại.

## Tasks / Subtasks

- [ ] Task 1: Verify idempotency của webhook handler
  - [ ] Subtask 1.1: Đọc `_get_or_create_purchase_from_checkout_session()` — đảm bảo có DB-level lock (SELECT FOR UPDATE hoặc unique constraint) để tránh race condition khi Stripe retry.
  - [ ] Subtask 1.2: Viết unit test simulate webhook event gửi 2 lần, assert `pages_limit` chỉ tăng 1 lần.
- [ ] Task 2: Thêm Purchase History UI (Frontend)
  - [ ] Subtask 2.1: Tạo page hoặc section trong Dashboard hiển thị danh sách `PagePurchase` từ `GET /api/v1/stripe/purchases`.
  - [ ] Subtask 2.2: Hiển thị: ngày mua, số pages, trạng thái (Completed/Failed/Pending), số tiền.
- [ ] Task 3: Xử lý `payment_intent.payment_failed` (defensive)
  - [ ] Subtask 3.1: Thêm case xử lý event `payment_intent.payment_failed` trong webhook handler — tìm `PagePurchase` qua `stripe_payment_intent_id` và mark failed.

## Dev Notes

### Existing Webhook Handler Structure
```python
@router.post("/webhook")
async def stripe_webhook(request, db_session):
    # 1. Verify Stripe-Signature
    # 2. Parse event
    # 3. Route by event type:
    event_handlers = {
        "checkout.session.completed": _fulfill_completed_purchase,
        "checkout.session.async_payment_succeeded": _fulfill_completed_purchase,
        "checkout.session.expired": _mark_purchase_failed,
        "checkout.session.async_payment_failed": _mark_purchase_failed,
    }
```

### Idempotency Pattern (đã có)
`_get_or_create_purchase_from_checkout_session()` query theo `stripe_checkout_session_id` — nếu đã COMPLETED thì skip, tránh double-grant.

### References
- `surfsense_backend/app/routes/stripe_routes.py` (lines ~86–345)
- `surfsense_backend/app/db.py` (class `PagePurchase`, `PagePurchaseStatus`)

## Dev Agent Record

### Agent Model Used
_TBD_

### File List
- `surfsense_backend/app/routes/stripe_routes.py`
- Frontend purchase history component (new)
