# Story 5.4: Hệ thống Khóa Tác vụ dựa trên Hạn Mức (Usage Tracking & Rate Limit Enforcement)

Status: ready-for-dev

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a Kỹ sư Hệ thống,
I want những người dùng hết quota (vượt quá file upload hoặc số lượng tin nhắn) bị từ chối dịch vụ cho đến khi nâng cấp,
so that mô hình kinh doanh không bị lỗ do chi phí LLM và Storage, áp dụng theo FR13.

## Acceptance Criteria

1. Endpoint Upload (Document Parser) và Endpoint Chat (RAG AI) sẽ query Database để check `Subscription_Status` và `document_count`, `token_balance`.
2. Nếu Document count >= Limit hệ thống từ chối Upload và trả lỗi `402 Payment Required` hoặc `403`. 
3. UI hiển thị Toast Error hoặc một Modal up-sell Upgrade to Pro.

## Tasks / Subtasks

- [ ] Task 1: Check Limits ở Route `/api/v1/documents`
  - [ ] Subtask 1.1: Tạo function Utils `check_upload_quota()` query lấy Package Plan của JWT User. Đếm số object hiện có trong DB (Count records trong table `documents` nơi `user_id = X`).
  - [ ] Subtask 1.2: Nếu đạt MAX_LIMIT (ví dụ 10 đối với FREE), Raise HTTPException 402/403.
- [ ] Task 2: Refine Frontend Validation 
  - [ ] Subtask 2.1: Ở component `DocumentUploader`, handle catch Error response `402`. Bật Toast thông báo "Bạn đã hết File Limit miễn phí".

## Dev Notes

### Relevant Architecture Patterns & Constraints
- Yêu cầu NFR Architecture: KHÔNG HARDCODE số file LIMIT vào trong code API mà phải load Enum hoặc Database row. Nên dùng một `config module` tĩnh hoặc Map Object dựa trên `plan_id` enum để check.
- Nếu User Plan là `PRO`, `MAX_LIMIT` là 100.
- Khúc check Chat Token Balance đã được cover một phần ở Story 3.5, nên Story 5.4 tập trung vào `File Upload Rate Limit` và `Chat Frequency Rate Limit` (tránh crawler/spam theo giờ).

### Project Structure Notes
- Module thay đổi:
  - `surfsense_backend/app/routes/documents_routes.py` (hoặc endpoints xử lý Upload mới nhất).
  - `surfsense_web/src/components/UploadDocument.tsx` 

### References
- [Epic 5.4 - Quota Check]

## Dev Agent Record

### Agent Model Used
Antigravity Claude 3.5 Sonnet Engine

### File List
- `surfsense_backend/app/routes/documents_routes.py`
