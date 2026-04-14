# Story 5.1: Giao diện Bảng giá & Lựa chọn Gói Cước (Pricing & Plan Selection UI)

Status: done

## Story

As a Khách hàng tiềm năng,
I want xem một bảng giá rõ ràng về các gói cước (ví dụ: Free, Pro, Team) với quyền lợi tương ứng,
so that tôi biết chính xác số lượng file/tin nhắn mình nhận được trước khi quyết định nâng cấp hoặc duy trì để quản lý ví (Wallet/Token) của mình.

## Acceptance Criteria

1. UI hiển thị các mức giá (monthly/yearly) rõ ràng cùng các bullets tính năng.
2. Thiết kế áp dụng chuẩn UX-DR1 (Dark mode, Base Zinc, Accent Indigo) hiện có của app.
3. Kèm theo hiệu ứng hover mượt mà cho các Pricing Cards (<150ms delay).
4. Phân bổ ít nhất 2 gói cước (Free, Pro) gắn liền với Limit.

## As-Is (Code hiện tại)

| Component | Hiện trạng | File |
|-----------|-----------|------|
| Pricing Page | **Đã tồn tại** — route `/pricing` | `surfsense_web/app/(home)/pricing/page.tsx` |
| Pricing Section | **Đã tồn tại** — 3 tiers (FREE / PAY AS YOU GO / ENTERPRISE) | `surfsense_web/components/pricing/pricing-section.tsx` |
| Pricing Data | Static `demoPlans` constant — Free=500 pages, PAYG=$1/1000 pages, Enterprise=Contact | `pricing-section.tsx` lines 2–59 |
| CTA Buttons | Free="Get Started" → `/login`, PAYG="Get Started" → `/login`, Enterprise="Contact Sales" → `/contact` | `pricing-section.tsx` |
| Monthly/Yearly Toggle | **Không có** — chỉ có `price` và `yearlyPrice` fields nhưng chưa có toggle UI | |

**Gap:** UI hiện tại mô hình PAYG (mua page packs 1 lần). Cần chuyển sang **Subscription tiers** (Free/Pro/Team monthly/yearly) theo PRD.

## Tasks / Subtasks

- [x] Task 1: Thiết kế lại Pricing Tiers (Frontend)
  - [x] Subtask 1.1: Cập nhật `demoPlans` constant → đổi sang subscription tiers:
    - **Free**: 500 pages ETL, 50 LLM messages/day, basic models (GPT-3.5), $0/mo
    - **Pro**: 5,000 pages ETL, 1,000 LLM messages/day, premium models (GPT-4, Claude), $X/mo hoặc $Y/year
    - **Team/Enterprise**: Unlimited, custom pricing, SSO, audit logs
  - [x] Subtask 1.2: Thêm Monthly/Yearly toggle switch — hiển thị `price` vs `yearlyPrice` tương ứng.

- [x] Task 2: Kết nối nút CTA với Stripe Checkout (Frontend)
  - [x] Subtask 2.1: Nút "Get Started" cho tier Free → redirect `/login` (giữ nguyên).
  - [x] Subtask 2.2: Nút "Upgrade to Pro" → gọi `POST /api/v1/stripe/create-subscription-checkout` (Story 5.2) với `plan_id` tương ứng. Nếu user chưa login → redirect `/login` trước.
  - [x] Subtask 2.3: Nút "Contact Sales" cho Enterprise → giữ nguyên `/contact`.

- [x] Task 3: Graceful degradation khi Offline
  - [x] Subtask 3.1: Pricing data dùng static constant (load được offline). Disable nút "Upgrade" khi offline để tránh lỗi network request.

## Dev Notes

### Giữ lại hay xóa PAYG?
Quyết định kinh doanh: PAYG (mua page packs 1 lần) có thể tồn tại song song với subscription, hoặc bị thay thế hoàn toàn. Nếu giữ PAYG → thêm 1 tier "Pay As You Go" bên cạnh Free/Pro. Nếu thay → xóa PAYG flow cũ.

### Stripe Price IDs
Mỗi tier subscription cần 1 Stripe Price ID (tạo trên Stripe Dashboard):
- `STRIPE_FREE_PRICE_ID` (optional — free tier không cần checkout)
- `STRIPE_PRO_MONTHLY_PRICE_ID`
- `STRIPE_PRO_YEARLY_PRICE_ID`
→ Lưu vào env vars backend, KHÔNG hardcode trong frontend.

### References
- `surfsense_web/components/pricing/pricing-section.tsx` — pricing UI hiện tại
- `surfsense_web/app/(home)/pricing/page.tsx` — pricing page route

## Dev Agent Record

### Implementation Notes
- Chuyển `pricing-section.tsx` thành Client Component (`"use client"`) để xử lý online state và Stripe CTA.
- Cập nhật `PricingPlan` interface trong `pricing.tsx`: thêm `onAction?: () => void` và `disabled?: boolean`.
- Bật lại Monthly/Yearly toggle (đã bị comment), refactor để nhận `isYearly` và `onToggleBilling` props từ parent.
- Pro plan dùng `onAction` → `handleUpgradePro()`: check `isAuthenticated()` rồi gọi `POST /api/v1/stripe/create-subscription-checkout`.
- Graceful degradation: `useEffect` lắng nghe `online`/`offline` events, disable nút Upgrade + thay text khi offline.
- Pricing data là static constant → luôn render được kể cả offline.
- Quyết định xóa PAYG tier cũ, thay bằng Free/Pro/Enterprise subscription tiers theo PRD.

### Completion Notes
✅ Tất cả tasks/subtasks hoàn thành. AC 1-4 đều được đáp ứng.

### File List
- `surfsense_web/components/pricing/pricing-section.tsx` — rewritten: subscription tiers, Stripe CTA, offline degradation
- `surfsense_web/components/pricing.tsx` — updated: PricingPlan interface, toggle enabled, button renders onAction/Link

### Review Findings

- [x] [Review][Decision] Gate Stripe checkout khi `isSelfHosted()` — DISMISSED: dự án chuyển sang SaaS-only, không còn self-hosted
- [x] [Review][Patch] Dùng `authenticatedFetch` thay `fetch` raw — xử lý 401/token refresh [pricing-section.tsx:43]
- [x] [Review][Patch] Hiện toast/error cho user khi Stripe checkout fail — hiện chỉ `console.error` [pricing-section.tsx:49-65]
- [x] [Review][Patch] Thêm `if (isLoading) return;` early guard chống double-click [pricing-section.tsx:33]
- [x] [Review][Patch] Xóa `useRouter` import không dùng [pricing-section.tsx:4,15]
- [x] [Review][Patch] Validate `checkout_url` bắt đầu bằng `https://` trước khi redirect [pricing-section.tsx:57]
- [x] [Review][Patch] Fix "Save 20%" → "Save 25%" hoặc tính dynamic từ giá [pricing.tsx:104]
- [x] [Review][Defer] `ref` cast `as any` trên Switch component — deferred, pre-existing [pricing.tsx:99]

### Change Log
- 2026-04-14: Chuyển sang subscription tiers (Free/Pro/Enterprise), bật toggle Monthly/Yearly, kết nối Stripe Checkout, graceful offline degradation.
