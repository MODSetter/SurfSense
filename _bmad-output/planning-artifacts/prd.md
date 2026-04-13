---
stepsCompleted:
  - step-01-init.md
  - step-02-discovery.md
  - step-02b-vision.md
  - step-02c-executive-summary.md
  - step-03-success.md
  - step-04-journeys.md
  - step-05-domain.md
  - step-06-innovation.md
  - step-07-project-type.md
  - step-08-scoping.md
  - step-09-functional.md
  - step-10-nonfunctional.md
  - step-11-polish.md
  - step-12-complete.md
classification:
  projectType: web_app/api_backend
  domain: scientific
  complexity: medium
  projectContext: brownfield
inputDocuments:
  - docs/index.md
  - docs/project-overview.md
  - docs/architecture-backend.md
  - docs/architecture-web.md
  - docs/data-models.md
  - docs/api-contracts.md
  - docs/source-tree-analysis.md
  - docs/component-inventory.md
  - docs/development-guide.md
  - docs/deployment-guide.md
  - docs/integration-architecture.md
  - docs/project-scan-report.json
  - _bmad-output/project-context.md
documentCounts:
  briefCount: 0
  researchCount: 0
  brainstormingCount: 0
  projectDocsCount: 13
workflowType: 'prd'
---

# Product Requirements Document - SurfSense

**Author:** luisphan
**Date:** 2026-04-13

## Executive Summary

SurfSense là nền tảng tìm kiếm và trích xuất ngữ cảnh (Context Extraction & Agentic RAG) AI-native, được thiết kế để giải quyết triệt để bài toán độ trễ và phân mảnh thông tin. Hệ thống cho phép người dùng và hạ tầng doanh nghiệp truy vấn dữ liệu theo thời gian thực một cách liền mạch, biến kho dữ liệu phức tạp thành các câu trả lời chính xác, an toàn và có thể hành động ngay lập tức. Thông qua kiến trúc Web App & Backend linh hoạt (Next.js & FastAPI), SurfSense đảm bảo trải nghiệm người dùng tối ưu với cơ chế xử lý dữ liệu song song và quy trình lập luận AI chuyên sâu.

### What Makes This Special

Điểm khác biệt cốt lõi của SurfSense nằm ở kiến trúc **Local-first** kết hợp cùng mô hình **Multi-agent Graph**. Bằng việc tích hợp công nghệ đồng bộ `@rocicorp/zero` (Zero-cache), nền tảng hỗ trợ đồng bộ dữ liệu tức thì và hoạt động hoàn hảo ngay cả khi offline (mất kết nối internet). Điều này khắc phục được điểm yếu cố hữu của các hệ thống RAG truyền thống: sự phụ thuộc vào kết nối mạng và độ trễ truy vấn cao. Đặc biệt, việc triển khai FastAPI & LangGraph cho phép hệ thống triển khai các luồng tác vụ Agentic linh hoạt đa bước, streaming kết quả về phía người dùng với tốc độ cao đồng thời bảo vệ nghiêm ngặt tính riêng tư của dữ liệu.

## Project Classification

- **Project Type:** Web App & API Backend
- **Domain:** Scientific / General (AI, Thông tin mạng, Retrieval-Augmented Generation)
- **Complexity:** Medium (Tích hợp Local-first Data Sync, Background Workers với Celery, Multi-agent orchestration)
- **Project Context:** Brownfield (Nền tảng kiến trúc đã thiết lập với Postgres/pgvector, Redis, Docker Stack và quy trình CI/CD hoàn thiện)

## Success Criteria

### User Success

Người dùng trải nghiệm được khoảnh khắc "Aha!" khi nhận được luồng phản hồi (streaming response) từ Agentic RAG ngay lập tức (dưới 1 giây kể từ khi submit) và có thể truy vấn ngữ cảnh/kho tài liệu ở dạng offline mượt mà không khác gì khi có mạng nhờ Zero-cache.

### Business Success

Hệ thống đạt tỷ lệ giữ chân (Retention rate) cao với tệp người dùng nghiên cứu chuyên sâu, đồng thời kiến trúc module hóa đủ linh hoạt để mở rộng quy mô (Scalability) và sẵn sàng đóng gói license nhắm tới thị trường B2B.

### Technical Success

Cơ chế Local-first (Zero-cache) đồng bộ hàng nghìn vector và bản ghi dữ liệu ngầm mà không gây tác động hay đóng băng (freeze) UI client. Ở backend, các Celery workers xử lý pipeline nhúng dữ liệu (background embeddings) hoàn toàn cách ly, duy trì độ ổn định và trơn tru cho API phục vụ.

