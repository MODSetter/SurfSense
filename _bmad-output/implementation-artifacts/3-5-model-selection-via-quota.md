# Story 3.5: Lựa chọn Mô hình LLM dựa trên Subscription (Model Selection via Quota)

Status: in-progress

## Story

As a Người dùng,
I want chọn cấu hình mô hình trí tuệ nhân tạo (VD: Claude 3.5 Sonnet, GPT-4) được cung cấp sẵn mà không cần điền API key cá nhân,
so that tôi có thể dùng trực tiếp và chi phí sử dụng được trừ thẳng vào số Token thuộc gói cước của tôi.

## Acceptance Criteria

1. Hệ thống cung cấp Dropdown chọn `LLM Model` trong giao diện Chat — danh sách model do hệ thống quản lý.
2. Tuyệt đối không hiển thị ô nhập "Your API Key" ở Frontend khi `DEPLOYMENT_MODE=hosted` (PRD: "Tuyệt đối không hỗ trợ chức năng User tự nhập LLM API Key riêng nhằm kiểm soát chất lượng và doanh thu").
3. Hệ thống Backend tính toán chi phí (Token × Đơn giá của Model) và trừ vào quota subscription.
4. Hệ thống kiểm tra Quota hàng tháng của người dùng; nếu vượt quá (Quota Exceeded), trả về lỗi 402/429 báo "Hãy nâng cấp gói".

## As-Is (Code hiện tại — cần thay đổi)

| Component | Hiện trạng | File |
|-----------|-----------|------|
| Frontend Model Selector | BYOK: user chọn từ `NewLLMConfig` do mình tự tạo (tự nhập API key) | `surfsense_web/components/new-chat/model-selector.tsx` |
| Frontend LLM Config UI | Cho user nhập API key, chọn provider, model name | `surfsense_web/app/dashboard/[search_space_id]/llm-configs/` |
| Backend LLM Config | `NewLLMConfig` table lưu `api_key`, `llm_model_name`, `provider` per-user | `surfsense_backend/app/db.py` |
| Backend Chat Streaming | Dùng API key từ user's `NewLLMConfig` để gọi LLM | Chat routes / RAG engine |
| Quota cho LLM | **Không tồn tại** — chỉ có `pages_limit`/`pages_used` cho document ETL | `surfsense_backend/app/db.py` |
| PageLimitService | Đã implement đầy đủ cho document quota — có thể dùng làm pattern | `surfsense_backend/app/services/page_limit_service.py` |

## Tasks / Subtasks

