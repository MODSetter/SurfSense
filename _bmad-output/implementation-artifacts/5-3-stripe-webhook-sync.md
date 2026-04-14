# Story 5.3: Webhook & Cập nhật Trạng thái Gói cước (Stripe Webhook Sync)

Status: ready-for-dev

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

- [ ] Task 1: Thêm Subscription Fields vào User Model (Backend DB)
  - [ ] Subtask 1.1: Alembic migration thêm columns (nếu chưa có từ Story 3.5):
    - `subscription_status` — Enum: `free`, `active`, `canceled`, `past_due` (default: `free`)
    - `plan_id` — String nullable (e.g. `pro_monthly`, `pro_yearly`)
    - `stripe_subscription_id` — String nullable, indexed
    - `subscription_current_period_end` — DateTime nullable (để biết khi nào renewal)

- [ ] Task 2: Thêm Subscription Event Handlers vào Webhook (Backend)
  - [ ] Subtask 2.1: Mở rộng webhook handler — thêm routing cho:
    - `customer.subscription.created` → activate subscription
    - `customer.subscription.updated` → update status/plan (handle upgrade/downgrade)
    - `customer.subscription.deleted` → set status=`canceled`, downgrade limits
    - `invoice.payment_succeeded` → reset `tokens_used_this_month = 0` (billing cycle mới)
    - `invoice.payment_failed` → set status=`past_due`
  - [ ] Subtask 2.2: Tạo helper function `_handle_subscription_event(event, db_session)`:
    - Extract `customer` ID từ event → query User by `stripe_customer_id`
    - Update `subscription_status`, `plan_id`, `monthly_token_limit` theo plan
    - Update `subscription_current_period_end`
  - [ ] Subtask 2.3: Plan → Limits mapping (config):
    ```python
    PLAN_LIMITS = {
        "free": {"monthly_token_limit": 50_000, "pages_limit": 500},
        "pro_monthly": {"monthly_token_limit": 1_000_000, "pages_limit": 5000},
        "pro_yearly": {"monthly_token_limit": 1_000_000, "pages_limit": 5000},
    }
    ```

- [ ] Task 3: Xử lý `checkout.session.completed` cho Subscription mode
  - [ ] Subtask 3.1: Trong handler `checkout.session.completed` hiện tại, thêm check: nếu `session.mode == 'subscription'` → activate subscription thay vì grant pages.
  - [ ] Subtask 3.2: Giữ logic PAYG cũ cho `session.mode == 'payment'`.

- [ ] Task 4: Idempotency cho Subscription Events
  - [ ] Subtask 4.1: Dùng `stripe_subscription_id` + event timestamp để tránh duplicate processing.
  - [ ] Subtask 4.2: Log tất cả webhook events để debug.

## Dev Notes

### Security — Raw Body Parsing
Webhook endpoint **PHẢI** parse raw body bằng `await request.body()` TRƯỚC khi Pydantic parse. Nếu FastAPI parse thành Pydantic object trước → Stripe signature verify sẽ fail. Code hiện tại đã xử lý đúng.

### Race Condition
`checkout.session.completed` và `customer.subscription.created` có thể fire gần như đồng thời. Dùng `stripe_subscription_id` unique constraint hoặc `updatedAt` timestamp check để tránh data đè lên nhau.

### References
- `surfsense_backend/app/routes/stripe_routes.py` — webhook handler hiện tại
- `surfsense_backend/app/db.py` — User model
- Stripe Subscription Events: https://stripe.com/docs/billing/subscriptions/webhooks