### Measurable Outcomes

- Độ trễ Time-to-First-Token (TTFT) < 1 giây kể cả với các truy vấn sử dụng đa AI Agent.
- Web Client truy cập bình thường toàn bộ thông tin đã lưu trữ khi offline.
- Tác vụ Embedding không gây nghẽn (bottleneck) hệ thống Chat.

## Product Scope

### MVP - Minimum Viable Product

- Tích hợp framework `@rocicorp/zero` cung cấp Local-first caching và realtime sync.
- Hỗ trợ khai thác truy vấn văn bản, lưu trữ lịch sử offline.
- Triển khai LangGraph Agents cơ bản (tìm, đọc, tổng hợp nội dung).

### Growth Features (Post-MVP)

- Hỗ trợ RAG đa định dạng (đọc file PDF, hình ảnh).
- Tích hợp tài liệu nội bộ, Chatbot riêng cá nhân hóa.
- Filter thông minh và tagging đa dạng để quản lý vector.

### Vision (Future)

- Autonomous Proactive Agents: AI chạy nền thu thập nguồn thông tin hữu ích theo sở thích của người dùng để liên tục cập nhật kho ngữ cảnh cá nhân.

## User Journeys

### 1. Primary User - Success Path
- **Người dùng:** Alex - Chuyên viên Nghiên cứu Dữ liệu.
- **Tình huống:** Có hàng chục tài liệu phân mảnh và cần tổng hợp nhanh.
- **Hành trình:** Cài đặt và mở SurfSense Web App -> Nạp hàng loạt tài liệu -> Hệ thống tự động phân tích và nhúng dữ liệu qua Celery workers/LangGraph API đồng bộ bằng Zero-cache trong nền -> Gõ truy vấn -> SurfSense streaming câu trả lời tức thì kèm trích dẫn.

### 2. Primary User - Edge Case (Offline Mode)
- **Người dùng:** Alex (Trường hợp mất kết nối mạng).
- **Tình huống:** Cần tra cứu gấp dữ liệu đã nạp mà không có Internet.
- **Hành trình:** Mở Web App offline -> Toàn bộ dữ liệu ngữ cảnh đều khả dụng nhờ Zero-cache -> Truy vấn Local DB -> Giao diện phản hồi mượt mà không độ trễ, không lỗi "No Internet".

### 3. Admin / Operations User
- **Người dùng:** Jamie - Kỹ sư DevOps nội bộ.
- **Tình huống:** Quản lý tài nguyên, theo dõi tính ổn định khi traffic tăng cao.
- **Hành trình:** Giám sát hệ thống qua Docker Logs -> Nhận biết hàng đợi Celery có lượng công việc lớn -> Can thiệp/Scale up node không làm luồng chat của người dùng bị gián đoạn.

### 4. API Consumer / Developer
- **Người dùng:** Sam - Kỹ sư phần mềm.
- **Tình huống:** Xây dựng ứng dụng bên thứ ba tích hợp AI Agent của SurfSense.
- **Hành trình:** Tham khảo API -> Gửi cấu trúc truy vấn vào endpoint FastAPI `/api/rag/stream` -> Nhận lại chuỗi sự kiện Server-Sent Events (SSE) theo thời gian thực -> Tích hợp dễ dàng nội dung streaming vào ứng dụng của mình.

### Journey Requirements Summary

- **Giao diện Client (Journey 1 & 2):** Đòi hỏi kiến trúc Frontend (Next.js) kết hợp chặt chẽ việc quản trị State và Local Offline Syncing `@rocicorp/zero`. Phải cung cấp tín hiệu (Indicator) về tiến trình đồng bộ dữ liệu tới file bộ nhớ cục bộ mà không gây khóa luồng chính (Main Thread).
- **Kiến trúc Server & DevOps (Journey 3 & 4):** Backend APIs cần được REST/SSE tối ưu; chuẩn Open-API contracts; và cách ly nghiêm ngặt giữa luồng Embedding Worker process cùng Data sync để không gây tắc nghẽn khả năng trả lời query.

## Domain-Specific Requirements

### Compliance & Regulatory
- **Quyền bảo mật dữ liệu:** Bảo vệ quyền riêng tư tuyệt đối cho tài liệu độc quyền của người dùng nhờ tận dụng kiến trúc Local-first (giảm thiểu luồng dữ liệu thô đẩy lên hạ tầng cloud không cần thiết).

