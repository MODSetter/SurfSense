# Story 5.3: Webhook & Cập nhật Trạng thái Gói cước (Stripe Webhook Sync)

Status: done

## Story

As a Kỹ sư Hệ thống,
I want backend tự động hứng Webhook từ Stripe mỗi khi có thanh toán thành công, gia hạn, hoặc hủy gói,
so that database được cập nhật trạng thái Subscription của user (Active/Canceled) mà không cần can thiệp thủ công.

## Acceptance Criteria

1. Backend bắt được Event Type qua HTTP POST và verify Webhook-Signature.
2. Xử lý các event subscription: `customer.subscription.created`, `customer.subscription.updated`, `customer.subscription.deleted`.
3. Update trạng thái (`subscription_status`, `plan_id`, `monthly_token_limit`, `token_reset_date`) vào User record tương ứng trên Database.
4. Reset `tokens_used_this_month = 0` khi subscription renews (billing cycle mới).

## As-Is (Code hiện tại)

| Component | Hiện trạng | File |
|-----------|-----------|------|
| Webhook Endpoint | **Đã tồn tại** — `POST /api/v1/stripe/webhook` với signature verification | `stripe_routes.py` line ~280 |
| Event Handlers | Chỉ xử lý PAYG events: `checkout.session.completed/expired/failed` → update `PagePurchase` | `stripe_routes.py` |
| Idempotency | **Đã có** cho page purchases — `_get_or_create_purchase_from_checkout_session()` | `stripe_routes.py` |
| Signature Verify | **Đã có** — dùng `stripe.Webhook.construct_event()` | `stripe_routes.py` line ~303 |
| User ↔ Stripe | **Không có** `stripe_customer_id` trên User (sẽ thêm ở Story 5.2) | `db.py` |
| Subscription Fields | **Không có** `subscription_status`, `plan_id` trên User | `db.py` |

**Gap:** Webhook infrastructure đã vững (signature verify, error handling). Cần thêm **subscription event handlers** bên cạnh PAYG handlers hiện tại.

## Tasks / Subtasks

- [x] Task 1: Thêm Subscription Fields vào User Model (Backend DB)
  - [x] Subtask 1.1: Alembic migration thêm columns (nếu chưa có từ Story 3.5):
    - `subscription_status` — Enum: `free`, `active`, `canceled`, `past_due` (default: `free`) ✅ migration 124
    - `plan_id` — String nullable (e.g. `pro_monthly`, `pro_yearly`) ✅ migration 124
    - `stripe_subscription_id` — String nullable, indexed ✅ migration 124
    - `subscription_current_period_end` — DateTime nullable ✅ migration 125 (mới thêm)

- [x] Task 2: Thêm Subscription Event Handlers vào Webhook (Backend)
  - [x] Subtask 2.1: Mở rộng webhook handler — thêm routing cho:
    - `customer.subscription.created` → activate subscription
    - `customer.subscription.updated` → update status/plan (handle upgrade/downgrade)
    - `customer.subscription.deleted` → set status=`canceled`, downgrade limits
    - `invoice.payment_succeeded` → reset `tokens_used_this_month = 0` (billing cycle mới)
    - `invoice.payment_failed` → set status=`past_due`
  - [x] Subtask 2.2: Tạo helper function `_handle_subscription_event(db_session, subscription)`:
    - Extract `customer` ID từ event → query User by `stripe_customer_id`
    - Update `subscription_status`, `plan_id`, `monthly_token_limit` theo plan
    - Update `subscription_current_period_end`
  - [x] Subtask 2.3: Plan → Limits mapping (config) — thêm `PLAN_LIMITS` vào `config/__init__.py`

- [x] Task 3: Xử lý `checkout.session.completed` cho Subscription mode
  - [x] Subtask 3.1: Trong webhook handler, check `session.mode == 'subscription'` → `_activate_subscription_from_checkout()`.
  - [x] Subtask 3.2: Giữ logic PAYG cũ cho `session.mode == 'payment'`.

- [x] Task 4: Idempotency cho Subscription Events
  - [x] Subtask 4.1: `_handle_subscription_event` so sánh `stripe_subscription_id + subscription_status + period_end` — skip nếu không đổi.
  - [x] Subtask 4.2: Log tất cả webhook events qua `logger.info("Received Stripe webhook event: %s", event.type)`.

## Dev Notes

### Security — Raw Body Parsing
Webhook endpoint **PHẢI** parse raw body bằng `await request.body()` TRƯỚC khi Pydantic parse. Nếu FastAPI parse thành Pydantic object trước → Stripe signature verify sẽ fail. Code hiện tại đã xử lý đúng.

### Race Condition
`checkout.session.completed` và `customer.subscription.created` có thể fire gần như đồng thời. Dùng `stripe_subscription_id` unique constraint hoặc `updatedAt` timestamp check để tránh data đè lên nhau.

### References
- `surfsense_backend/app/routes/stripe_routes.py` — webhook handler hiện tại
- `surfsense_backend/app/db.py` — User model
- Stripe Subscription Events: https://stripe.com/docs/billing/subscriptions/webhooks

## Dev Agent Record

