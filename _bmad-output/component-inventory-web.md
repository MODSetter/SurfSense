# Kho Components Web (Component Inventory)

Tài liệu này liệt kê các nhóm components UI chính được sử dụng trong `surfsense_web`.

## 1. UI Primitives (`components/ui`)
Dựa trên **Shadcn UI** và **Radix Primitives**. Các thành phần cơ bản này đảm bảo tính nhất quán về thiết kế và khả năng tiếp cận (accessibility).

- **Core**: `Button`, `Input`, `Select`, `Checkbox`, `Switch`.
- **Feedback**: `Toast` (thông báo), `Alert`, `Progress`, `Skeleton` (loading state).
- **Overlay**: `Dialog` (Modal), `Sheet` (Sidebar Drawer), `Popover`, `Tooltip`.
- **Layout**: `Card`, `Separator`, `ScrollArea`, `Resizable` (chia đôi màn hình).

## 2. Layout Components (`components/layout`)
Các thành phần cấu trúc dùng chung cho các trang.

- **`Sidebar`**: Menu điều hướng chính bên trái (collapsible).
- **`Header`**: Thanh trên cùng chứa User Menu, Theme Toggle, Breadcrumbs.
- **`UserNav`**: Dropdown menu tài khoản người dùng.
- **`ThemeToggle`**: Chuyển đổi Dark/Light mode.

## 3. Assistant UI (`components/assistant-ui`)
Các components chuyên biệt cho trải nghiệm AI Chat.

- **`ChatThread`**: Container chính quản lý danh sách tin nhắn.
- **`Composer`**: Khung nhập liệu thông minh (hỗ trợ slash commands, file attachment).
- **`MessageList`**: Hiển thị tin nhắn cuộn (scrollable).
- **`MessageBubble`**: Hiển thị nội dung tin nhắn (User/AI).
    - Hỗ trợ Markdown rendering.
    - Hỗ trợ hiển thị Code Block với syntax highlighting.
- **`ThreadHistory`**: Sidebar danh sách các cuộc hội thoại cũ.
- **`ToolResult`**: Hiển thị kết quả trả về từ tool (VD: Card thông tin thời tiết).

## 4. Feature Components
Các components đặc thù cho nghiệp vụ SurfSense.

- **`DocumentCard`**: Hiển thị tóm tắt tài liệu trong danh sách tìm kiếm.
- **`ConnectorGrid`**: Lưới các icon ứng dụng để user kết nối (Gmail, Slack...).
- **`SearchFilters`**: Bộ lọc nâng cao cho tìm kiếm (theo ngày, loại file, nguồn).
