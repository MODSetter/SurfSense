---
project_name: 'SurfSense'
user_name: 'Luisphan'
date: '2026-04-12'
sections_completed: ['technology_stack']
existing_patterns_found: 10
---

# Project Context for AI Agents

_This file contains critical rules and patterns that AI agents must follow when implementing code in this project. Focus on unobvious details that agents might otherwise miss._

---

## Technology Stack & Versions

- **Backend:** Python >= 3.12, FastAPI (0.115.8), PostgreSQL (`asyncpg`, `pgvector` 0.3.6).
- **Frontend (Web/Extension):** Next.js (16.1.0) App Router (có Turbopack), React (19.2.3), TypeScript (5.8.3), TailwindCSS (4.1.11).
- **ORM & Database State:** Drizzle ORM (0.44.5) cho Frontend, SQLAlchemy quản lý DB queries trên Backend.
- **Data Sync & Client State:** `@rocicorp/zero` (0.26.2), Zustand (5.0.9), TanStack Query (5.90.7).
- **Background Tasks:** Queue và Workers bằng Celery (5.5.3) trên Redis (5.2.1).
- **AI/LLM Ecosystem:** Xử lý luồng bằng LangChain (1.2.13), gọi API bằng LiteLLM (1.83.0), tìm kiếm bằng Elasticsearch (9.1.1).
- **Data Processing/Scraping:** Trích xuất file bằng Unstructured (0.18.31) / Docling (2.15.0), Scraping qua Playwright (1.50.0).

## Language-Specific Rules

### 1. Python (Backend)
- **Type Hinting:** Bắt buộc sử dụng Strict Type Hints cho tất cả các function, endpoint signature và dataclasses/pydantic models. Tận dụng syntax mới của Python 3.12+ (ví dụ: dùng `dict | None` thay vì `Optional[Dict]`).
- **Concurrency (Async/Await):** Bắt buộc dùng `async def` cho các I/O-bound operations (Database calls bằng `asyncpg`, gọi LLM APIs bằng LiteLLM). Code nào CPU-bound hoặc dùng thư viện sync thì đẩy vào background task (Celery) hoặc thread pool.
- **Dependency Injection:** Tận dụng tối đa `fastapi.Depends()` cho các logic như xác thực, cấp phát Database Session, cấu hình.
- **Naming Conventions:**
  - `snake_case` cho variables, functions, module files và methods.
  - `PascalCase` cho Classes và Pydantic Models.
  - `UPPER_SNAKE_CASE` cho constants và environment variables.
- **Docstrings:** Sử dụng chuẩn Google docstrings cho các Public Functions và Classes, mô tả rõ Parameters (`Args:`) và Return values (`Returns:`).
- **Linting & Formatting:** Tuân thủ `ruff` cho cả linting và formatting. Ghi đè các rules theo cấu hình trong `pyproject.toml`.

### 2. TypeScript/JavaScript (Web Frontend & Extension)
- **Strict Typing:** Không sử dụng `any` trừ trường hợp bất khả kháng. Luôn define `interface` hoặc `type` rõ ràng, đặc biệt với các props truyền qua Component hay Data Model lấy từ APIs/DB.
- **Next.js Paradigms:** Mặc định coi mọi component React là **Server Components**. Chỉ thêm `"use client"` trên đầu file khi component đó bắt buộc phải sử dụng Browser API, Client State (Zustand) hoặc Effects (`useEffect`).
- **Naming Conventions:**
  - `camelCase` cho variables, functions, methods, instances, và hooks (ví dụ: `useAuth`).
  - `PascalCase` cho React Components, Types, Interfaces, và Classes.
  - `UPPER_SNAKE_CASE` cho global constant configs.
- **File & Folder naming:** 
  - `kebab-case` cho tên file và thư mục thông thường (VD: `user-profile.tsx`, `components/ui`).
  - Đối với Next.js App Router rules: Tuân thủ cấu trúc framework như `page.tsx`, `layout.tsx`, `route.ts`.
