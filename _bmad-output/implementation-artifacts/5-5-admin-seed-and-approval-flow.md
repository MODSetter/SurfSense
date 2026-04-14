# Story 5.5: Admin Seed Account & Admin-Approval Subscription Flow

Status: done

## Story

As a Kỹ sư / Admin,
I want hệ thống tự tạo sẵn một tài khoản admin với đầy đủ quyền khi khởi động lần đầu, và khi Stripe chưa được cấu hình thì vẫn có thể test toàn bộ luồng Pro subscription thông qua giao diện duyệt thủ công của admin,
so that development và testing không bị chặn bởi việc thiếu Stripe credentials.

## Acceptance Criteria

1. Khi chạy `alembic upgrade head` trên database trống, hệ thống tự seed một user admin với thông tin mặc định (`admin@surfsense.local` / `Admin@SurfSense1`), overridable qua env vars `ADMIN_EMAIL` / `ADMIN_PASSWORD`.
2. Admin được seed với `is_superuser=TRUE`, `subscription_status='active'`, `plan_id='pro_yearly'`, `monthly_token_limit=1_000_000`, `pages_limit=5000` và có đủ search space, roles, membership, và default prompts.
3. Migration seed là idempotent: nếu đã có bất kỳ user nào trong DB thì bỏ qua, không insert lại.
4. Superuser có thể xem danh sách pending subscription requests tại `GET /api/v1/admin/subscription-requests`.
5. Superuser có thể approve request: `POST /api/v1/admin/subscription-requests/{id}/approve` → user được activate Pro plan ngay lập tức (không cần Stripe).
6. Superuser có thể reject request: `POST /api/v1/admin/subscription-requests/{id}/reject` → request bị đánh dấu rejected.
7. Non-superuser bị từ chối với HTTP 403 khi truy cập các endpoint admin.
8. Frontend tại `/admin/subscription-requests` hiển thị bảng pending requests với nút Approve / Reject; chuyển hướng về `/login` nếu chưa đăng nhập, hiển thị "Access denied" nếu không có quyền superuser.

## As-Is (Code trước Story này)

| Component | Hiện trạng |
|-----------|-----------|
| Admin user | Không có — DB trống sau fresh install |
| Subscription flow khi không có Stripe | Trả về HTTP 503 (xem Story 5.2) |
| Admin routes | Không có |
| `subscription_requests` table | Không có |
| `SubscriptionRequest` model | Không có |

## Tasks / Subtasks

- [x] Task 1: Admin Seed Migration
  - [x] Subtask 1.1: Tạo migration `126_seed_admin_user.py` — chỉ insert khi `SELECT 1 FROM "user" LIMIT 1` trả về empty.
  - [x] Subtask 1.2: Hash password bằng `argon2-cffi` (đã cài sẵn qua fastapi-users) bên trong migration function.
  - [x] Subtask 1.3: Insert admin user với tất cả subscription fields đầy đủ.
  - [x] Subtask 1.4: Insert default search space (với `citations_enabled=TRUE`), Owner/Editor/Viewer roles, owner membership.
  - [x] Subtask 1.5: Insert 8 default prompts (`fix-grammar`, `make-shorter`, `translate`, `rewrite`, `summarize`, `explain`, `ask-knowledge-base`, `look-up-web`) với `ON CONFLICT DO NOTHING`.
  - [x] Subtask 1.6: Downgrade là no-op (không xóa users).

- [x] Task 2: Subscription Requests Table Migration
  - [x] Subtask 2.1: Tạo migration `127_add_subscription_requests_table.py` — dùng raw SQL để tránh SQLAlchemy enum auto-create conflict.
  - [x] Subtask 2.2: `DROP TYPE IF EXISTS subscriptionrequeststatus` trước khi `CREATE TYPE ... AS ENUM ('pending', 'approved', 'rejected')`.
  - [x] Subtask 2.3: Tạo bảng `subscription_requests` với columns: `id` (UUID PK), `user_id` (FK → user CASCADE), `plan_id` (VARCHAR 50), `status` (subscriptionrequeststatus DEFAULT 'pending'), `created_at`, `approved_at` (nullable), `approved_by` (FK → user nullable).
  - [x] Subtask 2.4: Tạo index trên `user_id`.

