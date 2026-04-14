# Story 5.2: Xác minh & Hardening Stripe PAYG Flow

Status: ready-for-dev

## Context / Correction Note
> **⚠️ Story gốc bị sai hướng.** Story gốc mô tả implement `mode: "subscription"` Stripe Checkout. Thực tế, SurfSense dùng mô hình **PAYG (Pay-As-You-Go page packs)** với `mode: "payment"` (one-time purchase). Endpoint `POST /api/v1/stripe/create-checkout-session` **đã tồn tại và hoạt động**. Story này chỉ cần hardening, không cần implement mới.

## Story

As a Kỹ sư Hệ thống,
I want đảm bảo Stripe PAYG checkout flow hoạt động ổn định end-to-end,
so that user có thể mua page packs và pages được cộng vào tài khoản đúng cách.

## Actual Architecture (as-is)

**Đã implement:**
- `POST /api/v1/stripe/create-checkout-session` — tạo Stripe Checkout Session (`mode: "payment"`)
  - Nhận `search_space_id`, `quantity`
  - Tạo `PagePurchase` record với status `PENDING`
  - Trả về `checkout_url`
- `_fulfill_completed_purchase()` — khi webhook confirm, tăng `user.pages_limit`
- `_get_checkout_urls()` — tạo success/cancel URL cho Stripe redirect

**Config cần thiết (env vars):**
- `STRIPE_SECRET_KEY`
- `STRIPE_PRICE_ID` — price ID cho 1 page pack
- `STRIPE_WEBHOOK_SECRET`
- `STRIPE_PAGES_PER_UNIT` — pages per pack (default: 1000)

**Còn thiếu / chưa xác minh:**
- Frontend chưa gọi endpoint này (chặn bởi Story 5.1)
- Chưa có test end-to-end với Stripe test mode
- `STRIPE_PRICE_ID` cần được tạo trên Stripe Dashboard và config đúng

## Acceptance Criteria

1. Với Stripe test keys, tạo checkout session thành công, redirect đến Stripe test checkout page.
2. Sau khi hoàn tất thanh toán (dùng test card `4242 4242 4242 4242`), webhook trigger và `pages_limit` của user tăng lên đúng số lượng.
3. Nếu `STRIPE_SECRET_KEY` hoặc `STRIPE_PRICE_ID` không được cấu hình, API trả về lỗi có thể đọc được (không crash 500).

## Tasks / Subtasks

- [ ] Task 1: Verify Stripe config
  - [ ] Subtask 1.1: Kiểm tra `surfsense_backend/app/config.py` — đảm bảo `STRIPE_SECRET_KEY`, `STRIPE_PRICE_ID`, `STRIPE_WEBHOOK_SECRET`, `STRIPE_PAGES_PER_UNIT` được đọc từ env vars.
  - [ ] Subtask 1.2: Đảm bảo `_ensure_page_buying_enabled()` trả về lỗi 503 rõ ràng thay vì crash khi Stripe chưa config.
- [ ] Task 2: Test end-to-end với Stripe CLI
  - [ ] Subtask 2.1: Dùng `stripe listen --forward-to localhost:8000/api/v1/stripe/webhook` để test webhook locally.
  - [ ] Subtask 2.2: Verify `PagePurchase.status` chuyển từ `PENDING` → `COMPLETED` sau webhook.
  - [ ] Subtask 2.3: Verify `user.pages_limit` tăng đúng `quantity × STRIPE_PAGES_PER_UNIT`.
- [ ] Task 3: Thêm Stripe setup vào `.env.example`
  - [ ] Subtask 3.1: Bổ sung `STRIPE_SECRET_KEY`, `STRIPE_PRICE_ID`, `STRIPE_WEBHOOK_SECRET`, `STRIPE_PAGES_PER_UNIT` vào `surfsense_backend/.env.example` với comment hướng dẫn.

## Dev Notes

### Current Flow (hoạt động)
```
FE → POST /api/v1/stripe/create-checkout-session
   → Stripe Checkout (hosted page)
   → Stripe → POST /api/v1/stripe/webhook (checkout.session.completed)
   → _fulfill_completed_purchase() → user.pages_limit += pages_granted
   → Stripe redirects FE → success_url
```

### PagePurchase Status Enum
- `PENDING` — checkout tạo nhưng chưa thanh toán
- `COMPLETED` — thanh toán thành công, pages đã được grant
- `FAILED` — thanh toán thất bại

### References
- `surfsense_backend/app/routes/stripe_routes.py`
- `surfsense_backend/app/db.py` (class `PagePurchase`, lines ~1616+)
- Stripe Test Cards: https://stripe.com/docs/testing

## Dev Agent Record

### Agent Model Used
_TBD_

### File List
- `surfsense_backend/app/routes/stripe_routes.py`
- `surfsense_backend/app/config.py`
- `surfsense_backend/.env.example`
