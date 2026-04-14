# Deferred Work

## Deferred from: code review of story 3-5-model-selection-via-quota (2026-04-14)

- **stripe_subscription_id has no unique constraint** [surfsense_backend/app/db.py] — Column added without UNIQUE constraint. Should be enforced once Stripe integration (Epic 5) is implemented to prevent duplicate subscription mappings.
- **load_llm_config_from_yaml reads API keys directly from YAML file, not env vars** [surfsense_backend/app/config.py] — Pre-existing: YAML config stores API keys inline. Spec Task 1.2 says "đọc API keys từ env vars" but this is the existing pattern used throughout the project. To be refactored when security hardening is prioritized.

## Deferred from: code review of story 5-1 (2026-04-14)

- `ref` cast `as any` on Switch component in `pricing.tsx:99` — pre-existing issue, not introduced by this change. Should use proper `React.ComponentRef<typeof Switch>` type.

## Deferred from: code review of story 5-2 (2026-04-14)

- Webhook handler needs to distinguish `mode='subscription'` from `mode='payment'` in `checkout.session.completed` and update User's `subscription_status`, `plan_id`, `stripe_subscription_id` — scope of Story 5.3.
- Subscription lifecycle events (`invoice.paid`, `customer.subscription.updated/deleted`, `invoice.payment_failed`) not handled — scope of Story 5.3.
- `_get_or_create_stripe_customer` can create orphaned Stripe customers if `db_session.commit()` fails after `customers.create`. Consider idempotency key in future.

## Deferred from: Story 5.6 post-story bug fixes (2026-04-15)

- **`api_key` exposed in LLM preferences response** [`surfsense_backend/app/routes/search_space_routes.py`] — `GET/PUT /search-spaces/{id}/llm-preferences` returns full config objects including `api_key` (nested `agent_llm`, `document_summary_llm`, etc. fields). Should return sanitized Public versions (no api_key). Low risk since endpoint requires authentication, but still a credentials leak.

## Deferred from: code review of story-5.3 (2026-04-15)

- Race condition: `checkout.session.completed` and `customer.subscription.deleted` can fire near-simultaneously; if deleted arrives between checkout handlers, subscription can be reactivated. Fix requires Stripe API call to verify subscription status before activation.
- `invoice.payment_succeeded` does not update `subscription_current_period_end` — currently relies on `customer.subscription.updated` firing in the same event sequence. If that event is lost, period_end is stale.

## Deferred from: code review of Epic 5 (2026-04-15) — RESOLVED 2026-04-15

- ~~**Migration 124 drops enum type unconditionally**~~ — **Fixed**: Added `CASCADE` to `DROP TYPE IF EXISTS subscriptionstatus CASCADE` in `124_add_subscription_token_quota_columns.py`.
- ~~**`checkout_url` rejects non-HTTPS URLs**~~ — **Closed as invalid**: Original `startsWith("https://")` check is intentionally correct — Stripe always returns HTTPS URLs even in test mode. Relaxing to `http` would weaken security. No change made.
- ~~**`verify-checkout-session` endpoint lacks rate limiting**~~ — **Fixed**: Added in-memory per-user rate limit (20 calls/60s) via `_check_verify_session_rate_limit()` in `stripe_routes.py`.
- ~~**Rejected user can re-submit approval request immediately**~~ — **Fixed**: Added 24h cooldown check using `created_at >= now() - 24h` on REJECTED requests before creating a new SubscriptionRequest.
- ~~**`token_reset_date` not set in `_handle_subscription_event`**~~ — **Fixed**: When `new_status == ACTIVE` and `token_reset_date is None`, now sets `user.token_reset_date = datetime.now(UTC).date()`.
