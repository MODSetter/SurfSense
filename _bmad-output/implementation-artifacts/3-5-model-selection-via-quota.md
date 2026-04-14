# Story 3.5: Lựa chọn Mô hình LLM dựa trên Subscription (Model Selection via Quota)

Status: ready-for-dev

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

- [ ] Task 5: Frontend — System Model Selector (thay thế BYOK)
  - [ ] Subtask 5.1: Tạo component `SystemModelSelector` — fetch `GET /api/v1/models`, hiển thị dropdown với model name + cost indicator.
  - [ ] Subtask 5.2: Conditional rendering: nếu `NEXT_PUBLIC_DEPLOYMENT_MODE=hosted` → dùng `SystemModelSelector`; nếu `self-hosted` → giữ BYOK hiện tại.
  - [ ] Subtask 5.3: Ẩn/disable trang `llm-configs` (nhập API key) khi ở hosted mode.

- [ ] Task 6: Frontend — Upgrade Prompt khi hết quota
  - [ ] Subtask 6.1: Bắt lỗi 402 từ SSE stream, hiển thị modal "Bạn đã hết token quota. Nâng cấp gói tại /pricing".

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