- **Biome Formatting & Linting (`biome.json`):**
  - Thụt lề bằng `tab` (với hiển thị thụt lề bằng 2 spaces).
  - Sử dụng dấu ngoặc kép `"double"` cho chuỗi và thuộc tính JSX.
  - Bắt buộc chấm phẩy ở cuối dòng (`semicolons: "always"`).
  - Bật các cảnh báo kiểm tra Exhaustive Dependencies cho React hooks.
- **Comments:** Prefer các bình luận giải thích *TẠI SAO (Why)* thay vì *LÀM GÌ (What)*. Sử dụng TSDoc syntax (`/** ... */`) cho việc ghi chú function signature, component interface.

## Framework & Library Rules

### 1. Next.js 16 (App Router) & React
- **Data Fetching:** Ưu tiên dùng Server Components (`async/await` trực tiếp trong component) cho dữ liệu tải ở lần đầu tiên (Initial Load) để tối ưu hiển thị.
- **Client Side Fetching & Mutations:** Sử dụng React Query (`TanStack Query`) cho các thao tác gọi API phía client cần quản lý cache, loading, error state.
- **Server Actions:** Sử dụng Server Actions cho các form submission trên Server Components. Với WebApp cần tính realtime/phức tạp, có thể trực tiếp gọi REST APIs của FastAPI (hoặc thông qua `@rocicorp/zero`).

### 2. FastAPI (Backend)
- **Route Organization:** Phải chia nhỏ API endpoints thành các module `APIRouter` (ví dụ trong `app/routers/` hay `app/api/`). Tuyệt đối không nhét chung tất cả logic vào tệp `main.py`.
- **Validation:** Sử dụng triệt để các **Pydantic Models** nhận request object để tự động validate input.
- **Error Handling:** Nếu có lỗi, bắt buộc trả về bằng lệnh raise `HTTPException(status_code=..., detail=...)`. Không bắt lỗi rồi return thành công (HTTP 200) kèm thêm key `"error": true`.

### 3. Database & Real-Time Sync
- **Backend Migrations:** Mọi sự thay đổi về Cấu trúc bảng Database phải thông qua công cụ Migration Engine `Alembic` (cho SQLAlchemy). Không chạy lệnh `ALTER TABLE` trực tiếp.
- **Local-First Sync:** Các state/dữ liệu realtime trên giao diện cần tận dụng `@rocicorp/zero`. Khi làm việc với Zero Database, hãy tuân theo schema định nghĩa sẵn dành riêng cho Zero Client.
- **Client State (Theo mức độ):** 
  - *Server State (Dữ liệu từ API):* Quản lý bởi `TanStack Query` hoặc `@rocicorp/zero`.
  - *Global UI State (VD: Theme, Tooltip, Panel mở rông):* Quản lý qua `Zustand` hoặc `Jotai`.
  - *Local Component State:* Sử dụng `useState`.

### 4. Styling (TailwindCSS 4)
- **Convention:** Tuân thủ Utility-First CSS. Không viết custom CSS class trong file `index.css` trừ phi xử lý animation phức tạp hoặc theme variables.
- **Responsive Design:** Thiết kế theo luồng Mobile-First. Class mặc định dùng cho màn hình di động, dùng tiếp các prefix `sm:`, `md:`, `lg:` để build giao diện cho PC / Tablet.

## Critical Implementation Rules

## Testing Rules

### 1. Backend Testing (Python/FastAPI)
- **Framework:** Sử dụng `pytest` làm test runner chính cho cả Unit Tests và Integration Tests.
- **Coverage:** Bắt buộc phải có test bao phủ các API Endpoints (sử dụng `TestClient`) và các Core Services quan trọng (VD: RAG Pipeline, Sync logic).
- **Fixtures & Mocking:** 
  - Khai thác `pytest.fixture` để chia sẻ database sessions, settings hoặc authentication override.
  - Sử dụng `unittest.mock` (hoặc `pytest-mock`) thay thế các external LLM Services, third-party APIs nhằm đảm bảo test chạy độc lập, offline và nhanh chóng.

