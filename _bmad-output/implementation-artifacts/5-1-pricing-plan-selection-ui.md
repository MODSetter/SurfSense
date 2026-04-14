# Story 5.1: Kết nối Pricing UI với Stripe Checkout

Status: ready-for-dev

## Context / Correction Note
> **⚠️ Story gốc bị sai hướng.** Story gốc mô tả tạo mới pricing page với Free/Pro/Team subscription tiers. Thực tế, pricing page **đã tồn tại** với mô hình PAYG (Pay-As-You-Go page packs), không phải subscription. Stripe checkout endpoint cũng đã tồn tại. Task thực tế là **wire up** nút "Get Started" của PAYG tier với endpoint hiện có.

## Story

As a Người dùng đã đăng nhập,
I want bấm "Get Started" trên trang Pricing để mua page packs,
so that tôi có thể tiếp tục upload tài liệu sau khi hết quota.

## Actual Architecture (as-is)

**Đã tồn tại và hoạt động:**
- `surfsense_web/app/(home)/pricing/page.tsx` — pricing page route
- `surfsense_web/components/pricing/pricing-section.tsx` — UI với 3 tiers:
  - **FREE**: 500 pages included, button href="/login"
  - **PAY AS YOU GO**: $1/1,000 pages, button href="/login" ← **cần sửa**
  - **ENTERPRISE**: Contact Sales, button href="/contact"
- `surfsense_backend/app/routes/stripe_routes.py:create_checkout_session` — endpoint `POST /api/v1/stripe/create-checkout-session` đã implement, mode=`payment`, yêu cầu `search_space_id` và `quantity`

**Chưa làm:**
- Nút "Get Started" của PAYG tier chỉ link đến `/login`, chưa gọi Stripe checkout
- Không có flow chọn số lượng page packs (quantity)

## Acceptance Criteria

1. Khi user đã đăng nhập bấm "Get Started" ở PAYG tier, hiện modal/form cho phép chọn số lượng pack (1, 5, 10, etc.).
2. Sau khi confirm, gọi `POST /api/v1/stripe/create-checkout-session` với `quantity` và `search_space_id`, nhận `checkout_url`.
3. Redirect user đến `checkout_url` (Stripe-hosted checkout page).
4. Nếu user chưa đăng nhập, redirect đến `/login` trước (behavior hiện tại giữ nguyên cho FREE tier).

## Tasks / Subtasks

- [ ] Task 1: Cập nhật nút PAYG trong `pricing-section.tsx`
  - [ ] Subtask 1.1: Thay `href="/login"` bằng `onClick` handler. Nếu user chưa authenticated, redirect `/login`. Nếu đã authenticated, mở modal chọn quantity.
  - [ ] Subtask 1.2: Tạo `PurchasePagesModal` component với dropdown/input chọn số pack (1–10), hiển thị tổng tiền (`quantity × $1`).
- [ ] Task 2: Gọi Stripe checkout API
  - [ ] Subtask 2.1: Khi user confirm trong modal, gọi `POST /api/v1/stripe/create-checkout-session` với `{ quantity, search_space_id }`.
  - [ ] Subtask 2.2: Nhận `checkout_url` và redirect bằng `window.location.href = checkout_url`.
- [ ] Task 3: Xử lý return URL sau checkout
  - [ ] Subtask 3.1: Kiểm tra success/cancel URL config hiện tại trong `stripe_routes.py` (`_get_checkout_urls`).
  - [ ] Subtask 3.2: Sau purchase thành công, hiển thị toast "Mua thành công! X pages đã được thêm vào tài khoản."

## Dev Notes

### Stripe Checkout Request Schema (hiện tại)
```python
class CreateCheckoutSessionRequest(BaseModel):
    search_space_id: int
    quantity: int  # số pack, mỗi pack = STRIPE_PAGES_PER_UNIT pages
```

### API Endpoint
```
POST /api/v1/stripe/create-checkout-session
Authorization: Bearer <token>
Body: { "search_space_id": 1, "quantity": 2 }
Response: { "checkout_url": "https://checkout.stripe.com/..." }
```

### References
- `surfsense_web/components/pricing/pricing-section.tsx`
- `surfsense_backend/app/routes/stripe_routes.py` (lines ~204–271)
- `surfsense_web/app/dashboard/[search_space_id]/purchase-cancel/page.tsx`

## Dev Agent Record

### Agent Model Used
_TBD_

### File List
- `surfsense_web/components/pricing/pricing-section.tsx`
- `surfsense_web/components/pricing/PurchasePagesModal.tsx` (new)