- [x] Task 3: SubscriptionRequest Model & ORM
  - [x] Subtask 3.1: Thêm `SubscriptionRequestStatus(StrEnum)` enum vào `db.py` — values: `PENDING="pending"`, `APPROVED="approved"`, `REJECTED="rejected"`.
  - [x] Subtask 3.2: Thêm `SubscriptionRequest(Base)` model sau class `PagePurchase` trong `db.py`.
  - [x] Subtask 3.3: Thêm `values_callable=lambda x: [e.value for e in x]` vào tất cả `SQLAlchemyEnum(SubscriptionStatus)` và `SQLAlchemyEnum(SubscriptionRequestStatus)` — bắt buộc để ORM map DB lowercase values thay vì enum member names uppercase.
  - [x] Subtask 3.4: Thêm relationship `subscription_requests` vào cả hai nhánh User model (LOCAL và Google OAuth).

- [x] Task 4: Admin Routes Backend
  - [x] Subtask 4.1: Tạo `surfsense_backend/app/routes/admin_routes.py` với `APIRouter(prefix="/admin")`.
  - [x] Subtask 4.2: Dùng `fastapi_users.current_user(active=True, superuser=True)` làm dependency — tự động trả 403 cho non-superuser.
  - [x] Subtask 4.3: `GET /admin/subscription-requests` — query tất cả PENDING requests, JOIN lấy user email, trả về `List[SubscriptionRequestItem]`.
  - [x] Subtask 4.4: `POST /admin/subscription-requests/{id}/approve` — set `status=APPROVED`, `approved_at=now()`, `approved_by=current_user.id`; activate user subscription dùng cùng logic với `_activate_subscription_from_checkout` (Story 5.3): set `subscription_status=ACTIVE`, `plan_id`, `monthly_token_limit`, `pages_limit=max(pages_used, plan_limit)`, `tokens_used_this_month=0`, `token_reset_date=today`.
  - [x] Subtask 4.5: `POST /admin/subscription-requests/{id}/reject` — set `status=REJECTED`.
  - [x] Subtask 4.6: Đăng ký router trong `surfsense_backend/app/routes/__init__.py` và `app.py`.

- [x] Task 5: Admin Frontend Page
  - [x] Subtask 5.1: Tạo `surfsense_web/app/admin/subscription-requests/page.tsx` — client component.
  - [x] Subtask 5.2: Auth guard: gọi `isAuthenticated()` — nếu false redirect `/login`; nếu API trả 403 hiển thị "Access denied. Superuser privileges required."
  - [x] Subtask 5.3: Hiển thị bảng: User email | Plan | Requested At | Actions (Approve / Reject).
  - [x] Subtask 5.4: Approve/Reject gọi endpoint tương ứng; sau khi thành công xóa row khỏi danh sách local.

## Dev Notes

### Tại sao cần Admin Seed?
Fresh install không có user nào → không thể login để test. Admin seed giải quyết cold-start problem, đặc biệt cho CI/CD và development.

### Tại sao dùng raw SQL trong migration 127?
`op.create_table` với `SQLAlchemy.Enum(create_type=True/False)` vẫn trigger `_on_table_create` event tự động tạo enum type. Dùng raw SQL tránh `DuplicateObjectError` khi enum đã tồn tại từ `Base.metadata.create_all()`.

### ORM `values_callable` là bắt buộc
SQLAlchemy `Enum` mặc định dùng member **names** (uppercase: FREE, ACTIVE) để map vào DB, nhưng migration tạo enum với **values** lowercase (free, active). Không có `values_callable` → `LookupError: 'active' is not among enum values; Possible values: FREE, ACTIVE`. Fix: `values_callable=lambda x: [e.value for e in x]`.