### Technical Constraints
- **Kiểm soát tính chính xác (Accuracy):** Hệ thống LLM phải tuân thủ chặt chẽ ngữ cảnh được nạp (Strict Context Grounding), chống lại hiện tượng ảo giác (Hallucinations).
- **Phân bổ tài nguyên (Computational Resources):** Duy trì sự cô lập hoàn toàn giữa Celery workers (dành cho embed) và FastAPI server (dành cho API endpoints) để loại bỏ rủi ro nghẽn cổ chai.

### Integration Requirements
- Kiến trúc mở cho phép người dùng tự do lựa chọn các mô hình ngôn ngữ (OpenAI, Anthropic) do SurfSense quản lý. Chi phí sử dụng Token sẽ được tự động trừ vào gói cước Subscription của người dùng (Tuyệt đối không hỗ trợ chức năng User tự nhập LLM API Key riêng nhằm kiểm soát chất lượng và doanh thu).

### Risk Mitigations
- **Phòng ngừa lỗi đọc file:** Cơ chế fallback thông minh phát hiện, báo lỗi cụ thể và tiếp tục với các file không trích xuất được text.
- **Giám sát dung lượng phía biên (Client):** Kiểm soát kích cỡ của IndexedDB hay Local DB để phòng ngừa Zero-cache làm ngốn bộ nhớ thiết bị của Client.

## Innovation & Novel Patterns

### Detected Innovation Areas
**Local-First Agentic RAG:** Sự kết hợp mới mẻ giữa RAG nhiều tác tử điều phối (Multi-Agent) cùng kiến trúc Local-first (thông qua `@rocicorp/zero`). Các hệ thống RAG truyền thống dựa hoàn toàn vào Cloud Database nên thường gặp độ trễ lớn và giới hạn về bộ nhớ cục bộ. SurfSense đảo ngược mô hình này, đồng bộ ngữ cảnh (Context) trực tiếp về IndexedDB/SQLite ở biên (Client). Điều này mang lại cảm giác phản hồi tức thì (Instant) mà vẫn sở hữu khả năng suy luận đa tầng ở phía Backend (thông qua LangGraph).

### Market Context & Competitive Landscape
Đa số các công cụ RAG SaaS hiện tại phụ thuộc hoàn toàn vào Cloud (gây lo ngại về bảo mật tài liệu và phụ thuộc internet). Ngược lại, các công cụ Local (chạy LLM trên máy cá nhân) lại thiếu tính liên thông giữa nhiều thiết bị và giới hạn bởi phần cứng nội bộ. SurfSense đánh vào khoảng trống ở giữa (Sweet Spot): Nắm giữ độ bảo mật và tốc độ của "Local", đồng thời khai thác sức mạnh khổng lồ của "Cloud LLM/Agents".

### Validation Approach
- **Đo lường TTFT:** Đo đạc "Time-to-First-Token", đặt mục tiêu luôn phản hồi dưới 1 giây nhờ việc bớt đi một bước gọi Database trung gian.
- **Kiểm thử Offline-to-Online:** Đánh giá khả năng hoạt động (đọc Context/State) bất chấp việc mất mạng và tự động phục hồi sự kiện khi có wifi trở lại.

### Risk Mitigation
- **Vấn đề đồng bộ dung lượng lớn:** Cấu trúc Local-first mang tới rủi ro là nếu kho dữ liệu người dùng lên tới hàng Gigabytes, việc tải Zero-cache ban đầu sẽ quá chậm.
- **Fallback (Giải pháp dự phòng):** Sử dụng cơ chế Partial Sync (Đồng bộ một phần) theo Filter/Tag, hoặc phân trang để tối ưu băng thông.

## Web App & API Backend Specific Requirements

### Project-Type Overview
SurfSense kết hợp giữa kiến trúc Single Page Application (SPA) cực kỳ mượt mà trên Next.js và một Backend API vững chắc chuyên trị các tác vụ AI (FastAPI). Hai lớp này giao tiếp qua chuẩn REST/SSE và đặc biệt là hệ thống đồng bộ Local-first từ `@rocicorp/zero`.

