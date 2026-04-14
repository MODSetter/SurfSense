# Story 5.4: Hệ thống Khóa Tác vụ dựa trên Hạn Mức (Usage Tracking & Rate Limit Enforcement)

Status: done

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

- [x] Task 1: Thêm Page Quota Pre-check vào Document Upload Route (Backend)
  - [x] Subtask 1.1: Tìm document upload route — `surfsense_backend/app/routes/documents_routes.py`
  - [x] Subtask 1.2: Inject `PageLimitService`, gọi `estimate_pages_from_metadata(filename, file_size)` rồi `check_page_limit(user_id, estimated_pages)`.
  - [x] Subtask 1.3: `PageLimitExceededError` → `HTTPException(402)` với message mô tả quota.
  - [x] Subtask 1.4: Giữ nguyên enforcement trong Celery tasks (double-check layer).
  - [x] Subtask 1.5: Thêm pre-check cho `create_documents` endpoint (extension/YouTube connector).

- [x] Task 2: Plan-based Limits (Backend)
  - [x] Subtask 2.1: `PLAN_LIMITS` config đã có trong `config/__init__.py:314`.
  - [x] Subtask 2.2: Webhook Story 5.3 + admin approval đã update limits khi subscription change.

- [x] Task 3: Frontend — Bắt lỗi Quota Exceeded
  - [x] Subtask 3.1: Document upload — `DocumentUploadTab.tsx` bắt HTTP 402 (check `error.status`) cho cả file và folder upload.
  - [x] Subtask 3.2: Toast error với "Upgrade" action button → navigate to `/pricing`.
  - [x] Subtask 3.3: Chat SSE — đã có `QuotaExceededError` pattern từ Story 3.5 (`page.tsx`).

- [x] Task 4: Frontend — Quota Indicator (Dashboard)
  - [x] Subtask 4.1: Extend `UserRead` schema + Zod type với `monthly_token_limit`, `tokens_used_this_month`, `plan_id`, `subscription_status`.
  - [x] Subtask 4.2: Extend `PageUsageDisplay` — hiển thị 2 progress bars (Pages, Tokens) trong sidebar.
  - [x] Subtask 4.3: Warning state (amber) khi usage > 80%, critical state (red) khi > 95%.

- [ ] Task 5: Anti-spam Rate Limiting (Optional — skipped per spec)

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
- `surfsense_backend/app/routes/documents_routes.py` — document upload route
- `surfsense_web/components/sources/DocumentUploadTab.tsx` — frontend upload component

## Dev Agent Record

### Implementation (2026-04-15)

**Backend:**
- `documents_routes.py`: Added page quota pre-check to both `create_documents` and `create_documents_file_upload` endpoints. Uses `PageLimitService.estimate_pages_from_metadata()` for fast estimation before any I/O, raises HTTP 402 on exceeded quota.
- `schemas/users.py`: Extended `UserRead` with `monthly_token_limit`, `tokens_used_this_month`, `plan_id`, `subscription_status` — exposed via `/api/v1/users/me`.

**Frontend:**
- `DocumentUploadTab.tsx`: 402 handling in both file upload (`onError`) and folder upload (`catch`) paths — shows toast with "Upgrade" action linking to `/pricing`.
- `user.types.ts`: Zod schema extended with token quota fields.
- `PageUsageDisplay.tsx`: Extended with token usage bar, color-coded warning (amber >80%, red >95%).
- `layout.types.ts`: `PageUsage` interface extended with `tokensUsed`/`tokensLimit`.
- `LayoutDataProvider.tsx`: Passes token data to sidebar.

### File List
- `surfsense_backend/app/routes/documents_routes.py` — page quota pre-check in upload endpoints
- `surfsense_backend/app/schemas/users.py` — extended UserRead
- `surfsense_web/components/sources/DocumentUploadTab.tsx` — 402 error handling
- `surfsense_web/contracts/types/user.types.ts` — quota fields in Zod schema
- `surfsense_web/components/layout/ui/sidebar/PageUsageDisplay.tsx` — token usage bar + color states
- `surfsense_web/components/layout/types/layout.types.ts` — extended PageUsage interface
- `surfsense_web/components/layout/providers/LayoutDataProvider.tsx` — pass token data
- `surfsense_web/components/layout/ui/sidebar/Sidebar.tsx` — pass token props to PageUsageDisplay

## Review Findings (2026-04-15)

- [x] [Review][Patch] PAST_DUE users retain pro-tier limits and can continue consuming resources [page_limit_service.py, token_quota_service.py] — **Fixed**: Both services now check subscription_status and apply free-tier limits when PAST_DUE