### Implementation Notes
- Migration 124 đã có `subscription_status`, `plan_id`, `stripe_customer_id`, `stripe_subscription_id` từ Story 3.5 — không cần migration lại.
- Migration 125 thêm `subscription_current_period_end` (TIMESTAMP with timezone, nullable).
- `PLAN_LIMITS` dict thêm vào `config/__init__.py` — free: 50k tokens, pro: 1M tokens.
- `_get_user_by_stripe_customer_id()`: SELECT FOR UPDATE để safe với concurrent webhooks.
- `_handle_subscription_event()`: map Stripe status → `SubscriptionStatus` enum, idempotency check bằng so sánh subscription_id + status + period_end.
- `_handle_invoice_payment_succeeded()`: chỉ reset tokens khi `billing_reason` là `subscription_cycle` hoặc `subscription_update`.
- `_handle_invoice_payment_failed()`: set `PAST_DUE` nếu hiện đang `ACTIVE`.
- `_activate_subscription_from_checkout()`: kích hoạt ngay khi checkout hoàn thành (trước khi `customer.subscription.created` đến); idempotent.
- Webhook routing: thêm `logger.info` cho mỗi event type, route `checkout.session.*expired/failed` bỏ qua nếu là subscription mode.

### Completion Notes
✅ AC 1: Webhook đã có signature verification từ trước — giữ nguyên.
✅ AC 2: Xử lý `customer.subscription.created/updated/deleted` qua `_handle_subscription_event()`.
✅ AC 3: Update `subscription_status`, `plan_id`, `monthly_token_limit`, `subscription_current_period_end`.
✅ AC 4: Reset `tokens_used_this_month = 0` qua `_handle_invoice_payment_succeeded()` khi `billing_reason=subscription_cycle`.

### File List
- `surfsense_backend/app/db.py` — added `subscription_current_period_end` column to both User model variants
- `surfsense_backend/alembic/versions/125_add_subscription_current_period_end.py` — new migration
- `surfsense_backend/app/config/__init__.py` — added `PLAN_LIMITS` dict
- `surfsense_backend/app/routes/stripe_routes.py` — added `_get_user_by_stripe_customer_id`, `_period_end_from_subscription`, `_handle_subscription_event`, `_handle_invoice_payment_succeeded`, `_handle_invoice_payment_failed`, `_activate_subscription_from_checkout`; updated webhook router

### Review Findings

- [x] [Review][Patch] pages_limit never upgraded to Pro value on subscription activation — both `_activate_subscription_from_checkout` and `_handle_subscription_event` only set `monthly_token_limit`, not `pages_limit` [stripe_routes.py]
- [x] [Review][Patch] pages_limit downgrade ignores pages_used — sets `pages_limit=500` blindly, should use `max(pages_used, free_limit)` to avoid locking out existing content [stripe_routes.py]
- [x] [Review][Patch] `_activate_subscription_from_checkout` does not set `subscription_current_period_end` — stays NULL until `customer.subscription.created` fires [stripe_routes.py]
- [x] [Review][Patch] `_activate_subscription_from_checkout` does not set `token_reset_date` — stays NULL until first renewal invoice [stripe_routes.py]
- [x] [Review][Patch] `date.today()` used instead of `datetime.now(UTC).date()` in `_handle_invoice_payment_succeeded` — timezone mismatch with quota service [stripe_routes.py]
- [x] [Review][Patch] Unconfigured price ID env vars cause silent fallback to `plan_id="free"` for paying subscribers — should log warning when no price match [stripe_routes.py]
- [x] [Review][Patch] Idempotency check omits `plan_id` — mid-cycle plan change (monthly→yearly) with same status+period_end gets silently skipped [stripe_routes.py]
- [x] [Review][Patch] `billing_reason="subscription_create"` excluded from token reset — new subscribers inherit dirty free-tier token counter [stripe_routes.py]
- [x] [Review][Patch] `billing_reason="subscription_update"` included in token reset — plan changes mid-cycle incorrectly reset tokens to 0 [stripe_routes.py]
- [x] [Review][Patch] Out-of-order webhook delivery can overwrite newer `period_end` with older value — no "don't go backwards" guard [stripe_routes.py]
- [x] [Review][Patch] `SubscriptionStatus.FREE` in downgrade check is dead code — remove from set [stripe_routes.py]
- [x] [Review][Patch] Repeated `invoice.payment_failed` while PAST_DUE silently ignored without logging [stripe_routes.py]
- [x] [Review][Defer] Race between `checkout.session.completed` and `customer.subscription.deleted` can reactivate canceled subscription — deferred, requires Stripe API verification call
- [x] [Review][Defer] `invoice.payment_succeeded` does not update `subscription_current_period_end` — deferred, handled by `customer.subscription.updated` in same event sequence

### Change Log
- 2026-04-15: Implement Stripe webhook subscription event handlers — subscription lifecycle, invoice payment reset, checkout activation.
- 2026-04-15: Code review patches applied — 12 fixes: pages_limit upgrade/downgrade, period_end guards, token reset billing reasons, idempotency plan_id check, UTC date fix, unrecognized price ID warning.

## Review Findings (2026-04-15)

- [x] [Review][Patch] Unrecognized Stripe price ID silently downgrades active subscription to "free" [stripe_routes.py] — **Fixed**: Added early return when plan_id=="free" but subscription status is "active" and price ID was unrecognized
