---
stepsCompleted:
  - step-01-validate-prerequisites.md
  - step-02-design-epics.md
inputDocuments:
  - _bmad-output/planning-artifacts/prd.md
  - _bmad-output/planning-artifacts/architecture.md
  - _bmad-output/planning-artifacts/ux-design-specification.md
---

# SurfSense - Epic Breakdown

## Overview

This document provides the complete epic and story breakdown for SurfSense, decomposing the requirements from the PRD, UX Design if it exists, and Architecture requirements into implementable stories.

## Requirements Inventory

### Functional Requirements

FR1: Người dùng có thể tải lên các tệp tài liệu (PDF, TXT) vào không gian làm việc của họ.
FR2: Người dùng có thể xem lại danh sách các tài liệu đã tải lên trước đó.
FR3: Người dùng có thể xem được trạng thái tiến trình trích xuất (Đang đợi, Đang xử lý, Hoàn thành, Lỗi) của một tài liệu.
FR4: Người dùng có thể xóa một tài liệu khỏi không gian làm việc của họ.
FR5: Người dùng có thể tạo một phiên hỏi đáp (Chat Session) mới.
FR6: Người dùng có thể gửi câu hỏi dạng văn bản vào một phiên chat.
FR7: Người dùng có thể nhận được các luồng phản hồi trực tiếp (Streaming responses) từ AI bot theo thời gian thực.
FR8: Người dùng có thể xem lại danh sách các phiên trò chuyện trong quá khứ.
FR9: Người dùng có thể đọc lại toàn bộ nội dung tin nhắn của một phiên trò chuyện cụ thể.
FR10: Người dùng có thể đọc danh sách tài liệu và nội dung các khung chat cũ ngay cả khi ngắt kết nối hoàn toàn với internet.
FR11: Người dùng có thể nhận biết được trạng thái đồng bộ dữ liệu hiện tại của hệ thống (Ví dụ: Offline, Đang đồng bộ, Đã cập nhật xong).
FR12: Hệ thống có khả năng tự động bóc tách văn bản và tạo Vector Embeddings một cách bất đồng bộ ngầm khi tài liệu mới được tải lên.
FR13: Hệ thống có khả năng chặn yêu cầu (Rate Limit) nếu người dùng sử dụng vượt mức Token cho phép hoặc tải file quá quy định.
FR14: Người dùng có thể xác thực (Authentication) để đăng nhập và bảo vệ dữ liệu thuộc private workspace của họ.

### NonFunctional Requirements

NFR-P1 (Time to First Token - TTFT): Hệ thống bắt buộc phải phản hồi ký tự đầu tiên từ AI Agent thông qua SSE dưới 1.5 giây kể từ khi user nhấn Submit.
NFR-P2 (Sync Latency): Thời gian bộ nhớ đệm Zero-cache đồng bộ thay đổi trạng thái từ Remote DB về Local IndexedDB không được vượt quá 3 giây.
NFR-P3 (Background Processing): Tác vụ bóc tách văn bản và tạo Vector Embeddings cho file <5MB phải xong trên Celery Queue dưới 30 giây.
NFR-S1 (Data Segregation): RLS bắt buộc áp dụng. User ID không có quyền truy vấn dữ liệu tài khoản khác.
NFR-S2 (Local Storage Security): Dữ liệu Zero-cache bị xóa hoàn toàn khi "Log Out".
NFR-SC1 (Worker Scalability): Celery Worker phải "Stateless", có thể add thêm n-Workers mà code không can thiệp.
NFR-R1 (Offline Tolerance): Giao diện không trắng xoá khi mất mạng, đọc cache mượt như đang online.

### Additional Requirements

- Tận dụng Starter Template đã chọn: Official Next.js CLI & Custom Fast-Modern Async API (Cần lưu ý cho Epic 1 Story 1).
- Cấu trúc hệ thống Monorepo dùng Docker-compose để boot Postgres, Redis, Zero Server và Backend.
- Database Postgres sử dụng extension pgvector 0.8.2. Backend Python dùng SQLModel.
- Đồng bộ Realtime Local-first với rocicorp/zero 1.1.1 (truyền JWT từ API gateway sang bộ zero-client).
- Backend FastAPI phải trả về các REST API được bọc response chuẩn: `{ "data": ..., "error": ..., "meta": ... }`.
- Naming convention: FastAPI dùng snake_case nhưng output Pydantic phải set `by_alias=True` để convert ra camelCase phục vụ cho TypeScript Client. Database strictly snake_case.
- State Management: Sử dụng Zustand cho Global UI state, form xử lý với react-hook-form. Mọi fetch data chính từ Zero hook thay vì REST API. 
- API Streaming: Thực thi Server-Sent Events cho luồng trả lời Chatbot RAG.