### 2. Frontend Testing (Next.js/React)
- **Component Tests:** Áp dụng `Vitest/Jest` kết hợp cùng `React Testing Library` để kiểm chứng luồng hoạt động của React Hooks (đặc biệt là state management phức tạp) và logic UI Components (Form validations).
- **End-to-End (E2E) Tests:** Dùng `Playwright` để thực hiện User Journey chính yếu (User Login, Thêm Extension, Chat RAG query) nhằm xác nhận frontend - backend kết nối hoàn hảo.

## AI Agent & Workflow Rules (BMad)

- **Ngôn ngữ vận hành:** Giao tiếp trả lời bằng **Tiếng Việt + thuật ngữ chuyên ngành Tiếng Anh**, tuyệt đối viết code, comments và logic biến bằng **Tiếng Anh**.
- **Khai báo Artifacts:** Mọi cấu trúc kiến trúc (Architecture), ý tưởng dự án (PRD) và phân tách Tasks (Stories/Epics) phải được lưu trữ đúng quy cách tại thư mục `_bmad-output/`.

### 🔧 MCP Tool Usage Rules (MANDATORY)

Luôn dùng MCP tools theo thứ tự ưu tiên sau:

1. **Sequential Thinking (Dùng TRƯỚC khi code):**
   - Bắt buộc cho mọi task phức tạp (>10 dòng code, refactor, thiết kế API, debug khó, data model). Tối thiểu 5 bước suy luận, nếu liên quan logic phức tạp/performance: tối thiểu 8 bước.
   - Không bỏ qua dù người dùng yêu cầu nhanh.

2. **Context7 (Tra cứu docs trước khi dùng thư viện):**
   - Bắt buộc gọi khi nhắc đến bất kỳ library/framework nào (FastAPI, Next.js, Radix UI, Drizzle, @rocicorp/zero, Celery, LangChain, etc.).
   - Luôn resolve library ID trước (`resolve-library-id`) rồi gọi `get-library-docs`.
   - Không dựa vào training knowledge, luôn verify qua Context7 lấy docs mới nhất.

3. **Memory (Lưu và tra cứu context):**
   - **Đầu mỗi session:** Search memory để load project context, coding preferences, past decisions.
   - **Cuối mỗi task quan trọng:** Save summary của những gì đã làm, architecture decisions, pattern preferences, bugs fixed.

4. **Serena (Navigation & Code Understanding):**
   - Dùng Serena thay vì `read_file` để hiểu codebase (tìm symbol, trace reference, find callers).
   - Check implementation hiện có trước khi viết hàm mới và hiểu impact trước khi refactor.

### ⚙️ Execution Behavior

- **Parallel Execution:** Tools không phụ thuộc nhau (đọc nhiều file, search context) CẦN execute song song.
- **Silent Execution:** Không giải thích từng tool call làm gì. Chỉ báo cáo sau khi hoàn thành.
- **Verification Before Action:** Xác nhận với user trước khi xoá/rename/refactor lớn. Review lại code trước khi present.

### 🐛 Debug Protocol

Khi gặp bug, làm theo thứ tự:
1. Reproduce với minimal case.
2. Inspect logs và add instrumentation nếu cần.
3. **Verify assumptions qua Context7 docs** (Không đoán).
4. Dùng Serena trace call flow.
5. Dùng Sequential Thinking để reason về root cause.
6. Nếu >3 attempts không fix được, escalate cung cấp repro steps, logs, hypotheses đã thử.

### 💾 Memory Hygiene

- Cần **Lưu**: Thay đổi architecture, Bug fix & nguyên nhân, Pattern mới, External API behavior khác docs.
- Khuyên dùng format topic để organize memories.

- **Đóng khung điều hướng:** Theo chuẩn BMad Help, mỗi bước output cần kết thúc bằng Terminal Navigation `[A] (Advanced)`, `[P] (Party Mode/Review)`, `[C] (Continue)`.