### Technical Architecture Considerations
- **Kiến trúc SPA & Real-time:** Next.js sẽ đóng vai trò SPA cung cấp trải nghiệm liền mạch. Trạng thái ứng dụng được đồng bộ real-time mà không cần tải lại trang.
- **Browser Matrix (Hỗ trợ trình duyệt):** Yêu cầu bắt buộc trên trình duyệt hiện đại (Chrome 90+, Safari 15+, Edge 90+) vì dữ liệu Zero-cache nội bộ phụ thuộc vào WebAssembly và IndexedDB.
- **Performance Targets:** Giới hạn Time-to-First-Token (TTFT) ở mức dưới 1 giây. Tốc độ đồng bộ Local-DB dưới 2 giây cho một chunk dữ liệu mới.

### Endpoint Specifications
Cấu trúc API (FastAPI) bao gồm:
- `/api/v1/documents` (REST): Upload files, trích xuất text, đưa vào Celery tasks queuing.
- `/api/v1/chat` (SSE): Trả về luồng streaming answers từ các mô hình học máy theo thời gian thực.
- `/api/zero/sync` (WebSocket/Sync): Endpoint kết nối Rocicorp Zero Client để chia sẻ state.

### Authentication & Rate Limits
- **Auth Model:** Định danh qua token (JWt/Supabase Auth) để phân lập không gian làm việc (Workspace) của mỗi User.
- **Rate Limits:** Giới hạn số Token tải lên và Token trả lời để tránh nguy cơ phá vỡ hệ thống bằng cách lạm dụng Celery Worker.

### Data Schemas & Local Sync
- Cấu trúc Local Schema (phía Client) mô phỏng lại một tập con tối giản (Sub-set) của Remote Schema nhằm phục vụ riêng cho các thao tác Offline (Xem danh sách tài liệu, đọc và truy vấn lịch sử chat).

## Project Scoping & Phased Development

### MVP Strategy & Philosophy
**MVP Approach:** Problem-solving MVP (Tập trung giải quyết cốt lõi vấn đề: RAG cực nhanh nhờ sự hỗ trợ của Rocicorp Zero). Chứng minh được dữ liệu trích xuất thành công và LLM có thể trả lời tức thì (Streaming).
**Resource Requirements:** Nhóm nhỏ (1-2 kỹ sư Full-stack am hiểu kiến trúc Agent và Web Real-time).

### MVP Feature Set (Phase 1)
**Core User Journeys Supported:**
- User Tải File & Chờ trích xuất nền (Background extraction).
- User Hỏi đáp (Chat) dựa trên nội dung file đó với độ trễ (TTFT) < 1 giây.
- Tính năng xem lại lịch sử Chat ngay khi Offline (Zero-cache).
- Đăng ký và thanh toán gói cước Subscription thông qua Stripe để nâng cấp/quản lý hạn mức sử dụng.

**Must-Have Capabilities:**
- Giao diện thao tác Upload File (PDF/TXT cơ bản).
- Pipeline xử lý nền (Celery queue cho Embedding).
- Chức năng Chatbot gọi Stream API từ Agent.
- Local Database (Zero-cache) lưu được `Documents` và `Messages` cơ bản.
- Hỗ trợ duy nhất 1 LLM Provider mạnh mẽ ở giai đoạn đầu (Ví dụ: OpenAI / gpt-4o) để đảm bảo không bị phân tán.
- Tích hợp cổng thanh toán Stripe xử lý Subscriptions và giao diện Pricing/Usage Tracking.

### Post-MVP Features

**Phase 2 (Growth):**
- Đăng nhập nhiều Workspaces (Làm việc nhóm).
- Phân luồng quyền File (RBAC).
- Cho phép người dùng chuyển đổi linh hoạt giữa các mô hình LLM (như Claude 3.5 Sonnet, GPT-4) được cung cấp sẵn, tích hợp thẳng với hệ thống tính phí quota.

**Phase 3 (Expansion):**
- Tích hợp thêm Data Sources (Google Drive, Notion, Slack).
- Mở rộng Agent System: Agent tự biên tập bài viết dài, Agent tổng hợp nghiên cứu (Research Agent).
- API Keys cho bên thứ ba tích hợp (Consumer API access).

### Risk Mitigation Strategy
- **Technical Risks:** Ở MVP, chỉ chạy 1 Worker tập trung với logic Queue đơn giản nhất để giảm rủi ro về Scale.
- **Market Risks:** Đặt một bộ định tuyến trạng thái UI rõ ràng hiển thị "Offline", "Syncing", "Online" để giải tỏa sự khó hiểu của User về Local-first.
- **Resource Risks:** Tận dụng tối đa bộ Docker-compose dựng sẵn và component UI mở. Hạn chế thiết kế lại từ đầu.

## Functional Requirements

