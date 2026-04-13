# Component Inventory (Giao Diện)

## Tổng quan
SurfSense Frontend sử dụng hệ thống Component quy mô lớn (hơn 200 components) đặt tại `surfsense_web/components/`. 
Hệ thống tuân thủ thiết kế phân rã (Atomic/Feature-based) để tái sử dụng.

## Mục Lục Các Trụ Cột Thành Phần (Major Folders)

### 1. `ui/` - Components Dùng Chung (Atoms & Molecules)
Bao gồm toàn bộ nền tảng Shadcn (Button, Dialog, Dropdown, Table, Input, Accordion...). Đây là các component độc lập không chứa Business Logic, tuỳ chỉnh styles trực tiếp qua Tailwind.

### 2. `chat-comments/`, `public-chat/`, `new-chat/` - Cụm Hội Thoại
Chịu trách nhiệm render View của AI Chat.
- Hỗ trợ Markdown rendering (`markdown-viewer.tsx`).
- Rendering Metadata nội bộ do AI suy luận ra (`json-metadata-viewer.tsx`).
- Các UI liên quan đến Public Sharing và Reply Comment trên từng node hội thoại.

### 3. `connectors/`, `sources/` - Cụm Integrations
- UI dạng Form và Dialog để thêm kết nối bên thứ 3 (Slack, Docs, Airtable...).
- Quản lý trạng thái Sync / Load Error.

### 4. `documents/`, `editor/`, `editor-panel/` - Cụm Quản Lý Tri Thức
- Preview tài liệu nội bộ / PDF / Docs.
- Bảng hiển thị thông tin (`document-viewer.tsx`).
- Soạn thảo và tinh chỉnh tài liệu với Editor đi kèm.

### 5. `dashboard/`, `settings/`, `pricing/`, `auth/` - Cụm Tài Khoản & Ứng Dụng
- Các thiết lập Profile User, Tokens, RBAC, Billing UI (`pricing.tsx`).
- Authentication UIs (Login screen, Invite dialog, Onboarding flow).

### 6. Cụm AI & Tools Đặc Biệt
- `tool-ui/`: Các UI tương tác với công cụ do Agent gọi ra (Ví dụ: Công cụ lấy thời tiết, vẽ biểu đồ...).
- `prompt-kit/`: UI thiết lập thư viện câu lệnh cá nhân hóa.
- `assistant-ui/`: Khung bọc giao diện LLM Assistant (LangChain/Vercel AI SDK integration).
- `inference-params-editor.tsx`: Bảng cấu hình AI Models (Temperature, Top K, Provider switch).

---
*Ghi chú: Components thường xuyên kết hợp Zustand (`store/`) để lấy Global State. Hạn chế sử dụng Context API tránh re-render domino.*