- [ ] Task 1: Tạo System Model Catalog (Backend)
  - [ ] Subtask 1.1: Tạo config/table `SystemLLMModel` với fields: `model_id`, `provider` (openai/anthropic), `model_name`, `display_name`, `cost_per_1k_input_tokens`, `cost_per_1k_output_tokens`, `tier_required` (free/pro). Có thể dùng Enum hoặc DB table.
  - [ ] Subtask 1.2: Backend đọc API keys từ env vars (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`) — không lưu vào DB per-user.
  - [ ] Subtask 1.3: Tạo endpoint `GET /api/v1/models` trả danh sách models khả dụng (filtered theo subscription tier của user).

- [ ] Task 2: Cập nhật Chat Streaming để dùng System Keys (Backend)
  - [ ] Subtask 2.1: Sửa RAG engine / chat streaming endpoint để nhận `model_id` thay vì `llm_config_id`.
  - [ ] Subtask 2.2: Resolve API key từ env vars dựa trên `provider` của model, không từ user's `NewLLMConfig`.
  - [ ] Subtask 2.3: Sau khi stream xong, đếm tokens (dùng `tiktoken` cho OpenAI hoặc response metadata) → gọi atomic UPDATE `token_balance = token_balance - cost` (tránh race condition khi mở 2 tab chat đồng thời).

- [ ] Task 3: Thêm Token Quota vào User Model (Backend DB)
  - [ ] Subtask 3.1: Alembic migration thêm columns vào `User`: `monthly_token_limit` (Integer), `tokens_used_this_month` (Integer), `token_reset_date` (Date), `subscription_status` (Enum: free/active/canceled/past_due), `plan_id` (String).
  - [ ] Subtask 3.2: Logic reset `tokens_used_this_month = 0` khi đến `token_reset_date` (middleware hoặc webhook trigger khi subscription renews).

- [ ] Task 4: Quota Check trước khi gọi LLM (Backend — Fail-fast)
  - [ ] Subtask 4.1: Trước khi gọi LLM trong SSE stream, check `tokens_used_this_month < monthly_token_limit`. Nếu vượt → raise HTTPException 402 "Token quota exceeded. Upgrade your plan."
  - [ ] Subtask 4.2: (Optional) Ước tính input tokens trước khi gọi để pre-check.

- [x] Task 5: Frontend — System Model Selector (thay thế BYOK)
  - [x] Subtask 5.1: Tạo component `SystemModelSelector` — fetch `GET /api/v1/models/system`, hiển thị dropdown với model name + tier badge.
  - [x] Subtask 5.2: Conditional rendering: nếu `NEXT_PUBLIC_DEPLOYMENT_MODE=cloud` → dùng `SystemModelSelector`; nếu `self-hosted` → giữ BYOK hiện tại.
  - [ ] Subtask 5.3: Ẩn/disable trang `llm-configs` (nhập API key) khi ở hosted mode.

- [x] Task 6: Frontend — Upgrade Prompt khi hết quota
  - [x] Subtask 6.1: Bắt lỗi 402 từ SSE stream, hiển thị toast "Monthly token quota exceeded" với action button "Upgrade" → `/pricing`.

## Dev Notes

### Deployment Mode
Dùng `NEXT_PUBLIC_DEPLOYMENT_MODE` để phân biệt:
- `self-hosted`: Giữ BYOK (user tự quản lý API keys) — không billing
- `hosted`: System model catalog + token billing + subscription enforcement

### Concurrency & Race Conditions
```python
# Atomic update — tránh race condition khi 2 tab chat đồng thời
await session.execute(
    update(User).where(User.id == user_id)
    .values(tokens_used_this_month=User.tokens_used_this_month + tokens_consumed)
)
```

### Pattern Reference
Tham khảo `PageLimitService` (`surfsense_backend/app/services/page_limit_service.py`) — đã implement đầy đủ check + update + estimate cho page quota. Có thể tạo `TokenQuotaService` tương tự.

### References
- `surfsense_backend/app/db.py` — User model, NewLLMConfig
- `surfsense_web/components/new-chat/model-selector.tsx` — BYOK (cần thay)
- `surfsense_backend/app/services/page_limit_service.py` — pattern tham khảo
- Endpoint SSE hiện tại: `/api/v1/chat/stream`

### Review Findings
_Code review 2026-04-14 — Blind Hunter + Edge Case Hunter + Acceptance Auditor_

#### Decision Needed
- [x] [Review][Decision→Patch] **Backend tier enforcement at chat time** — RESOLVED: Enforce ngay trong Story 3.5. Thêm tier check vào chat endpoint trước khi gọi LLM. [model_list_routes.py, new_chat_routes.py]

#### Patch
- [x] [Review][Patch] **Alembic migration absent for 7 new User columns + SubscriptionStatus enum** — DB columns (monthly_token_limit, tokens_used_this_month, token_reset_date, subscription_status, plan_id, stripe_customer_id, stripe_subscription_id) added to model but no migration file. SubscriptionStatus enum has `create_type=False` but PG type never created. [surfsense_backend/app/db.py]
- [x] [Review][Patch] **Race condition: token quota uses ORM read-modify-write instead of atomic SQL UPDATE** — Spec explicitly requires `UPDATE ... SET tokens_used = tokens_used + cost` pattern. Current code reads user, adds in Python, writes back — concurrent tabs can overspend. [surfsense_backend/app/services/token_quota_service.py:update_token_usage]
- [x] [Review][Patch] **Security: model_id > 0 allows cross-user BYOK config hijack** — Cloud mode accepts any positive integer as model_id, which maps to user-created NewLLMConfig records. Attacker can use another user's API key. Must validate model_id ≤ 0 (system models) in cloud mode. [surfsense_backend/app/routes/new_chat_routes.py]
- [x] [Review][Patch] **stream_resume_chat never deducts tokens from quota** — Token counting + deduction logic only in stream_new_chat. Resume path skips quota update entirely — violates AC 3. [surfsense_backend/app/tasks/chat/stream_new_chat.py:stream_resume_chat]
- [x] [Review][Patch] **Frontend handleResume doesn't send model_id** — onNew and handleRegenerate inject selectedSystemModelId but handleResume omits it. Backend schema already supports it. [surfsense_web/app/dashboard/[search_space_id]/chat/[chat_session_id]/page.tsx:handleResume]
- [x] [Review][Patch] **systemModelsAtom fetches unconditionally in self-hosted mode** — atomWithQuery fires on mount regardless of deployment mode. Wastes network call + may 404. Add isCloud() guard. [surfsense_web/atoms/new-llm-config/system-models-query.atoms.ts]
- [x] [Review][Patch] **_maybe_reset_monthly_tokens double-commit fragility** — Method calls session.commit() then caller also commits → potential MissingGreenlet in async context. Should let caller manage transaction boundary. [surfsense_backend/app/services/token_quota_service.py:_maybe_reset_monthly_tokens]
- [x] [Review][Patch] **get_token_usage skips monthly reset check** — Doesn't call _maybe_reset_monthly_tokens, so stale tokens_used may be returned after month rollover. [surfsense_backend/app/services/token_quota_service.py:get_token_usage]
- [x] [Review][Patch] **Token accumulation ignores None usage_metadata** — on_chat_model_end callback doesn't guard against None/missing total_tokens from LLM response metadata. Will silently skip or raise AttributeError. [surfsense_backend/app/tasks/chat/stream_new_chat.py:on_chat_model_end]
- [x] [Review][Patch] **selectedSystemModelIdAtom persists across search spaces** — Global atom never resets when user switches search space. Previous selection carries over incorrectly. [surfsense_web/atoms/new-llm-config/system-models-query.atoms.ts]
- [x] [Review][Patch] **token_reset_date stored as String(50) instead of Date column** — Should be a proper Date/DateTime column for reliable comparison. Current string comparison with fromisoformat() is fragile. [surfsense_backend/app/db.py]
- [x] [Review][Patch] **QuotaExceededError only handles HTTP 402, not mid-stream SSE quota errors** — If quota is exceeded during streaming (race condition between check and stream), SSE error is not caught as QuotaExceededError. [surfsense_web/app/dashboard/…/page.tsx]
- [x] [Review][Patch] **Indentation inconsistency in page.tsx** — Mixed tab/space indentation in modified sections. [surfsense_web/app/dashboard/[search_space_id]/chat/[chat_session_id]/page.tsx]
- [x] [Review][Patch] **displayModel falls back to models[0] silently** — If selectedSystemModelId doesn't match any model, defaults to first model without user notice. Empty array not guarded. [surfsense_web/components/new-chat/system-model-selector.tsx]
- [x] [Review][Patch] **check_token_quota boundary: tokens_used == limit passes with estimated_tokens=0** — Off-by-one: when exactly at limit, check passes. Should use >= for strict enforcement. [surfsense_backend/app/services/token_quota_service.py:check_token_quota]
- [x] [Review][Patch] **_get_tier_for_model pattern matching fragile** — Hardcoded substring checks ("gpt-4o-mini", "claude-3-haiku") will break with new model names. No fallback tier. [surfsense_backend/app/routes/model_list_routes.py:_get_tier_for_model]
- [x] [Review][Patch] **GET /models/system endpoint not gated by is_cloud()** — Endpoint accessible in self-hosted mode. Should return 404 or empty when not in cloud mode. [surfsense_backend/app/routes/model_list_routes.py]
- [x] [Review][Patch] **Subtask 5.3: llm-configs page not hidden in hosted/cloud mode** — User can still navigate to BYOK API key page. Needs conditional route guard or redirect. [surfsense_web/app/dashboard/[search_space_id]/llm-configs/]
- [x] [Review][Patch] **update_token_usage has unnecessary session.refresh()** — Refresh after atomic update is redundant and adds latency. [surfsense_backend/app/services/token_quota_service.py:update_token_usage]
- [x] [Review][Patch] **Model catalog missing cost_per_1k_tokens and explicit tier_required fields** — Spec Task 1.1 requires cost_per_1k_input_tokens, cost_per_1k_output_tokens, tier_required per model. YAML catalog doesn't include these; tier derived by fragile pattern match. [surfsense_backend/config/global_llm_config.yaml]

#### Deferred (pre-existing / out of scope)
- [x] [Review][Defer] **stripe_subscription_id has no unique constraint** [surfsense_backend/app/db.py] — deferred, will be addressed in Epic 5 (Stripe Payment Integration)
- [x] [Review][Defer] **load_llm_config_from_yaml reads API keys directly from YAML file, not env vars** [surfsense_backend/app/config.py] — deferred, pre-existing architecture pattern
