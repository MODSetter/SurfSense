# Story 3.5: Lựa chọn Mô hình LLM dựa trên Subscription (Model Selection via Quota)

Status: ready-for-dev

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a Người dùng,
I want chọn cấu hình mô hình trí tuệ nhân tạo (VD: Claude 3.5 Sonnet, GPT-4) được cung cấp sẵn mà không cần điền API key cá nhân,
so that tôi có thể dùng trực tiếp và chi phí sử dụng được trừ thẳng vào số Token thuộc gói cước của tôi.

## Acceptance Criteria

1. Hệ thống cung cấp Dropdown chọn `LLM Model` trong giao diện Chat.
2. Tuyệt đối không hiển thị ô nhập "Your API Key" ở Frontend (Xóa bỏ logic Bring-Your-Own-Key cũ nếu có).
3. Hệ thống Backend tính toán chi phí (Token * Đơn giá của Model).
4. Hệ thống kiểm tra Quota hàng tháng của người dùng; nếu vượt quá (Quota Exceeded), trả về lỗi 403/429 báo "Hãy nâng cấp gói".

## Tasks / Subtasks

- [ ] Task 1: Dọn dẹp Kiến trúc Client cũ (Frontend)
  - [ ] Subtask 1.1: Gỡ bỏ flow nhập `api_key` tự do ở giao diện LLM Configs (`surfsense_web/app/dashboard/[search_space_id]/llm-configs`), khoá cứng các tuỳ chọn chọn Provider.
  - [ ] Subtask 1.2: Triển khai Component `ModelSelector` trên UI Chat (hoặc sửa đổi UI chọn LLM Config cũ sang danh sách LLM thương mại).
- [ ] Task 2: Cập nhật Schema & Table Quản lý Quota (Backend - `db.py`)
  - [ ] Subtask 2.1: Bổ sung column `token_balance` (Integer) vào model `User` (hoặc tạo table `UserSubscription`).
  - [ ] Subtask 2.2: Bổ sung ENUM `LLM_MODEL` vào config db.
- [ ] Task 3: Tích hợp logic Trừ Quota vào RAG Engine (Backend - `rag_engine` / `chat_session_api`)
  - [ ] Subtask 3.1: Ở API Endpoint Streaming, kiểm tra `token_balance` trước khi khởi tạo luồng SSE. Nếu <= 0, trả HTTP 402/429.
  - [ ] Subtask 3.2: Dùng `tiktoken` hoặc đếm chữ ước tính số tokens Generate để UPDATE trừ lùi vào Database sau mỗi chu kỳ trả lời xong.
- [ ] Task 4: Hiển thị Banner nâng cấp (Frontend)
  - [ ] Subtask 4.1: Bắt lỗi 402/429 từ SSE, render Alert UI Upgrade.

## Dev Notes

### Relevant Architecture Patterns & Constraints
- **Billing Pivot Constraint:** Đây là cốt lõi của quá trình chuyển đổi sang nền tảng Thương mại (SaaS SaaS Commercialization). CẤM các logic Hardcode API key người dùng truyền vào, tất cả Server Auth phải lấy từ biến môi trường `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`.
- **Concurrency & Database Locks:** Việc trừ Token balance phải chịu sự cạnh tranh cao (ví dụ mở 2 tab chat đồng thời). Yêu cầu cân nhắc dùng `session.execute(update(User).where(...).values(token_balance=User.token_balance - cost))` để tận dụng Database atomic locks (tránh Race conditions).
- **RAG Endpoint:** `Surfsense` stream thông qua giao thức SSE ở `/api/v1/chat/stream`. Hãy thêm interceptor kiểm tra số dư ngay đầu route (Fail-fast).

### Project Structure Notes
- Module thay đổi: 
  - `surfsense_backend/app/db.py`
  - `surfsense_backend/app/routes/chat_routes.py` (hoặc nơi implement SSE)
  - `surfsense_web/src/components/chat/`
- Phải đảm bảo DB schema migration (bằng Alembic) khi có thuộc tính mới `token_balance` ở User. 
- Endpoint `/api/v1/chat/stream` hiện đang phụ thuộc vào `NewLLMConfig`. Cần chỉnh sửa kiến trúc để ánh xạ ID Model do người dùng chọn sang Backend Config cố định của hệ thống.

### References
- [Epic 3 - RAG Engine Requirements]: Epic `3.5`.
- [Constraint from BMad Rule]: "All billing must handle quota limits based on the user's current subscription".

## Dev Agent Record

### Agent Model Used
Antigravity Claude 3.5 Sonnet Engine (Context: 120k)

### File List
- `surfsense_backend/app/db.py`
- `surfsense_backend/app/routes/chat_routes.py`
- `surfsense_web/app/dashboard/[search_space_id]/llm-configs/...`
- `surfsense_web/components/chat/...`
