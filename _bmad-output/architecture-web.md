# Kiến Trúc Web Frontend

## Tổng Quan
Ứng dụng Web SurfSense được xây dựng trên **Next.js 16**, tận dụng các tính năng mới nhất như **React Server Components (RSC)** và **Server Actions**. Nó mang lại trải nghiệm người dùng (UX) hiện đại, nhanh chóng và tương tác cao, đóng vai trò là giao diện chính để người dùng quản lý kiến thức và tương tác với AI Agents.

## Stack Công Nghệ (Tech Stack)

| Hạng Mục | Công Nghệ | Ghi Chú |
|----------|-----------|---------|
| **Core** | Next.js 16 (Turbopack) | App Router, Server Actions |
| **Language** | TypeScript | Type safety toàn diện |
| **UI Library** | React 19 | Hooks mới (useOptimistic, useFormStatus) |
| **Styling** | Tailwind CSS v4 | Utility-first CSS |
| **State/Sync** | ElectricSQL | Đồng bộ dữ liệu local-first / real-time |
| **ORM Client** | Drizzle ORM | Truy vấn database an toàn (Type-safe) |
| **Components** | Shadcn UI + Assistant UI | Reusable components & AI Chat UI |

## Mô Hình Kiến Trúc (Architecture Patterns)

### 1. App Router & Server Components
- **Mặc định là Server Component**: Hầu hết các components (Layout, Page) được render trên server để tối ưu SEO và tải trang ban đầu.
- **Client Components**: Chỉ sử dụng (`"use client"`) cho các phần tương tác (interactive) như form, button, hoặc real-time chat.
- **Data Fetching**: Fetch dữ liệu trực tiếp trong Server Components (không cần useEffect cho initial data).

### 2. Server Actions cho Mutations
- Thay vì tạo API routes riêng biệt cho mọi hành động (submit form, like bài viết), SurfSense sử dụng **Server Actions**.
- Gọi hàm backend trực tiếp từ frontend code.
- Xử lý xác thực và validation ngay trong action.

### 3. Local-First Sync với ElectricSQL
- **Vấn đề**: Độ trễ mạng khi thao tác nhiều dữ liệu.
- **Giải pháp**: ElectricSQL đồng bộ một phần database Postgres xuống client (trong trình duyệt).
- **Lợi ích**: UI phản hồi tức thì (Optimistic UI), hoạt động offline-first, và tự động đồng bộ khi có mạng.

### 4. Kiến Trúc AI Chat
- **Streaming**: Sử dụng `AI SDK` (hoặc tương đương) để stream phản hồi từ Backend LangGraph.
- **Generative UI**: Render các components React ngay trong luồng chat (ví dụ: hiển thị một bảng dữ liệu hoặc biểu đồ thay vì chỉ text).
- **Tool Call Handling**: Client hiển thị trạng thái "đang xử lý" khi Agent gọi tool kiểm tra thời tiết hoặc tìm kiếm document.

## Cấu Trúc Thư Mục Chính (`surfsense_web/app`)

- `(home)/`: Landing page, Marketing sites (Public).
- `dashboard/`: Không gian làm việc chính của user (Protected).
    - `layout.tsx`: Sidebar, Header, Auth Check.
    - `page.tsx`: Dashboard tổng quan.
    - `chat/[id]/page.tsx`: Giao diện chat chi tiết.
    - `search/page.tsx`: Giao diện tìm kiếm nâng cao.
- `api/`: Route Handlers cho các trường hợp đặc biệt (như Webhook từ bên thứ 3).
