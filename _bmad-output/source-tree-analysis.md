# Phân Tích Cây Mã Nguồn

Tài liệu này ánh xạ các thư mục và tệp tin quan trọng trong dự án đa phần (multi-part) SurfSense.

## Sơ Đồ Thư Mục

```
/Users/mac_1/Documents/GitHub/SurfSense/
├── docs/                                   # Tài liệu cấp dự án
│   └── chinese-llm-setup.md                # Hướng dẫn cài đặt chuyên biệt
├── docker-compose.yml                      # File điều phối chính
├── .env.example                            # Mẫu biến môi trường toàn cục (Global environment)
│
├── surfsense_backend/                      # [PART: Backend]
│   ├── app/
│   │   ├── api/                            # Các tiện ích API
│   │   ├── config/                         # Cấu hình & Cài đặt
│   │   ├── connectors/                     # Connectors ứng dụng ngoài (Slack, Jira...)
│   │   ├── prompts/                        # System Prompts cho Agents
│   │   ├── retriever/                      # Logic RAG & Search
│   │   ├── routes/                         # API Route Controllers (Endpoints)
│   │   ├── schemas/                        # Pydantic Data Models
│   │   ├── services/                       # Business Logic Services
│   │   ├── tasks/                          # Celery Background Tasks
│   │   ├── app.py                          # Điểm nhập (Entry Point) của FastAPI
│   │   ├── celery_app.py                   # Điểm nhập của Worker
│   │   └── db.py                           # Database ORM (SQLAlchemy) & Models
│   ├── alembic/                            # Database Migrations
│   ├── pyproject.toml                      # Dependencies (kiểu uv/poetry)
│   └── Dockerfile                          # Cấu hình container Backend
│
├── surfsense_web/                          # [PART: Web]
│   ├── app/                                # Next.js App Router (Pages & API)
│   │   ├── (home)/                         # Marketing/Landing Pages
│   │   ├── dashboard/                      # Ứng dụng người dùng (đã xác thực)
│   │   ├── api/                            # Next.js API Routes (BFF/Proxy)
│   │   └── docs/                           # Documentation Routes
│   ├── components/                         # React Components
│   │   ├── ui/                             # Base UI Kit (giống Shadcn)
│   │   ├── layout/                         # Components cấu trúc (Structural)
│   │   └── assistant-ui/                   # Components giao diện Chat/AI
│   ├── lib/                                # Utilities & Logic chia sẻ
│   │   ├── apis/                           # Client-side API Wrappers
│   │   └── electric/                       # Cấu hình ElectricSQL Sync
│   ├── content/                            # Nội dung MDX (Docs)
│   ├── contracts/                          # Shared Types/Contracts
│   ├── public/                             # Static Assets
│   ├── package.json                        # Dependencies (pnpm)
│   └── next.config.ts                      # Cấu hình Next.js
│
└── surfsense_browser_extension/            # [PART: Extension]
    ├── background/                         # Service Workers
    │   └── index.ts                        # Điểm nhập Background
    ├── routes/                             # Extension UI Routes
    ├── assets/                             # Icons & Static Files
    ├── popup.tsx                           # Điểm nhập Popup (React)
    ├── manifest.json                       # Extension Manifest (tạo bởi Plasmo)
    └── package.json                        # Dependencies
```

## Phân Tích Các Thư Mục Quan Trọng

### Backend (`surfsense_backend`)
- **`app/routes/`**: Chứa tất cả REST API endpoints. Mỗi file thường tương ứng với một miền tính năng (ví dụ: `discord_add_connector_route.py`).
- **`app/connectors/`**: Logic tích hợp cốt lõi cho hơn 30 dịch vụ bên ngoài. Đây là nơi quá trình data ingestion diễn ra.
- **`app/db.py`**: Hệ thống thần kinh trung ương để lưu trữ dữ liệu. Định nghĩa tất cả các SQLAlchemy models và kết nối database.

### Web (`surfsense_web`)
- **`app/dashboard/`**: Giao diện ứng dụng chính mà người dùng tương tác. Được bảo vệ bởi xác thực (auth).
- **`components/assistant-ui/`**: Các components chuyên biệt cho giao diện AI chat, xử lý streaming, tool calls, và lịch sử tin nhắn.
- **`lib/apis/`**: Lớp client được định kiểu (typed client layer) giao tiếp với Backend.

### Extension (`surfsense_browser_extension`)
- **`background/`**: Xử lý logic bền vững (persistent logic) như thu thập lịch sử và giám sát tab ngay cả khi popup đã đóng.
