# Mô Hình Dữ Liệu (Backend)

Tài liệu này mô tả schema cơ sở dữ liệu Postgres, được quản lý bởi SQLAlchemy và Alembic.

## Các Thực Thể Chính (Core Entities)

### `User`
Đại diện cho người dùng hệ thống.
- **`id`**: `Integer` (Primary Key)
- **`email`**: `String` (Unique)
- **`hashed_password`**: `String`
- **`is_active`**: `Boolean`
- **`created_at`**: `DateTime`

### `Usage`
Theo dõi hạn ngạch sử dụng (quota) của người dùng.
- **`id`**: `Integer`
- **`user_id`**: `ForeignKey -> User`
- **`request_count`**: `Integer` (Số request API đã gọi)
- **`token_consumed`**: `Integer` (Số token LLM đã dùng)

### `Document`
Đơn vị kiến thức cơ bản. Một tài liệu có thể là một file PDF, một trang web, hoặc một ghi chú Notion.
- **`id`**: `Integer`
- **`title`**: `String`
- **`content`**: `Text` (Nội dung thô, nếu có)
- **`url`**: `String` (Nguồn gốc)
- **`source_type`**: `Enum` (PDF, WEB, NOTION, SLACK...)
- **`owner_id`**: `ForeignKey -> User`
- **`embedding_status`**: `Enum` (PENDING, INDEXED, FAILED)

### `Chunk`
Phần nhỏ của tài liệu dùng cho Vector Search.
- **`id`**: `Integer`
- **`document_id`**: `ForeignKey -> Document`
- **`content`**: `Text` (Nội dung của đoạn chunk)
- **`embedding`**: `Vector(1536)` (Vector đại diện, dùng cho pgvector)
- **`metadata`**: `JSONB` (Thông tin bổ sung)

### `ChatThread`
Đại diện cho một cuộc hội thoại.
- **`id`**: `Integer`
- **`user_id`**: `ForeignKey -> User`
- **`title`**: `String`
- **`created_at`**: `DateTime`

### `ChatMessage`
Một tin nhắn trong cuộc hội thoại.
- **`id`**: `Integer`
- **`thread_id`**: `ForeignKey -> ChatThread`
- **`role`**: `Enum` (USER, ASSISTANT, SYSTEM)
- **`content`**: `Text`
- **`tool_calls`**: `JSONB` (Lưu trữ các function calls nếu có)

### `ConnectorCredential`
Lưu trữ token xác thực cho các ứng dụng bên ngoài.
- **`id`**: `Integer`
- **`user_id`**: `ForeignKey -> User`
- **`connector_type`**: `String` (ví dụ: "google_drive")
- **`encrypted_token`**: `String` (Token đã mã hóa)
- **`refresh_token`**: `String`

## Mối Quan Hệ ERD (Tóm tắt)
- `User` **1 -- n** `Document`
- `Document` **1 -- n** `Chunk`
- `User` **1 -- n** `ChatThread`
- `ChatThread` **1 -- n** `ChatMessage`
- `User` **1 -- 1** `Usage`
