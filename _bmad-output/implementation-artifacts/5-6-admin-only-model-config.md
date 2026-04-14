# Story 5.6: Admin-only Model Configuration (LLM / Image / Vision)

Status: done

## Story

As a Quản trị viên (Admin),
I want chỉ mình có quyền thêm/sửa/xóa cấu hình LLM, Image Generation, và Vision models,
so that người dùng thông thường chỉ có thể chọn model để sử dụng mà không thể thêm BYOK credentials hay thay đổi cấu hình model.

## Acceptance Criteria

1. Chỉ superuser (`is_superuser=TRUE`) mới có thể gọi `POST/PUT/DELETE` cho cả 3 loại model config — non-superuser nhận HTTP 403 Forbidden.
2. Regular user vẫn có thể `GET` (đọc/liệt kê) model configs trong search space của họ.
3. Trong chat interface, nút "Add Model", "Add Image Model", "Add Vision Model" bị ẩn hoàn toàn với regular user.
4. Trong search space settings dialog (LLM/Image/Vision tabs), nút Add/Edit/Delete bị ẩn với regular user — chỉ hiển thị danh sách model read-only.
5. Admin-created configs lưu với `user_id=NULL` (không gắn với user cụ thể) — visible cho tất cả members trong search space.
6. DB migration: `user_id` trên cả 3 bảng config trở thành nullable để cho phép admin configs với `user_id=NULL`.

## As-Is (Code trước Story này)

| Component | Hiện trạng |
|-----------|-----------|
| `new_llm_configs.user_id` | NOT NULL — mọi config đều gắn với user cụ thể |
| `image_generation_configs.user_id` | NOT NULL |
| `vision_llm_configs.user_id` | NOT NULL |
| Backend CUD permissions | RBAC per search space (`check_permission`) — bất kỳ member có `llm_configs:create` đều tạo được |
| Frontend Add buttons | Hiển thị dựa theo RBAC permissions — owner và editor đều thấy |

## Tasks / Subtasks

- [x] Task 1: DB Migration
  - [x] Subtask 1.1: Tạo migration `128_make_model_config_user_id_nullable.py`
  - [x] Subtask 1.2: `ALTER TABLE new_llm_configs ALTER COLUMN user_id DROP NOT NULL`
  - [x] Subtask 1.3: Tương tự cho `image_generation_configs` và `vision_llm_configs`
  - [x] Subtask 1.4: Downgrade: xóa rows có `user_id=NULL` rồi re-add NOT NULL

- [x] Task 2: Shared Superuser Dependency
  - [x] Subtask 2.1: Thêm `current_superuser = fastapi_users.current_user(active=True, superuser=True)` vào `users.py`
  - [x] Subtask 2.2: Cập nhật `admin_routes.py` để import `current_superuser` từ `users.py` thay vì định nghĩa lại

- [x] Task 3: Backend — Gate CUD endpoints với superuser
  - [x] Subtask 3.1: `new_llm_config_routes.py` — POST/PUT/DELETE dùng `Depends(current_superuser)`, set `user_id=None`, xóa `check_permission`
  - [x] Subtask 3.2: `image_generation_routes.py` — tương tự (POST/PUT/DELETE config endpoints)
  - [x] Subtask 3.3: `vision_llm_routes.py` — tương tự

- [x] Task 4: Frontend — Settings dialog managers
  - [x] Subtask 4.1: `model-config-manager.tsx` — import `currentUserAtom`, replace RBAC flags (`canCreate/Update/Delete`) với `currentUser.is_superuser`
  - [x] Subtask 4.2: `image-model-manager.tsx` — tương tự
  - [x] Subtask 4.3: `vision-model-manager.tsx` — tương tự

- [x] Task 5: Frontend — Chat interface model selector
  - [x] Subtask 5.1: `model-selector.tsx` — thêm `?` vào `onAddNewLLM` prop (optional), wrap "Add Model" button với `{onAddNewLLM && (...)}`
  - [x] Subtask 5.2: `chat-header.tsx` — import `currentUserAtom`, compute `isAdmin`, truyền `onAddNew*={isAdmin ? handler : undefined}` cho cả 3 model types

## Dev Notes

### Tại sao làm optional thay vì truyền boolean?
`ModelSelector` đã có pattern `{onAddNewImage && (...)}` cho Image và Vision — consistent nhất là làm `onAddNewLLM` optional và dùng cùng pattern, thay vì thêm prop `showAddButton`.

### Existing model configs (có user_id)
Existing configs của các user trước kia vẫn hoạt động bình thường — migration chỉ làm nullable, không xóa data. Tuy nhiên, vì GET endpoint không filter theo user_id nên tất cả configs (kể cả cũ) đều visible cho mọi member trong search space.

### Image/Vision edit buttons trong model selector
`onEditImage` và `onEditVision` props không được gated — regular user vẫn có thể click edit nhưng sẽ xem ở mode "view" (dialog opens in view mode for global configs). Việc submit edit sẽ bị 403 từ backend. Đây là acceptable — UX nhất quán đủ dùng.

## Dev Agent Record

### Verification Results (2026-04-15)

**Regular user (epic5user@example.com):**
- Model selector popup: "No models found" — NO Add/Add Image Model/Add Vision Model buttons ✅
- `POST /api/v1/new-llm-configs` with regular user token → HTTP 403 Forbidden ✅

