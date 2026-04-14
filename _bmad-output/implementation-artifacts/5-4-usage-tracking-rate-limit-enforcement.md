# Story 5.4: Enforce Page Quota tại HTTP API Layer & Frontend Feedback

Status: ready-for-dev

## Context / Correction Note
> **⚠️ Story gốc bị sai một phần.** Story gốc mô tả implement quota từ đầu (tạo `check_upload_quota()`, v.v.). Thực tế, hệ thống quota **đã tồn tại đầy đủ** với `PageLimitService`, enforcement trong Celery tasks và tất cả connector indexers. Task thực tế chỉ là: (1) thêm check tại HTTP API layer trước khi enqueue task, (2) feedback rõ ràng ở Frontend, (3) hiển thị quota usage trong UI.

## Story

As a Người dùng,
I want nhận phản hồi ngay lập tức khi tôi hết page quota thay vì đợi task xử lý xong mới biết,
so that tôi có thể mua thêm pages trước khi tiếp tục upload.

## Actual Architecture (as-is)

**Đã implement và đang hoạt động:**
- `surfsense_backend/app/services/page_limit_service.py`:
  - `PageLimitService.check_page_limit(user_id, estimated_pages)` — raises `PageLimitExceededError`
  - `PageLimitService.update_page_usage(user_id, pages_to_add)`
  - `PageLimitService.get_page_usage(user_id)` → `(pages_used, pages_limit)`
  - `PageLimitService.estimate_pages_before_processing(file_path)` — ước tính từ file size/type
  - `PageLimitService.estimate_pages_from_metadata(filename, file_size)` — pure function, không cần file
- Enforcement **đã có** trong:
  - `surfsense_backend/app/tasks/celery_tasks/document_tasks.py` — check trước khi xử lý
  - `surfsense_backend/app/tasks/connector_indexers/google_drive_indexer.py`
  - `surfsense_backend/app/tasks/connector_indexers/onedrive_indexer.py`
  - `surfsense_backend/app/tasks/connector_indexers/dropbox_indexer.py`
  - (và các connectors khác)

**Còn thiếu:**
- Check tại HTTP API layer (document upload route) — hiện tại task mới fail sau khi đã enqueue
- Frontend hiển thị `pages_used` / `pages_limit` (quota indicator)
- Frontend bắt lỗi 402 từ upload và hiển thị upgrade prompt

## Acceptance Criteria

1. Khi user upload document và estimated pages sẽ vượt `pages_limit`, API trả về 402 **ngay lập tức** (không enqueue Celery task).
2. Frontend upload component bắt HTTP 402 và hiển thị toast: "Bạn đã hết page quota (X/Y pages). Mua thêm tại /pricing".
3. Dashboard hiển thị quota indicator: "X / Y pages used" với progress bar.
4. API `GET /api/v1/users/me` (hoặc equivalent) trả về `pages_used` và `pages_limit`.

## Tasks / Subtasks

- [ ] Task 1: Thêm quota pre-check vào Document Upload HTTP route
  - [ ] Subtask 1.1: Tìm document upload route (search `surfsense_backend/app/routes/` cho endpoint nhận file upload).
  - [ ] Subtask 1.2: Inject `PageLimitService`, gọi `estimate_pages_from_metadata(filename, file_size)` để ước tính.
  - [ ] Subtask 1.3: Gọi `check_page_limit(user_id, estimated_pages)` — nếu raises `PageLimitExceededError`, return `HTTPException(402, "Page quota exceeded. Purchase more pages at /pricing.")`.
- [ ] Task 2: Expose quota info trên user endpoint
  - [ ] Subtask 2.1: Đảm bảo `GET /api/v1/users/me` response bao gồm `pages_used` và `pages_limit` (kiểm tra `UserRead` schema trong `db.py`).
- [ ] Task 3: Frontend quota indicator
  - [ ] Subtask 3.1: Đọc `pages_used` / `pages_limit` từ current user data (đã có trong Zero/DB sync hoặc API).
  - [ ] Subtask 3.2: Hiển thị progress bar nhỏ trong Dashboard sidebar hoặc header: "X / Y pages".
  - [ ] Subtask 3.3: Khi `pages_used / pages_limit > 0.9`, đổi màu indicator sang warning (amber).
- [ ] Task 4: Frontend upload error handling
  - [ ] Subtask 4.1: Trong document upload component, bắt HTTP 402 response.
  - [ ] Subtask 4.2: Hiển thị toast/alert với link đến `/pricing`.

## Dev Notes

### Không cần viết lại PageLimitService
`PageLimitService` đã có đầy đủ logic. Chỉ cần inject và gọi tại HTTP layer.

### Pattern dùng trong Celery tasks (làm mẫu)
```python
# Trong document_tasks.py
page_limit_service = PageLimitService(db_session)
await page_limit_service.check_page_limit(user_id, estimated_pages)
# → raises PageLimitExceededError nếu vượt quota
```

### UserRead schema — kiểm tra xem đã expose pages_used chưa
```python
# Tìm trong db.py hoặc schemas/
class UserRead(schemas.BaseUser[uuid.UUID]):
    pages_limit: int
    pages_used: int  # ← check xem field này có trong schema không
```

### References
- `surfsense_backend/app/services/page_limit_service.py`
- `surfsense_backend/app/tasks/celery_tasks/document_tasks.py` (xem cách dùng làm mẫu)
- `surfsense_backend/app/db.py` (UserRead schema / User model)
- `surfsense_web/` (document upload component — cần tìm)

## Dev Agent Record

### Agent Model Used
_TBD_

### File List
- `surfsense_backend/app/routes/` (document upload route)
- `surfsense_backend/app/services/page_limit_service.py` (đọc, không sửa)
- Frontend upload + dashboard components
