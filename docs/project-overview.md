# SurfSense Project Overview

## Mục Đích Dự Án
SurfSense là một hệ thống đa nền tảng (Web, Desktop, Extension) cho phép thu thập, lưu trữ, lập chỉ mục (indexing) và phân tích dữ liệu qua AI. Hệ thống sử dụng phương pháp **local-first** sync (ưu tiên đồng bộ local realtime qua Zero) để mang lại trải nghiệm người dùng liền mạch và không có độ trễ. 

## Cấp Độ Kiến Trúc (Executive Summary)
Dự án được xây dựng dưới dạng **Monorepo** chia làm 4 bộ phận độc lập có tính kết nối cao qua API và Websocket (Sync):
1. **Frontend App (`surfsense_web`)**: Dashboard và giao diện end-user.
2. **Backend Service (`surfsense_backend`)**: Nơi xử lý dữ liệu nặng (Extract-Transform-Load, LLM processing, Background Tasks, Embedding).
3. **Browser Extension (`surfsense_browser_extension`)**: Tool capture dữ liệu từ trình duyệt người dùng.
4. **Desktop App (`surfsense_desktop`)**: Native client hỗ trợ sâu các tính năng OS-level.

## Tiêu Chuẩn Công Nghệ Cốt Lõi
| Hạng Mục | Công Nghệ | Vai trò / Justification |
| ---------|----------| ----------------------- |
| **Frontend Framework** | Next.js 16 (App Router) | Hỗ trợ Server Components, SEO & routing tối giản. Mặc định SSR. |
| **Frontend State/Sync** | @rocicorp/zero, Zustand | Zero cho đồng bộ realtime state từ CSDL đến client. |
| **UI Components** | React 19, TailwindCSS 4, Shadcn | Thiết kế tái sử dụng cao, tối ưu performance. |
| **Backend API** | FastAPI (Python 3.12) | API xử lý tốc độ cao, type-hinting tự động generate Swagger/OpenAPI. |
| **Database/ORM** | PostgreSQL, pgvector, SQLAlchemy, Drizzle | Vector database phục vụ embedding/LLM. Quản lý schema 2 chiều Python/TS. |
| **Async Tasks** | Celery + Redis | Đảm nhận các heavy background jobs: AI processing, indexing files. |
| **RAG & Agents** | LangChain, LangGraph | Quản lý graph agent logic, query LLM API. |

## Thư Mục Mã Nguồn Chính
Kiến trúc mã nguồn được phân bổ như sau:
```text
SurfSense/
├── docs/                        # Tài liệu dự án (kết quả sau scan BMAD)
├── docker/                      # Cấu hình container & infra (Compose)
├── surfsense_web/               # Giao diện Next.js
│   ├── app/                     # Page routers
│   ├── components/              # ~200 ui components
│   └── public/                  # Static assets
├── surfsense_backend/           # Server APIs
│   ├── app/
│   │   ├── api/routes           # Định tuyến API
│   │   ├── schemas/             # Pydantic validation
│   │   ├── services/            # Core business logic / DI
│   │   └── tasks/               # Background task workers
│   └── tests/                   # Pytest suites
└── ...                          # Extension & Desktop folders
```
---
*Được khởi tạo bởi Agent theo tiêu chuẩn BMAD (Full-Scan Workflow).*
