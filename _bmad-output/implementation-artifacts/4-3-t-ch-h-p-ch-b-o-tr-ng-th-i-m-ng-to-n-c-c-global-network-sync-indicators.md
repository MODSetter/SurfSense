# Story 4.3: Tích hợp Chỉ báo Trạng thái Mạng Toàn Cục (Global Network & Sync Indicators)

**Status:** done

## PRD Requirements
As a Người dùng,
I want thấy một icon nhỏ hoặc dải màu trực quan cho biết App đang Online, Offline, hay Syncing,
So that tôi chủ động biết ứng dụng có đang "sống" và "khớp nối" dữ liệu với đám mây hay không (FR11).
**Acceptance Criteria:**
**Given** app đang khởi chạy bình thường
**When** trạng thái kết nối mạng của Zero Client hoặc Browser thay đổi
**Then** Header hoặc góc dưới màn hình cập nhật icon (Xanh: Connected / Vàng: Syncing / Đỏ/Xám: Offline)
**And** thiết kế phải hòa hợp với bộ màu ZinC/Slate đã chọn, tuyệt đối không dùng thông báo (alert) nhảy ập vào mặt người dùng.
Hệ thống biến từ một ứng dụng tĩnh thành một nền tảng SaaS thương mại thông qua tích hợp thanh toán Stripe. Người dùng có thể xem bảng giá, chọn gói cước phù hợp, thanh toán an toàn và hệ thống tự động kiểm soát quota sử dụng dựa trên gói đăng ký, đảm bảo mô hình kinh doanh bền vững.
**FRs covered:** FR15, FR16, FR17

## Architecture Compliance & As-Built Context
> *This section is automatically generated to map implemented components to this story's requirements.*

This story has been successfully implemented in the brownfield codebase. The following key files contain the core logic for this feature:

- `surfsense_backend/app/schemas/stripe.py`
- `surfsense_backend/app/services/linear/kb_sync_service.py`
- `surfsense_backend/app/services/page_limit_service.py`
- `surfsense_backend/app/services/google_calendar/kb_sync_service.py`
- `surfsense_backend/app/routes/stripe_routes.py`
- `surfsense_backend/app/services/google_drive/kb_sync_service.py`
- `surfsense_backend/app/services/gmail/kb_sync_service.py`
- `surfsense_backend/app/services/onedrive/kb_sync_service.py`

## Implementation Notes
- **UI/UX**: Needs to follow `surfsense_web` React/Tailwind standards.
- **Backend**: Needs to follow `surfsense_backend` FastAPI standards.