**Admin (admin@surfsense.local):**
- `POST /api/v1/new-llm-configs` → HTTP 422 (schema validation error, NOT 403) → superuser check passed ✅

**DB:**
- `new_llm_configs.user_id`: `is_nullable=YES` ✅
- `image_generation_configs.user_id`: `is_nullable=YES` ✅
- `vision_llm_configs.user_id`: `is_nullable=YES` ✅

### File List
- `surfsense_backend/alembic/versions/128_make_model_config_user_id_nullable.py` — NEW migration
- `surfsense_backend/app/users.py` — added `current_superuser` export
- `surfsense_backend/app/routes/admin_routes.py` — import `current_superuser` from `users.py` instead of defining locally
- `surfsense_backend/app/routes/new_llm_config_routes.py` — superuser gate on POST/PUT/DELETE, `user_id=None`
- `surfsense_backend/app/routes/image_generation_routes.py` — superuser gate on config POST/PUT/DELETE
- `surfsense_backend/app/routes/vision_llm_routes.py` — superuser gate on POST/PUT/DELETE
- `surfsense_web/components/settings/model-config-manager.tsx` — `is_superuser` replaces RBAC flags
- `surfsense_web/components/settings/image-model-manager.tsx` — same
- `surfsense_web/components/settings/vision-model-manager.tsx` — same
- `surfsense_web/components/new-chat/model-selector.tsx` — `onAddNewLLM` made optional, LLM Add button gated
- `surfsense_web/components/new-chat/chat-header.tsx` — `isAdmin` check gates all 3 `onAddNew*` props

### Change Log
- 2026-04-15: Implement admin-only model configuration — superuser gate on backend CUD, hide Add/Edit/Delete UI for regular users in both chat selector and settings dialog.

---

## Post-Story Bug Fixes & Enhancements (2026-04-15)

### Bug 1: "No models found" for regular users

**Root Cause:** Admin configs scoped to `search_space_id=5`. Each user has their own space. GET filtered strictly by space ID → configs invisible to other users.

**Fix:**
- Migration 129: `search_space_id` nullable in all 3 config tables
- `db.py`: `search_space_id = nullable=True` in all 3 SQLAlchemy models (also fixed `user_id` mismatch)
- Schemas: `search_space_id: int | None = None` in Create/Read for all 3 types
- GET list query: `WHERE search_space_id = :id OR search_space_id IS NULL`
- Re-seeded all configs without `search_space_id` → global (visible to all spaces)

### Bug 2: Chat error with stale config ID

**Root Cause:** Frontend kept `agent_llm_id` pointing to a deleted config.

**Fix:** `model-selector.tsx` — `useEffect` auto-resets `agent_llm_id` to `null` when saved preference ID no longer exists in fetched configs.

### Bug 3: db.py `nullable=False` mismatch

**Root Cause:** Migration 128 made DB columns nullable but SQLAlchemy models still said `nullable=False`.

**Fix:** All 3 models in `db.py` updated to `nullable=True` for both `user_id` and `search_space_id`.

### Security: api_key exposed in GET list

**Fix:** GET list response model changed from `*Read` (exposes `api_key`) to `*Public` (hides it) for all 3 config types.

### New: Image configs (3 global, via v98store)

| Name | model_name |
|------|-----------|
| DALL-E 3 | `dall-e-3` |
| GPT-Image 1 | `gpt-image-1` |
| Flux Pro | `flux-pro` |

### New: Vision configs (3 global, via v98store)

| Name | model_name |
|------|-----------|
| GPT-4o Vision | `gpt-4o` |
| Claude Sonnet 4 Vision | `claude-sonnet-4-20250514` |
| Gemini 2.5 Flash Vision | `gemini-2.5-flash` |

### Enhancement: Edit buttons admin-only in model selector

**Fix:** `onEditLLM` prop in `ModelSelectorProps` changed from required → optional. In `chat-header.tsx`, all 3 `onEdit*` props now gated with `isAdmin ? handler : undefined` — consistent với `onAdd*` pattern đã có. Regular users thấy model list read-only, không có edit button trên hover.

### Additional Files Changed
- `surfsense_backend/alembic/versions/129_make_model_config_search_space_id_nullable.py`
- `surfsense_backend/app/db.py`
- `surfsense_backend/app/schemas/new_llm_config.py`, `image_generation.py`, `vision_llm.py`
- `surfsense_backend/app/routes/new_llm_config_routes.py`, `image_generation_routes.py`, `vision_llm_routes.py`
- `surfsense_web/components/new-chat/model-selector.tsx`
- `surfsense_web/components/new-chat/chat-header.tsx`

## Review Findings (2026-04-15)

- [x] [Review][Patch] Superuser config update/delete can modify any config (not just global ones) [new_llm_config_routes.py:274,357, image_generation_routes.py:373,405, vision_llm_routes.py:222,254] — **Fixed**: Added `user_id.is_(None)` filter to all superuser PUT/DELETE endpoints
- [x] [Review][Patch] admin_approval_mode field missing from CreateSubscriptionCheckoutResponse — **Already fixed**: field was already present in schemas/stripe.py with `bool = False` default