### UX Design Requirements

UX-DR1: Triển khai Design System từ shadcn/ui & Tailwind CSS. Base color là Zinc/Slate (Dark mode #09090b); màu nhấn Accent là Indigo/Teal chuyên dùng cho button và thẻ citation. Typography với font Inter/Geist Sans và JetBrains Mono.
UX-DR2: Ràng buộc Transition/Animation thời gian đáp ứng cực ngắn (<150ms) đáp ứng trải nghiệm Khởi tác Tức thì trên toàn ứng dụng.
UX-DR3: Cấu trúc Layout đặc thù Tách viền (Dynamic Split-Pane) – phân bổ màn hình hiển thị cả khu vực dòng Chat và Trình đọc/view Document đồng thời; cần implement thư viện như `react-resizable-panels`.
UX-DR4: Action "Interactive Citation" – Khi người dùng click hoặc tương tác thẻ citation, hệ thống phải liên kết điều khiển panel Document auto-scroll hoặc highlight sang đúng vị trí đoạn text gốc mà không cần refresh.
UX-DR5: Xây dựng System Indicators mượt mà (Micro-Sync Indicator) - chấm vàng góc màn hình thể hiện Syncing, thanh process bar nhỏ đính kèm các file list đang được upload (Index ẩn). Không dùng blocking modal spinners chặn màn hình.
UX-DR6: Hiển thị giao diện "Graceful Degradation" linh hoạt khi Offline: tự chuyển các nút/icon qua xám muted, duy trì trải nghiệm đọc danh sách và chat history trong trạng thái mất kết nối mạng.

### FR Coverage Map

FR1: Epic 2 - Tải tài liệu lên workspace
FR2: Epic 2 - Xem danh sách tài liệu đã tải
FR3: Epic 2 - Theo dõi trạng thái tiến trình trích xuất
FR4: Epic 2 - Xoá tài liệu khỏi workspace
FR5: Epic 3 - Tạo phiên chat mới
FR6: Epic 3 - Gửi câu hỏi vào chat
FR7: Epic 3 - Nhận phản hồi Streaming tức thì
FR8: Epic 4 - Xem danh sách phiên chat cũ
FR9: Epic 4 - Đọc nội dung tin nhắn cũ
FR10: Epic 4 - Đọc tài liệu/chat khi ngắt mạng (Offline mode)
FR11: Epic 4 - Nhận biết trạng thái đồng bộ Zero-sync (Online/Offline/Syncing)
FR12: Epic 2 - Tiến trình nhúng Vector bất đồng bộ ngầm
FR13: Epic 2 - Chặn yêu cầu nếu vượt mức cho phép (Rate Limit)
FR14: Epic 1 - Xác thực và bảo vệ dữ liệu (Workspace)

## Epic List

### Epic 1: Thiết lập Không gian riêng tư & Xác thực người dùng (User Workspace & Authentication)
Người dùng có thể đăng ký, đăng nhập và sở hữu một vùng không gian thao tác hoàn toàn tách biệt, bảo mật tuyệt đối cho dữ liệu cá nhân của họ. Epic này đặt nền móng hạ tầng (Next.js, FastAPI, Database) cho các tính năng tiếp theo.
**FRs covered:** FR14

#### Story 1.1: Khởi tạo Hạ tầng Dự án & Cơ sở Dữ liệu (Project Infrastructure & Database Init)
As a Kỹ sư Hệ thống,
I want thiết lập bộ khung Next.js, FastAPI, và cấu hình Docker-compose cho Postgres/Redis/ZeroServer,
So that toàn bộ nền tảng có thể khởi chạy môi trường phát triển (Dev Environment) một cách nhất quán cho tất cả các team.

**Acceptance Criteria:**
**Given** môi trường dự án mới
**When** chạy lệnh `docker-compose -f docker/docker-compose.dev.yml up -d`
**Then** các containers Postgres 16 (với pgvector), Redis, Zero-Server, FastAPI, và Next.js khởi tạo thành công
**And** database tự động migrate được schema ban đầu bao gồm bảng `users` với quy tắc `snake_case`.

#### Story 1.2: Triển khai Backend API Xác thực & JWT (Backend Auth API & JWT)
As a Người dùng,
I want gọi API an toàn để tạo tài khoản, đăng nhập và lấy mã Token (JWT),
So that hệ thống xác thực được danh tính của tôi và kích hoạt RLS (Row-level Security) bảo vệ dữ liệu trên Database Postgres.

**Acceptance Criteria:**
**Given** thông tin đăng nhập hợp lệ
**When** gửi request tới endpoint liên quan `/api/v1/auth/login`
**Then** hệ thống trả về mã JWT chứa userID hợp lệ, bọc trong cấu trúc Wrapper chuẩn `{ "data": {"token": "xxx"}, "error": null, "meta": null }`
**And** Cấu hình Row-Level Security (RLS) cơ bản cho bảng dữ liệu (người này không query được dữ liệu của người kia).

#### Story 1.3: Giao diện Đăng nhập & Tích hợp Token vào Zero-Client (Frontend Auth UI)
As a Người dùng,
I want sử dụng giao diện trơn tru để đăng ký/đăng nhập,
So that tôi nhận được Token và ngay lập tức kết nối tới hệ thống dữ liệu Local-first an toàn qua Zero Client.

**Acceptance Criteria:**
**Given** tôi đang ở trạng thái khách (Guest) trên UI
**When** tôi điền form đăng nhập thành công
**Then** giao diện lưu token vào cục bộ và tự động khởi tạo instance `ZeroClient` để bắt đầu mở cầu nối WebSockets.
**And** khi tôi nhấn nút "Đăng xuất" (Log Out), hàm `onLogout()` tự động thực thi dọn dẹp sạch (purge) toàn bộ IndexedDB, chặn bảo mật.
**And** Giao diện (Form đăng nhập, nút bấm) ứng dụng quy chuẩn UX-DR1 (Màu Base Zinc/Accent Indigo, font Inter).

### Epic 2: Quản lý Kho kiến thức & Trích xuất tự động (Knowledge Base Management & Ingestion)
Người dùng dễ dàng kéo thả các tệp PDF/TXT lên hệ thống; hệ thống tự động bóc tách dữ liệu mượt mà trong nền mà không làm gián đoạn công việc. Họ nắm rõ tiến độ nạp file và làm chủ khối lượng tài liệu của mình.
**FRs covered:** FR1, FR2, FR3, FR4, FR12, FR13

#### Story 2.1: Khởi tạo Kiến trúc Tác vụ nền & Xử lý PDF (Celery Worker & PDF Parser)
As a Kỹ sư Hệ thống,
I want xây dựng hệ thống worker bất đồng bộ (Celery + Redis) để bóc tách văn bản và tạo Vector Embeddings,
So that hệ thống API chính không bị nghẽn khi người dùng upload file, và có thể scale linh hoạt số lượng worker.

**Acceptance Criteria:**
**Given** phần mềm nhận một file PDF/TXT được đẩy vào hàng đợi (Queue)
**When** worker được phân công thực thi tác vụ
**Then** tiến trình phân giải text và nạp Vector qua pgvector hoàn thành dưới 30s (đối với file <5MB)
**And** trạng thái bản ghi tài liệu trên Database được cập nhật tuần tự (Processing -> Completed hoặc Error).

#### Story 2.2: Triển khai API Tải lên & Giới hạn Rate Limit (Upload API & Rate Limiting)
As a Kỹ sư Backend,
I want xây dựng endpoint FastAPI cho việc upload tài liệu kèm cơ chế Rate Limit,
So that server tiếp nhận an toàn và ngăn chặn upload spam quá mức hệ thống cho phép.

**Acceptance Criteria:**
**Given** người dùng đăng nhập hợp lệ
**When** đính kèm file và gửi POST tới `/api/v1/documents`
**Then** hệ thống check user token, lưu file vô Storage, tạo record ở DB với status 'Queue', và trigger đẩy task vào Celery
**And** nếu user push liên tục quá mức quy định (token/hạn mức tải), API sẽ trả về lỗi `429 Too Many Requests` bọc trong error format chuẩn.

#### Story 2.3: Giao diện Quản lý Tài liệu & Chỉ báo Syncing Khớp nối (Knowledge Base UI & Micro-Sync Indicators)
As a Người dùng,
I want thấy ngay lập tức danh sách tài liệu đang có và dễ dàng tải file mới lên,
So that tôi biết file nào đã sẵn sàng để chat, file nào đang chạy nền mà không bị gián đoạn thao tác chuột.

**Acceptance Criteria:**
**Given** người dùng ở giao diện không gian làm việc (Workspace)
**When** có một tài liệu đang được tải lên hoặc xử lý (Processing)
**Then** UX hiển thị thanh tiến trình nhỏ ở góc trên màn hình / cạnh danh sách (Micro-Sync Indicator) và không được chặn màn hình (UX-DR5)
**And** danh sách tài liệu được lấy thông qua Zero-client tự động update state realtime khi worker xử lý xong (FR2, FR3).

#### Story 2.4: API và Giao diện Xóa tài liệu khỏi Workspace (Delete Document Flow)
As a Người dùng,
I want chọn một tài liệu cũ và xóa hoàn toàn,
So that không gian lưu trữ được dọn dẹp và AI sẽ không bao giờ truy cập nội dung đó nữa.

**Acceptance Criteria:**
**Given** người dùng đang có tài liệu hiển thị trên danh sách
**When** người dùng click icon "Xoá" file
**Then** dữ liệu tài liệu lập tức bị loại bỏ khỏi giao diện UI do cơ chế optimism update của Zero
**And** trên Database, bản ghi bị xoá hoặc mark deleted, kèm theo việc dọn dẹp các Vectors rác liên quan trong background.

### Epic 3: Trò chuyện AI Hiện đại & Nguồn trích dẫn (AI Interactive Chat & Streaming Responses)
Người dùng có trải nghiệm truy vấn kho tài liệu "không độ trễ" (Instant Action) thông qua chat. Kết quả được stream về theo thời gian thực như một trợ lý xịn, tích hợp hệ thống Split-pane tinh tế để đối chiếu thẳng với Nguồn trích dẫn.
**FRs covered:** FR5, FR6, FR7

#### Story 3.1: API Tạo & Quản lý Phiên Chat (Chat Session API)
As a Người dùng,
I want tạo một phiên trò chuyện (chat session) mới với AI,
So that tôi có thể bắt đầu một định mức hội thoại mới, tách bạch hoàn toàn với các chủ đề cũ.

**Acceptance Criteria:**
**Given** cửa sổ Chat
**When** tôi chọn lệnh "New Chat" hoặc nhập thẳng vào input đầu tiên
**Then** hệ thống tạo một "Session" ID mới trên Database và lưu tin nhắn đầu tiên của user (FR5, FR6)
**And** trả về data qua REST API theo wrapper chuẩn để client chốt phiên làm việc.

#### Story 3.2: Khối RAG Engine & Cổng trả Streaming SSE (RAG Engine & SSE Endpoint)
As a Kỹ sư Backend,
I want xây dựng khối RAG query bằng pgvector và đẩy dữ liệu về dạng Server-Sent Events (SSE),
So that AI có thể phản hồi từng chữ một (streaming) ngay khi lấy được ngữ cảnh, và đảm bảo chuẩn NFR-P1 (< 1.5s).

**Acceptance Criteria:**
**Given** backend nhận một câu hỏi của user và Session ID
**When** gọi tới Model AI (ví dụ OpenAI/Gemini) với ngữ cảnh lấy từ VectorDB
**Then** API `/api/v1/chat/stream` trả dòng response trả về dưới định dạng sự kiện SSE (text/event-stream) (FR7)
**And** ký tự đầu tiên (First token) về tới client dưới 1.5s
**And** ở cuối luồng stream trả về đính kèm bộ Metadata (Array các id/đoạn trích dẫn được dùng).

#### Story 3.3: Giao diện Khung Chat & Tiếp nhận Streaming (Chat UI & SSE Client)
As a Người dùng,
I want thấy AI gõ từng chữ một vào màn hình chat kèm format Markdown đàng hoàng,
So that tôi không phải mòn mỏi nhìn biểu tượng Loading như các web đời cũ.

**Acceptance Criteria:**
**Given** tôi vừa bấm gửi câu hỏi "Ping"
**When** Next.js client mở luồng SSE kết nối về FastAPI
**Then** tin nhắn được append dần lên UI mượt mà với hoạt ảnh <150ms
**And** render được định dạng Markdown cơ bản (Bold, List, Code block) một cách trơn tru, không xộc xệch nhảy dòng khó chịu.

#### Story 3.4: Kiến trúc Split-Pane & Tương tác Trích dẫn (Split-Pane Layout & Interactive Citation)
As a Người dùng,
I want đọc khung chat ở một bên và văn bản gốc ở bên cạnh trên cùng 1 màn hình, bấm vào thẻ [1] ở chat là bên kia nhảy text tương ứng,
So that tôi có thể đối chiếu thông tin AI "bịa" hay "thật" ngay lập tức mà không phải tìm mỏi mắt.

**Acceptance Criteria:**
**Given** UI chia 2 bên (Split-Pane - bằng react-resizable-panels) - Chat trái, Doc phải (UX-DR3)
**When** AI trả lời xong có đính kèm cite `[1]`, tôi click vào `[1]`
**Then** bảng Document tự động đổi sang file tương ứng và auto-scroll + highlight dải vàng đúng dòng text đó (UX-DR4).

#### Story 3.5: Lựa chọn Mô hình LLM dựa trên Subscription (Model Selection via Quota)
As a Người dùng,
I want chọn cấu hình mô hình trí tuệ nhân tạo (VD: Claude 3.5 Sonnet, GPT-4) được cung cấp sẵn mà không cần điền API key cá nhân,
So that tôi có thể dùng trực tiếp và chi phí sử dụng được trừ thẳng vào số Token thuộc gói cước của tôi.

**Acceptance Criteria:**
**Given** tôi đang trong giao diện Chat
**When** tôi bấm vào Dropdown "LLM Model"
**Then** hệ thống liệt kê các tùy chọn model do SurfSense hỗ trợ kèm chi phí token mỗi lần gọi
**And** tuyệt đối không hiển thị ô nhập "Your API Key"
**And** nếu user dùng hết quota của Subscription khi gọi model cao cấp, hệ thống tự động chặn và bật thông báo Upgrade.

### Epic 4: Trải nghiệm Truy xuất Offline & Đồng bộ Local-First (Local-First & Offline Experience)
Người dùng tự do lướt xem danh sách tài liệu và đọc lịch sử chat ngay cả khi nằm ngoài vùng phủ sóng internet. Hệ thống cung cấp chỉ báo trạng thái rõ ràng (Syncing, Offline) giúp họ luôn an tâm về dữ liệu.
**FRs covered:** FR8, FR9, FR10, FR11

#### Story 4.1: Đồng bộ Danh sách Phiên Chat & Lịch sử Tin nhắn (Chat History Sync)
As a Người dùng,
I want danh sách lịch sử các phiên chat và tin nhắn bên trong tự động đồng bộ xuống máy tôi qua Zero-client,
So that tôi mở app lên là thấy ngay lập tức lịch sử cũ (FR8, FR9) và đọc liên tiếp không cần chờ load từ internet (FR10).

**Acceptance Criteria:**
**Given** thiết bị của tôi đã từng kết nối mạng trước đó
**When** tôi chọn một Session cũ (như hôm qua) trong Sidebar
**Then** hệ thống query trực tiếp từ IndexedDB cục bộ qua thư viện `@rocicorp/zero` và móc lên UI
**And** thời gian data mới từ server đẩy cập nhật xuống dưới Local Storage luôn đảm bảo dưới 3s (NFR-P2).

#### Story 4.2: Giao diện Phân rã Ân hạn khi ngắt mạng (Graceful Degradation Offline UI)
As a Người dùng,
I want hệ thống tự động khóa các tính năng cần internet như "Chat/Gửi tin/Upload" khi tôi mất wifi,
So that tôi không bị văng lỗi hay hiện màn hình đơ cứng, thay vào đó vẫn thong dong đọc nội dung cũ (NFR-R1).

**Acceptance Criteria:**
**Given** người dùng cấu hình ngắt mạng cố ý hoặc đột ngột mất wifi
**When** họ đang mở app
**Then** giao diện tự động bật mode Graceful Degradation: Input chat bị disable, nút Upload file bị mờ (muted xám)
**And** người dùng vẫn có thể click đọc văn bản trên màn Split-Pane thoăn thoắt không trễ (UX-DR6).

#### Story 4.3: Tích hợp Chỉ báo Trạng thái Mạng Toàn Cục (Global Network & Sync Indicators)
As a Người dùng,
I want thấy một icon nhỏ hoặc dải màu trực quan cho biết App đang Online, Offline, hay Syncing,
So that tôi chủ động biết ứng dụng có đang "sống" và "khớp nối" dữ liệu với đám mây hay không (FR11).

**Acceptance Criteria:**
**Given** app đang khởi chạy bình thường
**When** trạng thái kết nối mạng của Zero Client hoặc Browser thay đổi
**Then** Header hoặc góc dưới màn hình cập nhật icon (Xanh: Connected / Vàng: Syncing / Đỏ/Xám: Offline)
**And** thiết kế phải hòa hợp với bộ màu ZinC/Slate đã chọn, tuyệt đối không dùng thông báo (alert) nhảy ập vào mặt người dùng.

### Epic 5: Quản lý Gói cước, Thanh toán & Hạn mức Sử dụng (Subscription, Billing & Usage Management)
Hệ thống biến từ một ứng dụng tĩnh thành một nền tảng SaaS thương mại thông qua tích hợp thanh toán Stripe. Người dùng có thể xem bảng giá, chọn gói cước phù hợp, thanh toán an toàn và hệ thống tự động kiểm soát quota sử dụng dựa trên gói đăng ký, đảm bảo mô hình kinh doanh bền vững.
**FRs covered:** FR15, FR16, FR17

#### Story 5.1: Giao diện Bảng giá & Lựa chọn Gói Cước (Pricing & Plan Selection UI)
As a Khách hàng tiềm năng,
I want xem một bảng giá rõ ràng về các gói cước (ví dụ: Free, Pro, Team) với quyền lợi tương ứng,
So that tôi biết chính xác số lượng file/tin nhắn mình nhận được trước khi quyết định nâng cấp.

**Acceptance Criteria:**
**Given** tôi đang ở trang Pricing hoặc Modal nâng cấp tài khoản
**When** tôi lướt xem các tùy chọn gói cước
**Then** UI hiển thị các mức giá (monthly/yearly) rõ ràng cùng các bullets tính năng (FR15)
**And** thiết kế áp dụng chuẩn UX-DR1 (Dark mode, Accent Indigo) và có hiệu ứng hover mượt mà cho các pricing cards (<150ms).

#### Story 5.2: Tích hợp Stripe Checkout (Stripe Payment Integration)
As a Người dùng,
I want bấm "Nâng cấp" và được chuyển tới trang thanh toán an toàn,
So that tôi có thể điền thông tin thẻ tín dụng mà không sợ bị lộ dữ liệu trên máy chủ của SurfSense.

**Acceptance Criteria:**
**Given** tôi chọn một gói cước trả phí ở Story 5.1
**When** tôi click nút "Nâng cấp qua Stripe"
**Then** hệ thống gọi API backend lấy `sessionId` của Stripe Checkout
**And** tôi được điều hướng (redirect) an toàn sang trang thanh toán chính thức do Stripe cung cấp (FR16, NFR-S3).

#### Story 5.3: Webhook & Cập nhật Trạng thái Gói cước (Stripe Webhook Sync)
As a Kỹ sư Hệ thống,
I want backend tự động hứng Webhook từ Stripe mỗi khi có thanh toán thành công, gia hạn, hoặc hủy gói,
So that database được cập nhật trạng thái Subscription của user (Active/Canceled) mà không cần can thiệp thủ công.

**Acceptance Criteria:**
**Given** hệ thống Stripe bắn ra một event (ví dụ `checkout.session.completed` hoặc `customer.subscription.updated`)
**When** endpoint `/api/v1/stripe/webhook` tiếp nhận sự kiện
**Then** hệ thống verify chữ ký bảo mật từ Stripe (Stripe-Signature) để đảm bảo không bị giả mạo
**And** cập nhật trường `subscription_status` và `plan_id` tương ứng của User trong Database (FR17).

#### Story 5.4: Hệ thống Khóa Tác vụ dựa trên Hạn Mức (Usage Tracking & Rate Limit Enforcement)
As a Kỹ sư Hệ thống,
I want những người dùng hết quota (vượt quá file upload hoặc số lượng tin nhắn) bị từ chối dịch vụ cho đến khi nâng cấp,
So that mô hình kinh doanh không bị lỗ do chi phí LLM và Storage, áp dụng theo FR13.

**Acceptance Criteria:**
**Given** người dùng ở gói miễn phí (Ví dụ: giới hạn 5 file)
**When** họ cố gắng upload file thứ 6
**Then** API `/api/v1/documents` từ chối xử lý và trả về lỗi `403/429` (Quota Exceeded)
**And** UI nhận phản hồi từ API và hiển thị một thông báo / Modal nhỏ để up-sell giới thiệu họ lên gói Pro để tải file tiếp.
