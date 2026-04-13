# Hợp Đồng API (Backend)

Tài liệu này tóm tắt các REST API endpoints chính được phơi bày bởi Backend FastAPI.

*Lưu ý: Tất cả các protected endpoints đều yêu cầu Header Authorization: `Bearer <token>`.*

## Quản Lý Tài Liệu (Documents)

| Method | Endpoint | Mô tả | Quyền Truy Cập |
|--------|----------|-------|----------------|
| `POST` | `/api/v1/documents/` | Tạo hoặc upload tài liệu mới. | `User` |
| `GET` | `/api/v1/documents/` | Liệt kê tài liệu (có phân trang & lọc). | `User` |
| `GET` | `/api/v1/documents/{doc_id}` | Lấy chi tiết một tài liệu. | `User` (Owner) |
| `PATCH` | `/api/v1/documents/{doc_id}` | Cập nhật metadata tài liệu. | `User` (Owner) |
| `DELETE`| `/api/v1/documents/{doc_id}` | Xóa tài liệu (Soft or Hard delete). | `User` (Owner) |
| `POST` | `/api/v1/documents/search` | Tìm kiếm ngữ nghĩa (Semantic search) trên tài liệu. | `User` |

## Chat & AI

| Method | Endpoint | Mô tả |
|--------|----------|-------|
| `POST` | `/api/v1/chat/threads` | Tạo phiên chat mới. |
| `GET` | `/api/v1/chat/threads` | Lấy lịch sử các phiên chat. |
| `POST` | `/api/v1/chat/message` | Gửi tin nhắn tới Agent (Streaming response). |
| `GET` | `/api/v1/chat/{thread_id}/history` | Lấy lịch sử tin nhắn của một thread. |

## Connectors (Tích Hợp)

| Method | Endpoint | Mô tả |
|--------|----------|-------|
| `GET` | `/api/v1/connectors/available` | Danh sách các connectors được hỗ trợ. |
| `POST` | `/api/v1/connectors/{type}/auth` | Bắt đầu quy trình OAuth cho connector. |
| `POST` | `/api/v1/connectors/{type}/sync` | Kích hoạt đồng bộ dữ liệu thủ công. |

## Tiện Ích Trình Duyệt (Extension)

| Method | Endpoint | Mô tả |
|--------|----------|-------|
| `POST` | `/api/v1/extension/ingest` | Nhận dữ liệu trang web từ extension. |
| `POST` | `/api/v1/extension/context` | Kiểm tra ngữ cảnh hiện tại (User có đang track trang này không?). |
