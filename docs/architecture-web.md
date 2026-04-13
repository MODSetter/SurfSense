# Kiến Trúc Hệ Thống: Frontend (`surfsense_web`)

## 1. Tổng Quan
Frontend (Web Application) cung cấp giao diện tương tác chính cho người dùng: bao gồm Dashboard, Chat Interface, Trình quản lý tài liệu, và Cấu hình kết nối. Ứng dụng theo hơi hướng **Local-First**, nghĩa là tải nhanh và phản hồi tức thì nhờ đồng bộ trạng thái ngầm.

## 2. Công Nghệ Cốt Lõi
- **Framework Chính**: Next.js 16 (App Router)
- **View Layer**: React 19
- **Styling**: TailwindCSS 4, Radix UI primitives, Lucide Icons
- **Quản lý State & Đồng Bộ**: `@rocicorp/zero` (cho Realtime DB Sync), Zustand (Global UI State), TanStack Query (Server State fetch)
- **Database Access / Schema**: Drizzle ORM

## 3. Cấu Trúc Mã Nguồn (Directory Structure)
```text
surfsense_web/
├── app/                  # Next.js App Router
│   ├── (home)/           # Landing page / Trang chủ
│   ├── api/              # Route handlers / API routes của NextJS (Proxy/Webhooks)
│   ├── auth/             # Luồng xác thực đăng nhập
│   ├── dashboard/        # Bảng điều khiển quản trị và sử dụng chính
│   ├── docs/             # Trang tài liệu dành cho end-user (Tích hợp Fumadocs)
│   ├── layout.tsx        # Global Layout / App Provider
│   └── globals.css       # Global styles (Tailwind directives)
├── components/           # Hơn 200 UI components tái sử dụng
├── hooks/                # Custom React Hooks
├── lib/                  # Tiện ích chung, utils cho UI
└── store/                # Nơi định nghĩa Zustand store
```

## 4. Patterns Hiện Có
- **Server Components Mặc Định**: Giao diện cố định và data fetching tĩnh đều đặt ở Server Components. Các Hook/State mới chuyển qua Client Component (`"use client"`).
- **Zero Local-First Sync**: Thay vì fetch API liên tục để xem file hay chat log, frontend đọc trực tiếp từ Local Zero State, trong khi Zero Client ngầm đồng bộ với Backend Data trên Postgres. Đảm bảo trải nghiệm tức thì (Optimistic Updates).
- **Zustand cho Component State Liên Kết**: Dùng nhiều cho các side-panels, tooltips hay modal triggers mà không cần truyền Props quá rườm rà.

## 5. UI/UX Design System
Hệ thống UI được thiết kế riêng với TailwindCSS. Sử dụng phong cách Modern Interface (bo góc mềm, Glassmorphism, Focus ring rõ ràng) giúp ứng dụng thân thiện, sạch sẽ và phù hợp với một công cụ tìm kiếm tri thức AI cá nhân. Dữ liệu theme nằm ở `globals.css` và `tailwind.config.ts` (hoặc chuẩn Tailwind v4).
