# SurfSense API Contracts

## Tổng quan
SurfSense Backend cấu trúc hệ thống APIs thành các Routers chuẩn RESTful (thư mục `api/routes`). Toàn bộ API đều trả về type hints giúp FastAPI tự động serialize Pydantic ra Swagger UI và các Frontend Generator có thể tiêu thụ.

## 1. Nhóm API Quản Trị Hệ Thống / Tài Khoản
- **`auth_routes.py`**: Quản lý OAuth/Login, Tokens, Session Refresh.
- **`rbac_routes.py`**: Role-based Access Control API, lấy quyền truy cập Workspace/Search Spaces.
- **`stripe_routes.py`**: Webhooks và API phục vụ payment/subscriptions nếu có.
- **`logs_routes.py`**, **`notifications_routes.py`**: Đẩy Log errors, gửi các Notifications system.

## 2. Nhóm API Core Search & AI
- **`search_spaces_routes.py`**: Tạo, cập nhật, xóa các Knowledge Bases cô lập.
- **`new_chat_routes.py`**, **`public_chat_routes.py`**: Mọi call Stream SSE/WebSocket cho tin nhắn từ AI Agent, cũng như query dữ liệu Chat Threads cũ.
- **`search_source_connectors_routes.py`**: Trung tâm điều hướng cấu hình các External Syncs. Thường làm việc chung với Backend Workers.

## 3. Nhóm Connectors Bên Thứ 3
Các Connectors này định nghĩa quá trình OAuth Consent hoặc Add Webhooks để cào dữ liệu:
- **`google_drive_add_connector_route.py`**
- **`slack_add_connector_route.py`**
- **`notion_add_connector_route.py`**
- **`confluence_add_connector_route.py`**, **`jira_add_connector_route.py`**
- **`discord_add_connector_route.py`**
*(Và khoảng 10 nền tảng khác).*

## 4. Nhóm AI Outputs Đa Phương Tiện
Mở rộng LLM capabilities beyond text:
- **`image_generation_routes.py`**: Sinh hình ảnh từ context.
- **`vision_llm_routes.py`**: Parse hình ảnh thành Text (OCR hoặc Context).
- **`podcasts_routes.py`**: Sinh Audio / Deep Dive từ documents.
- **`video_presentations_routes.py`**: Tạo video tổng hợp.
- **`reports_routes.py`**, **`export_routes.py`**: Chuyển đổi Chat Output thành format Markdown, PDF.

## Quy Chuẩn Tương Tác
- Backend sử dụng chuẩn Pydantic Models (nằm ở `surfsense_backend/app/schemas/`) rải đều qua response `response_model=...`.
- Client gọi thông qua tanstack-query được define trong `surfsense_web/api/`. Riêng đối với dữ liệu Realtime, Client hoàn toàn bypass API POST/GET truyền thống mà dùng `@rocicorp/zero` để mutate trực tiếp vào Schema.
