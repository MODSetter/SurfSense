# SurfSense Data Models

## Tổng quan
SurfSense xử lý hệ thống dữ liệu vô cùng phức tạp với nhiều nguồn Integration (Slack, Discord, Confluence...) kết nối với LLM RAG System. Hệ thống Models dưới đây được định nghĩa bằng SQLAlchemy tại `surfsense_backend/app/db.py` và có ánh xạ Typescript bên `surfsense_web/db/`.

## 1. Phân Hệ Core Documents & RAG (Retrieval-Augmented Generation)

Đây là trung tâm lưu trữ khối lượng dữ liệu chính của AI.
- **`Document` / `DocumentVersion`**: Lưu trữ Metadata của các tập tin tải lên nội bộ hoặc import từ Internet.
- **`Chunk`**: Phân mảnh văn bản (Splitted text) sinh ra từ `Document` đi kèm với Vector Embeddings (`pgvector`). Dùng cho Vector Search khi RAG.
- **`SurfsenseDocsDocument` / `SurfsenseDocsChunk`**: Bộ models riêng quản lý tài liệu nội bộ / hệ thống hướng dẫn của SurfSense.

## 2. Phân Hệ Search Spaces & Connectors

Để tách biệt quyền và phân mảnh RAG theo Workspaces hoặc Project.
- **`SearchSpace`**: Định nghĩa một vùng không gian RAG cô lập cho một dự án.
- **`SearchSourceConnector`**: Dùng lưu trữ Credentials và State đồng bộ với các nền tảng bên thứ ba (Slack, Notion, Jira...). Dữ liệu kéo về từ con này sẽ nằm trong `SearchSpace`.
- **RBAC (Role-Based Access Control)**: Được quản lý thông qua `SearchSpaceRole`, `SearchSpaceMembership` và `SearchSpaceInvite`.

## 3. Phân Hệ Chats & Collaboration

Quản lý tương tác trực tiếp với Agent và Multi-user Chat.
- **`NewChatThread` / `NewChatMessage`**: Lịch sử hội thoại cốt lõi. Chứa Role của người gửi (User/Assistant/System).
- **`PublicChatSnapshot`**: Lưu trữ các luồng chat publish ra ngoài hệ thống (public sharing).
- **`ChatComment` / `ChatCommentMention`**: Tính năng bình luận nhóm trên một đoạn trả lời của LLM.
- **`ChatSessionState`**: Quản lý biến ngữ cảnh, bộ nhớ session của AI.

## 4. Phân Hệ AI Configurations

Cấu hình cho các Nodes Agent xử lý.
- **`NewLLMConfig` / `Prompt`**: Cấu hình Provider (OpenAI/Anthropic/Gemini) và System Prompts (độ dài tokens, temp...).
- **`ImageGenerationConfig` / `ImageGeneration`**: Quản lý lịch sử và API sinh ảnh do Agent tạo.
- **`Podcast` / `VideoPresentation`**: Các dạng Outputs tổng hợp xuất bản từ văn bản bằng Voice / Video AI.

## 5. Tổ Chức & Telemetry
- **`Folder`**: Hệ thống tổ chức cây Chat / Document.
- **`Notification`**: Thông báo realtime push qua Zero.
- **`Log`**: Hệ thống Telemetry, Log usage cho API Calls của Agent.

---
_Lưu ý: Do Zero Framework yêu cầu, các Primary Keys lưu trữ thường theo chuẩn chuỗi UUIDv4 string, tích hợp 2 chiều Pydantic (Backend) và Drizzle (Frontend)._