### Admin Approval Activation Logic
Reuse `PLAN_LIMITS` config từ `config/__init__.py`. `pages_limit = max(user.pages_used, PLAN_LIMITS[plan_id]["pages_limit"])` để không lock out user khỏi content đã upload.

### Luồng test E2E (không có Stripe)
1. Register user → Login → `/pricing` → "Upgrade to Pro" → toast "Subscription request submitted"
2. Login admin (`admin@surfsense.local` / `Admin@SurfSense1`) → `/admin/subscription-requests` → Approve
3. Login lại user → DB: `subscription_status=active`, `plan_id=pro_monthly`, `monthly_token_limit=1_000_000`

## Dev Agent Record

### Implementation Notes
- Migration 126: Dùng `argon2-cffi` (`from argon2 import PasswordHasher`) để hash password. Không dùng `bcrypt` vì fastapi-users mặc định dùng argon2 với cấu hình chuẩn.
- Migration 126: Không có cột `created_at`/`updated_at` trên bảng `user` (fastapi-users base không có) — không insert các cột này.
- Migration 126: `searchspaces` cần `citations_enabled=TRUE` vì cột NOT NULL và không có server default.
- Migration 127: Dùng hoàn toàn raw SQL — không dùng `op.create_table`, không dùng `SQLAlchemy.Enum`.
- `SubscriptionRequest` model: `__allow_unmapped__ = True` để tương thích với codebase hiện tại.
- Admin routes: `SubscriptionRequestItem` Pydantic schema thêm field `user_email` (không có trong ORM model, populated thủ công khi query).
- Frontend: dùng `authenticatedFetch` từ `@/lib/auth-utils` và `BACKEND_URL` từ `@/lib/env-config`.

### Completion Notes
✅ AC 1-3: Migration 126 seed admin user — idempotent, argon2 hashed, full setup.
✅ AC 4-7: Admin routes với superuser guard — list/approve/reject subscription requests.
✅ AC 8: Frontend `/admin/subscription-requests` với auth guard và approve/reject UI.

### E2E Test Results (2026-04-15)
- Backend restarted với `STRIPE_SECRET_KEY=""` → admin-approval mode active.
- User `epic5user@example.com` click "Upgrade to Pro" → toast hiển thị đúng.
- Login `admin@surfsense.local` → `/admin/subscription-requests` → thấy pending request của epic5user.
- Click Approve → request biến mất khỏi danh sách.
- Query DB xác nhận: `subscription_status=active`, `plan_id=pro_monthly`, `monthly_token_limit=1000000`, `pages_limit=5000`.

### File List
- `surfsense_backend/alembic/versions/126_seed_admin_user.py` — NEW: admin seed migration (no-op if users exist)
- `surfsense_backend/alembic/versions/127_add_subscription_requests_table.py` — NEW: subscription_requests table (raw SQL)
- `surfsense_backend/app/db.py` — MODIFIED: `SubscriptionRequestStatus` enum, `SubscriptionRequest` model, `subscription_requests` relationship trên User, `values_callable` fix trên tất cả `SubscriptionStatus` enum columns
- `surfsense_backend/app/routes/admin_routes.py` — NEW: GET/approve/reject subscription requests, superuser-only
- `surfsense_backend/app/routes/__init__.py` — MODIFIED: import và include `admin_router`
- `surfsense_web/app/admin/subscription-requests/page.tsx` — NEW: admin UI page

### Change Log
- 2026-04-15: Implement admin seed migration + admin-approval subscription flow.

## Review Findings (2026-04-15)

- [x] [Review][Patch] Hard-coded default admin password should warn operators [126_seed_admin_user.py:53] — **Fixed**: Added runtime print warning when ADMIN_PASSWORD env var is not set
- [x] [Review][Patch] Race condition: concurrent approval lacks row-level lock [admin_routes.py:98] — **Fixed**: Added `.with_for_update()` to SubscriptionRequest and User selects in approve endpoint
- [x] [Review][Patch] N+1 query in list_subscription_requests [admin_routes.py:62] — **Fixed**: Batch-loaded users with `.where(User.id.in_(user_ids))` instead of per-request query
