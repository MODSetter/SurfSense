# Tổng Quan Dự Án SurfSense

## Tóm Tắt Điều Hành
SurfSense là một nền tảng tìm kiếm và quản lý kiến thức toàn diện được hỗ trợ bởi AI. Hệ thống bao gồm một Browser Extension chuyên dụng để thu thập dữ liệu, một Python Backend hiệu năng cao để xử lý AI và RAG (Retrieval-Augmented Generation), và một Web Dashboard hiện đại xây dựng trên Next.js để tương tác người dùng. Hệ thống tận dụng framework DeepAgents và LangGraph cho các quy trình agentic (agentic workflows) tiên tiến.

## Cấu Trúc Dự Án
Dự án được tổ chức dưới dạng kho lưu trữ đa phần (multi-part repository) chứa ba thành phần riêng biệt:

| Thành phần | Thư mục | Loại | Công nghệ chính |
|------------|---------|------|-----------------|
| **Backend** | `surfsense_backend/` | Microservice | Python, FastAPI, LangGraph, DeepAgents, Postgres, Redis |
| **Web Frontend** | `surfsense_web/` | Web App | Next.js 16, React 19, Tailwind v4, Drizzle ORM |
| **Browser Extension** | `surfsense_browser_extension/` | Extension | Plasmo, React 18, Tailwind |

## Loại Kiến Trúc
**Layered Microservice Architecture** (Kiến trúc Microservice phân lớp) kết hợp với **Distributed Client System** (Hệ thống Client phân tán).
- **Data Layer**: Postgres (Vector + Relational)
- **Service Layer**: Python FastAPI với khả năng Agentic
- **Client Layer**: Lai (Web Dashboard + Browser Extension)

## Tính Năng Chính
- **Deep Search**: Pipeline RAG nâng cao để tìm kiếm trên các ứng dụng kết nối (Slack, Notion, v.v.).
- **Agentic AI**: Sử dụng LangGraph/DeepAgents cho các tác vụ suy luận phức tạp, nhiều bước.
- **Data Connectors**: Thư viện kết nối đồ sộ (30+) cho các nền tảng bên ngoài.
- **Sync Engine**: Browser extension thu thập lịch sử/ngữ cảnh để cá nhân hóa tìm kiếm.
- **Local/Cloud Hybrid**: Hỗ trợ Local LLMs và các nhà cung cấp cloud thông qua LiteLLM.

## Điều Hướng Tài Liệu
- [Master Index](./index.md) - **Bắt đầu tại đây**
- [Phân Tích Cây Mã Nguồn](./source-tree-analysis.md)
- [Kiến Trúc Tích Hợp](./integration-architecture.md)

### Tài Liệu Thành Phần Chi Tiết
- **Backend**: [Kiến Trúc](./architecture-backend.md) | [Hợp Đồng API](./api-contracts-backend.md) | [Mô Hình Dữ Liệu](./data-models-backend.md)
- **Web**: [Kiến Trúc](./architecture-web.md) | [Inventory Component](./component-inventory-web.md)
- **Extension**: [Kiến Trúc](./architecture-extension.md)