### Document Management
- **FR1:** Người dùng có thể tải lên các tệp tài liệu (PDF, TXT) vào không gian làm việc của họ.
- **FR2:** Người dùng có thể xem lại danh sách các tài liệu đã tải lên trước đó.
- **FR3:** Người dùng có thể xem được trạng thái tiến trình trích xuất (Đang đợi, Đang xử lý, Hoàn thành, Lỗi) của một tài liệu.
- **FR4:** Người dùng có thể xóa một tài liệu khỏi không gian làm việc của họ.

### Chat & AI Interaction
- **FR5:** Người dùng có thể tạo một phiên hỏi đáp (Chat Session) mới.
- **FR6:** Người dùng có thể gửi câu hỏi dạng văn bản vào một phiên chat.
- **FR7:** Người dùng có thể nhận được các luồng phản hồi trực tiếp (Streaming responses) từ AI bot theo thời gian thực.
- **FR8:** Người dùng có thể xem lại danh sách các phiên trò chuyện trong quá khứ.
- **FR9:** Người dùng có thể đọc lại toàn bộ nội dung tin nhắn của một phiên trò chuyện cụ thể.

### Offline & Synchronization Capabilities
- **FR10:** Người dùng có thể đọc danh sách tài liệu và nội dung các khung chat cũ ngay cả khi ngắt kết nối hoàn toàn với internet.
- **FR11:** Người dùng có thể nhận biết được trạng thái đồng bộ dữ liệu hiện tại của hệ thống (Ví dụ: Offline, Đang đồng bộ, Đã cập nhật xong).

### Background Processing & System Limits
- **FR12:** Hệ thống có khả năng tự động bóc tách văn bản và tạo Vector Embeddings một cách bất đồng bộ ngầm khi tài liệu mới được tải lên.
- **FR13:** Hệ thống có khả năng chặn yêu cầu (Rate Limit) nếu người dùng sử dụng vượt mức Token cho phép hoặc tải file quá quy định.
- **FR14:** Người dùng có thể xác thực (Authentication) để đăng nhập và bảo vệ dữ liệu thuộc private workspace của họ.

### Pricing & Subscription
- **FR15:** Hệ thống hiển thị bảng giá (Pricing) cho các gói cước với những đặc quyền về giới hạn tải file/nhắn tin khác nhau.
- **FR16:** Người dùng có thể đăng ký gói cước và thanh toán an toàn thông qua cổng Stripe.com.
- **FR17:** Hệ thống tự động theo dõi lượng sử dụng (Usage Tracking) và cập nhật trạng thái gói cước (Active/Canceled) qua Stripe Webhook.

## Non-Functional Requirements

### Performance
- **NFR-P1 (Time to First Token - TTFT):** Hệ thống bắt buộc phải phản hồi ký tự đầu tiên từ AI Agent thông qua SSE dưới 1.5 giây kể từ khi user nhấn Submit.
- **NFR-P2 (Sync Latency):** Thời gian bộ nhớ đệm Zero-cache đồng bộ thay đổi trạng thái (ví dụ một message mới) từ Remote DB về Local IndexedDB không được vượt quá 3 giây.
- **NFR-P3 (Background Processing):** Tác vụ bóc tách văn bản và tạo Vector Embeddings cho một file chuẩn (dưới 5MB) phải được giải quyết xong trên Celery Queue trong vòng dưới 30 giây.

### Security
- **NFR-S1 (Data Segregation):** Row-level Security (RLS) bắt buộc được áp dụng trên cấu trúc Database. Một User ID tuyệt đối không có quyền truy vấn chéo Document List hay Messages của tài khoản khác.
- **NFR-S2 (Local Storage Security):** Toàn bộ dữ liệu Zero-cache lưu ở IndexedDB phía Client sẽ bị xóa hoàn toàn (purged) ngay khi người dùng nhấn "Log Out".

### Scalability
- **NFR-SC1 (Worker Scalability):** Kiến trúc Celery Worker phải được giữ ở trạng thái "Stateless". Hệ thống phải đảm bảo việc thêm n-Workers vào hạ tầng Docker khi hàng đợi đang quá tải sẽ chạy lập tức mà không phải cấu hình lại mã nguồn.

### Reliability
- **NFR-R1 (Offline Tolerance - Chống chịu rớt mạng):** Website phải chịu đựng được việc mất mạng vô thời hạn. Giao diện không được "Trắng màn hình" (White Screen of Death), mà phải cho phép User đọc dữ liệu đã cache mượt mà như đang online.

