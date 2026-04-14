# Story 3.5: Enforce Page Quota tại Document Upload API

Status: ready-for-dev

## Context / Correction Note
> **⚠️ Story gốc bị sai hướng.** Story gốc mô tả việc xóa BYOK và dùng system API keys — đây là sai với kiến trúc thực tế của SurfSense. SurfSense là **self-hosted** product, BYOK (Bring-Your-Own-Key) là tính năng cốt lõi và cần giữ nguyên. Hệ thống quota thực tế dùng **pages** (document processing), không phải tokens LLM.

## Story

As a Người dùng,
I want nhận thông báo rõ ràng khi tôi đã dùng hết pages quota,
so that tôi biết cần mua thêm page packs trước khi upload thêm tài liệu.

## Actual Architecture (as-is)

- **LLM**: BYOK via `NewLLMConfig` — user tự cấu hình API key của từng provider (OpenAI, Anthropic, etc.). **Giữ nguyên, không thay đổi.**
- **Quota**: `pages_limit` / `pages_used` trên bảng `User` — track lượng pages đã ETL
- **PageLimitService**: `surfsense_backend/app/services/page_limit_service.py` — đã implement đầy đủ `check_page_limit()`, `update_page_usage()`, `get_page_usage()`
- **Enforcement đã có**: trong `document_tasks.py` (Celery), các connector indexers (Google Drive, OneDrive, Dropbox, Notion, etc.)
- **Enforcement còn thiếu**: tại HTTP API layer trước khi enqueue task

## Acceptance Criteria

1. Khi user upload document và `pages_used >= pages_limit`, API trả về HTTP 402 với message rõ ràng trước khi queue Celery task.
2. Frontend bắt lỗi 402 từ upload API và hiển thị toast/modal hướng user đến trang Pricing để mua thêm pages.
3. Endpoint `GET /api/v1/users/me` (hoặc equivalent) trả về `pages_used` và `pages_limit` để FE hiển thị quota indicator.

## Tasks / Subtasks

- [ ] Task 1: Thêm quota check vào Document Upload API route
  - [ ] Subtask 1.1: Tại route xử lý document upload (tìm trong `surfsense_backend/app/routes/`), inject `PageLimitService` và gọi `check_page_limit()` với estimated pages trước khi enqueue Celery task.
  - [ ] Subtask 1.2: Raise `HTTPException(status_code=402, detail="Page quota exceeded. Please purchase more pages.")` khi bị vượt giới hạn.
- [ ] Task 2: Frontend xử lý lỗi 402
  - [ ] Subtask 2.1: Trong component upload document, bắt HTTP 402 response và render toast/alert "Bạn đã hết page quota. Mua thêm tại /pricing".
  - [ ] Subtask 2.2: Link trong toast/alert dẫn đến `/pricing`.
- [ ] Task 3: Hiển thị quota indicator (nice-to-have)
  - [ ] Subtask 3.1: Thêm `pages_used` / `pages_limit` vào response của current user endpoint.
  - [ ] Subtask 3.2: Hiển thị progress bar nhỏ trong UI.

## Dev Notes

### What Already Works (Don't Re-Implement)
- `PageLimitService.check_page_limit()` — dùng trực tiếp, không cần viết lại
- Quota enforcement trong Celery tasks và connectors — đã có, giữ nguyên
- `pages_limit` tự động tăng khi user mua page pack (xem `stripe_routes.py:_fulfill_completed_purchase`)

### What Needs to Change
- Chỉ cần thêm 1 check tại HTTP layer (trước khi enqueue) để user nhận feedback ngay, thay vì đợi task chạy xong mới biết bị reject.

### References
- `surfsense_backend/app/services/page_limit_service.py`
- `surfsense_backend/app/tasks/celery_tasks/document_tasks.py` (xem cách dùng PageLimitService ở đây làm mẫu)

## Dev Agent Record

### Agent Model Used
_TBD_

### File List
- `surfsense_backend/app/routes/` (document upload route — cần tìm file cụ thể)
- `surfsense_backend/app/services/page_limit_service.py` (đọc, không sửa)
- Frontend upload component (cần tìm file cụ thể)
