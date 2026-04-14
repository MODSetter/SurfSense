# Story 5.4: Hệ thống Khóa Tác vụ dựa trên Hạn Mức (Usage Tracking & Rate Limit Enforcement)

Status: ready-for-dev

## Story

As a Kỹ sư Hệ thống,
I want những người dùng hết quota (vượt quá file upload hoặc số lượng tin nhắn) bị từ chối dịch vụ cho đến khi nâng cấp,
so that mô hình kinh doanh không bị lỗ do chi phí LLM và Storage, áp dụng theo FR13.

## Acceptance Criteria

1. Endpoint Upload (Document) kiểm tra `pages_used` vs `pages_limit` (dựa trên subscription tier) → từ chối nếu vượt.
2. Endpoint Chat (RAG AI) kiểm tra `tokens_used_this_month` vs `monthly_token_limit` → từ chối nếu vượt (đã cover ở Story 3.5 Task 4).
3. API trả lỗi `402 Payment Required` khi quota exceeded.
4. UI hiển thị Toast Error hoặc Modal up-sell "Upgrade to Pro".
5. Dashboard hiển thị quota indicator (pages used / limit, tokens used / limit).

## As-Is (Code hiện tại)

| Component | Hiện trạng | File |
|-----------|-----------|------|
| Page Quota Service | **Đã implement đầy đủ** — `check_page_limit()`, `update_page_usage()`, `get_page_usage()`, `estimate_pages_*()` | `surfsense_backend/app/services/page_limit_service.py` |
| Enforcement trong Celery | **Đã có** — check quota trước khi process document | `document_tasks.py` |
| Enforcement trong Connectors | **Đã có** — Google Drive, OneDrive, Dropbox indexers check `remaining_quota` | `connector_indexers/*.py` |
| Enforcement tại HTTP API | **Chưa có** — document upload route không check quota trước khi enqueue task | routes/ |
| Token Quota Service | **Chưa có** — sẽ tạo ở Story 3.5 | |
| Frontend Quota UI | **Chưa có** | |
| Frontend Error Handling | **Chưa có** — không bắt 402 từ upload/chat | |

**Gap chính:**
1. Thiếu quota pre-check tại HTTP layer (upload route) — user phải đợi Celery task fail mới biết bị reject
2. Thiếu frontend feedback khi quota exceeded
3. Thiếu quota indicator trong dashboard

## Tasks / Subtasks

- [ ] Task 1: Thêm Page Quota Pre-check vào Document Upload Route (Backend)
  - [ ] Subtask 1.1: Tìm document upload route (search trong `surfsense_backend/app/routes/`).
  - [ ] Subtask 1.2: Inject `PageLimitService`, gọi `estimate_pages_from_metadata(filename, file_size)` rồi `check_page_limit(user_id, estimated_pages)`.
  - [ ] Subtask 1.3: Nếu `PageLimitExceededError` → raise `HTTPException(402, detail={"error": "page_quota_exceeded", "pages_used": X, "pages_limit": Y, "message": "..."})`.
  - [ ] Subtask 1.4: Giữ nguyên enforcement trong Celery tasks (double-check layer cho trường hợp estimate sai).

- [ ] Task 2: Plan-based Limits (Backend)
  - [ ] Subtask 2.1: Tạo config mapping `plan_id` → limits (liên kết với Story 5.3):
    ```python
    PLAN_LIMITS = {
        "free": {"pages_limit": 500, "monthly_token_limit": 50_000, "max_docs": 10},
        "pro": {"pages_limit": 5000, "monthly_token_limit": 1_000_000, "max_docs": 100},
    }
    ```
  - [ ] Subtask 2.2: Khi subscription activate/update (webhook Story 5.3), update `pages_limit` và `monthly_token_limit` theo plan mới.

- [ ] Task 3: Frontend — Bắt lỗi Quota Exceeded
  - [ ] Subtask 3.1: Document upload component — bắt HTTP 402 response, phân biệt `page_quota_exceeded` vs `token_quota_exceeded`.
  - [ ] Subtask 3.2: Hiển thị toast/modal: "Bạn đã dùng X/Y pages. Nâng cấp lên Pro để tiếp tục." với link đến `/pricing`.
  - [ ] Subtask 3.3: Chat component — bắt HTTP 402 từ SSE stream (tương tự Story 3.5 Task 6).

- [ ] Task 4: Frontend — Quota Indicator (Dashboard)
  - [ ] Subtask 4.1: Expose `pages_used`, `pages_limit`, `tokens_used_this_month`, `monthly_token_limit` qua user endpoint hoặc Zero sync.
  - [ ] Subtask 4.2: Tạo component `QuotaIndicator` — hiển thị 2 progress bars (Pages, Tokens) trong sidebar/header.
  - [ ] Subtask 4.3: Warning state (amber) khi usage > 80%, critical state (red) khi > 95%.

- [ ] Task 5: Anti-spam Rate Limiting (Optional — nếu cần)
  - [ ] Subtask 5.1: Thêm rate limit cho chat endpoint (e.g. max 60 requests/hour cho free tier).
  - [ ] Subtask 5.2: Dùng Redis counter hoặc FastAPI dependency.

## Dev Notes

### PageLimitService — đã sẵn sàng, không cần viết lại
`page_limit_service.py` đã có đầy đủ:
- `check_page_limit(user_id, estimated_pages)` → raises `PageLimitExceededError`
- `update_page_usage(user_id, pages_to_add)`
- `estimate_pages_before_processing(file_path)`
- `estimate_pages_from_metadata(filename, file_size)` (pure function, dùng cho HTTP layer)

### Enforcement Layers
```
HTTP Upload Route → PageLimitService.check_page_limit() [FAST — pre-check]
       ↓ (nếu pass)
Celery Task → PageLimitService.check_page_limit() [ACCURATE — sau khi parse xong]
       ↓ (nếu pass)
PageLimitService.update_page_usage() [COMMIT — tăng pages_used]
```

### References
- `surfsense_backend/app/services/page_limit_service.py` — page quota (đọc, ít sửa)
- `surfsense_backend/app/tasks/celery_tasks/document_tasks.py` — enforcement pattern hiện tại
- `surfsense_backend/app/routes/` — document upload route (cần tìm)
- Frontend upload component (cần tìm)
