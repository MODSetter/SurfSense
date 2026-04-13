---
stepsCompleted:
  - 1
  - 2
  - 3
  - 4
  - 5
  - 6
  - 7
  - 8
inputDocuments:
  - _bmad-output/planning-artifacts/prd.md
  - _bmad-output/planning-artifacts/architecture.md
  - docs/project-overview.md
---

# UX Design Specification SurfSense

**Author:** Luisphan
**Date:** 2026-04-13

---

## Executive Summary

### Project Vision
SurfSense là nền tảng tìm kiếm và trích xuất ngữ cảnh (Agentic RAG) được thiết kế đặc biệt với kiến trúc Local-first. Sứ mệnh cốt lõi của ứng dụng là mang tới trải nghiệm truy vấn siêu tốc (Time-to-First-Token < 1 giây) và khả năng hoạt động liền mạch ngay cả khi mất kết nối mạng. Hệ thống phá bỏ rào cản về độ trễ của các ứng dụng RAG truyền thống dựa trên cloud nhờ việc đồng bộ hoá ngầm kho dữ liệu trực tiếp về thiết bị người dùng (Zero-cache). 

### Target Users
1. **Người dùng chính (Alex - Data Researcher):** Làm việc với lượng lớn tài liệu phân mảnh, có yêu cầu khắt khe về việc tổng hợp thông tin, trích dẫn chính xác và không có thời gian chờ đợi web load (loading spinners).
2. **Kỹ sư vận hành (Jamie - DevOps) & Nhóm dev tích hợp (Sam - Developer):** Cần giám sát hệ thống phân tán minh bạch, tích hợp AI streaming qua SSE một cách dể hiểu, đảm bảo background workers không làm nghẽn luồng chat.

### Key Design Challenges
1. **Truyền đạt trạng thái kết nối mạng phức tạp (Local-first logic):** Cần chỉ báo UI (indicators) tinh tế thể hiện trạng thái `Syncing`, `Offline`, hoặc `Online` mà không gây rối rắm.
2. **Quản lý kỳ vọng thời gian thực:** Giao diện cần placeholder khéo léo để User an tâm chờ đợi tiến trình trích xuất tài liệu (Embedding) qua Celery.
3. **Hiển thị Streaming và Trích dẫn (Citations):** Giao diện AI chat phát sinh văn bản theo luồng SSE cực mượt, pop-up hiển thị nguồn tham khảo tự nhiên.

### Design Opportunities
1. **Trải nghiệm truy xuất không có 'Loading':** Biến việc chờ đợi thành dĩ vãng nhờ Rocicorp Zero. UI phản hồi tức thì cho các thao tác nội bộ.
2. **Tương tác Desktop-like trên Web:** Áp dụng tư duy tương tác layout mở đa khung giống một phần mềm biên tập nội dung, thay vì danh sách chat cuộn đơn tuyến.

## Core User Experience

### Defining Experience
- **Hành động nòng cốt:** Tiến hành "Trò chuyện mang tính Khám phá" (Exploratory Chat) với kho dữ liệu cá nhân. 
- Mọi thao tác xoay quanh việc hỏi đáp cực kỳ tự nhiên, trong đó văn bản do người dùng tải lên sẽ đóng vai trò bệ đỡ (grounding) vô hình hỗ trợ đằng sau mà không bắt ép người dùng phải thao tác chọn file quá rườm rà.

### Platform Strategy
- **Chiến lược Nền tảng:** Môi trường Web (Browser-based) nhưng mang cảm giác của "Ứng dụng Hệ điều hành/Desktop App". Ưu tiên thiết kế trên Desktop và Tablet vì hành vi "Data Research" thường yêu cầu màn hình lớn để đọc tài liệu song song với khung Chat. 
- Ứng dụng phải hoạt động mượt mà kể cả khi Refresh trang đột ngột nhờ lưu cache sâu.

### Effortless Interactions
- **Các tương tác "Không tốn sức" (Zero-friction):** 
  - Kéo và thả file là tệp sẽ lập tức xuất hiện trong danh sách ảo (Placeholder) mà không cần thấy thanh loading-bar của HTTP Upload.
  - Lướt lại tin nhắn lịch sử của ngày hôm qua không tốn nổi 1ms - cảm giác cuộn mượt như đang scroll bộ nhớ offline.

### Critical Success Moments
- **"Khoảnh khắc Aha" làm nên sự khác biệt:** 
  1. Khi người dùng bấm nút [Gửi câu hỏi], chưa kịp rời tay khỏi chuột, chữ cái đầu tiên (First Token) của AI đã bắt đầu gõ lên màn hình.
  2. Người dùng vô tình mất WiFi, nhưng họ vẫn có thể xem lại toàn bộ câu trả lời AI sinh ra trước đó và đọc tài liệu đính kèm mà không dính logo "Lỗi khủng long".

### Experience Principles
1. **Khởi tác Tức thì (Instant Action):** UI không bao giờ bị "đóng băng" kể cả khi đang có background work. Mọi click đều phải phản hồi state dưới 10ms.
2. **Lùi bước Âm thầm (Graceful Degradation):** Khi mất mạng, giao diện ngầm đổi màu sang trạng thái "Offline" tinh tế. Nút "Tạo Embedding" tự động disable nhẹ nhàng (chứ không báo lỗi popup) và khuyến khích họ đọc lịch sử.
3. **Hiển thị Rành mạch (Clear Provenance):** Không bao giờ để User phải tự đoán AI lấy câu trả lời từ đâu. Tính năng pop-up Trích dẫn (Citation) là trái tim của giao diện hiển thị câu trả lời AI.

## Desired Emotional Response

### Primary Emotional Goals
- **Quyền năng & Tự chủ (Empowered & In Control):** Người dùng cảm thấy họ đang nắm giữ một "bộ não thứ hai" (second brain) có khả năng đọc hiểu khối lượng kiến thức khổng lồ ngay lập tức.
- **Tin tưởng tuyệt đối (Absolute Trust):** Hoàn toàn yên tâm về tính bảo mật (dữ liệu nằm trên máy) và độ tin cậy của câu trả lời (luôn có trích dẫn minh bạch).
- **Kinh ngạc vì sự êm ái (Delightfully Frictionless):** Cảm giác ngạc nhiên, thích thú khi không phải chờ đợi các vòng quay "Loading" nhàm chán như môi trường web truyền thống.

### Emotional Journey Mapping
- **Tiếp xúc ban đầu (First Discovery):** Tò mò và ngỡ ngàng trước tốc độ phản hồi tức thì khi thả file vào (dữ liệu được sync ngầm bằng Rocicorp Zero).
- **Trong quá trình Chat (Core Action):** Cảm giác trôi chảy (Flow state). Suy nghĩ không bị đứt đoạn nhờ AI gõ trả lời không độ trễ.
- **Sau khi hoàn thành (Task Completion):** Thoả mãn và minh mẫn, lấy được câu trả lời kèm nguồn tham chiếu rõ ràng.
- **Sự cố mất mạng/Vào vùng lõm (Disruption/Offline):** Cảm giác an tâm, thở phào nhẹ nhõm vì giao diện chỉ nhẹ nhàng chuyển sang màu "Offline" nhưng mọi dữ liệu chat hay tài liệu vẫn hiện diện để đọc tiếp.

### Micro-Emotions
- **Tự tin (Confidence) > Bối rối (Confusion):** Người dùng luôn biết câu trả lời này được trích xuất từ văn bản gốc nào nhờ cơ chế Highlight Citation.
- **Thư giãn (Relaxed) > Căng thẳng (Anxiety):** Không lo sợ ấn nhầm nút làm mất đi đoạn chat dài, vì mọi state được lưu xuống IndexedDB (PGLite) liên tục.

### Design Implications
- *Nếu muốn tạo sự Tự chủ:* Giấu đi các thiết lập Agent rườm rà, nhường chỗ cho giao diện chat/đọc tài liệu rộng rãi; chỉ hiển thị trạng thái "Đang đồng bộ (Syncing)" là một icon nhỏ gọn không chặn thao tác (Non-blocking UI).
- *Nếu muốn tạo sự Tin tưởng:* Giao diện hiển thị Nguồn trích dẫn (Citations) phải cực kỳ nổi bật, có thể click thẳng vào để nhảy đến đúng trang PDF/đoạn text bên sidebar.
- *Nếu muốn tạo Delight:* Áp dụng các micro-animations (ví dụ: nút "Gửi" biến đổi mượt mà khi AI đang type), nhưng phải giữ cho mọi animation có thời lượng cực ngắn (<150ms).

### Emotional Design Principles
1. **Thiết kế vì trạng thái Dòng chảy (Design for Flow):** Loại bỏ mọi pop-up chặn màn hình.
2. **Minh bạch là Đáng tin (Transparency is Trust):** AI phải luôn "thừa nhận" nguồn gốc kiến thức của nó, nếu không biết thì thể hiện giao diện trung lập thay vì bịa (hallucinate).
3. **Im lặng là Vàng (Quiet Background):** Trạng thái Embeddings hay Syncing để làm việc với dữ liệu lớn phải diễn ra như một nhịp thở nhẹ ở dưới đáy UI, không đòi hỏi sự chú ý.

## UX Pattern Analysis & Inspiration

### Inspiring Products Analysis
1. **Linear:**
   - *Điểm xuất sắc:* Tốc độ tuyệt đối nhờ kiến trúc Local-first (sync ngầm). Cảm giác mượt mà, phản hồi lập tức (zero-latency).
   - *Bài học xử lý:* Không bao giờ dùng thanh Loading (Spinner) chặn luồng làm việc. Sử dụng phím tắt (Cmd+K) để tăng tốc thao tác.
2. **Obsidian / Logseq:**
   - *Điểm xuất sắc:* Quản lý kiến thức mạnh mẽ, cảm giác dữ liệu hoàn toàn thuộc về mình (nằm trên máy tính local). Khả năng chia đa màn hình (Split-pane) để vừa đọc nội dung vừa ghi chú.
3. **Perplexity / Cursor (Tính năng Composer/Chat):**
   - *Điểm xuất sắc:* Minh bạch về nguồn dữ liệu (Sources). Cách trích dẫn (Citations) nhỏ gọn `[1]` nhưng có thể click để tra cứu ngược nguồn gốc câu trả lời rất thuyết phục.

### Transferable UX Patterns
- **Kiểu bố cục Tách viền (Split-Pane Layout):** Góc Chat một bên, góc Đọc/Tra cứu tài liệu (PDF/Text Viewer) một bên. Người dùng không phải chuyển tab để kiểm chứng độ chính xác của câu trả lời.
- **Trích dẫn có tính tương tác (Interactive Citations):** Khi di chuột hoặc click vào số trích dẫn trong câu trả lời báo cáo, đoạn văn bản gốc tương ứng trong file PDF/Text ở pane bên cạnh sẽ tự động scroll tới và highlight.
- **Micro-Sync Indicator (Hiển thị đồng bộ tinh tế):** Học từ Linear - sử dụng một chấm nhỏ hoặc icon xoay góc màn hình để báo hiệu "Đang đồng bộ" (Syncing lên PGlite/Local) thay vì khoá màn hình.

### Anti-Patterns to Avoid
- **The Chatbot Island (Chatbot đơn độc):** Chỉ thiết kế một khung chat ở giữa màn hình mà giấu nhẹm đi khu vực hiển thị tài liệu gốc. Điều này tước mất công cụ đối chiếu của người dùng.
- **Blocking Spinners (Vòng lặp chờ đợi):** Bắt người dùng nhìn Icon xoay màn hình trong 10-15 giây để chờ AI tạo Embedding hoặc khi mạng chậm.
- **Blackbox AI (AI Hộp đen):** Trả lời một câu dài nhưng không có bất kỳ dòng trích dẫn nào, khiến người dùng mất niềm tin nếu phát hiện ra ảo giác (hallucination).

### Design Inspiration Strategy
- **Điều sẽ Áp dụng (Adopt):** 
  - Mô hình UI phản hồi tức thời (Optimistic UI) cho các thao tác nội bộ và thêm file.
  - Card/Badge hiển thị rõ ràng Nguồn (Sources) được dùng cho mỗi response.
- **Điều sẽ Biến tấu (Adapt):** 
  - Đưa Layout Split-pane vào Web truyền thống (Dùng cơ chế kéo thanh chia hoặc tự động bật mở ngăn tài liệu khi người dùng click vào trích dẫn).
- **Điều sẽ Tránh xa (Avoid):** 
  - Ẩn quá trình Index dữ liệu. Chúng ta phải "cho thấy âm thầm" việc tài liệu đang được học (Indexed) thông qua một thanh tiến trình nhỏ gắn liền với từng file cụ thể, không ảnh hưởng chat chính.

## Design System Foundation

### 1.1 Design System Choice
**shadcn/ui + Tailwind CSS (Themeable/Custom Hybrid)**

### Rationale for Selection
- **Kiểm soát tuyệt đối (Total Control):** Khác với các thư viện đóng gói sẵn (như Ant Design hay MUI), `shadcn/ui` cho phép chúng ta cài đặt thẳng mã nguồn component (với Tailwind) vào dự án. Điều này tối quan trọng để Frontend Dev có thể can thiệp sâu vào các micro-animation, đáp ứng tiêu chí "Khởi tác Tức thì" (Instant Action) dưới 150ms mà không bị xung đột thư viện.
- **Tốc độ và Hiệu suất:** Dựa trên nền tảng Radix UI Primitives, các logic phức tạp như Focus, Keyboard Navigation đều được xử lý chuẩn mực. Điều này hoàn toàn thích hợp với mục tiêu theo đuổi kiến trúc Local-first (Rocicorp Zero), nơi mọi tương tác UI đều được phản hồi lập tức.
- **Phong cách Hiện đại:** Mặc định `shadcn/ui` mang hơi hướng thẩm mỹ "sạch", trung tính và hiện đại, rất tương đồng với trải nghiệm "Desktop-like" của Linear hay Notion mà chúng ta đang nhắm tới.

### Implementation Approach
- Các component cơ bản (Button, Dialog, Toast, Tooltip) sẽ được khởi tạo qua shadcn CLI để tái sử dụng chuẩn kiến trúc.
- Riêng hệ thống **Tách viền (Split-Pane)** kết hợp không gian Chat và Đọc Tài liệu sẽ được custom chuyên sâu bằng thư viện chuyên dụng cho resizable panel (ví dụ `react-resizable-panels`) kết hợp Tailwind để chịu tải tốt nhất khi nội dung AI đang streaming thay đổi DOM liên tục.

### Customization Strategy
- **Design Tokens:** Tinh chỉnh `tailwind.config.ts` để gán màu sắc trực quan cho các trạng thái mạng (Online/Syncing/Offline) dưới dạng Non-blocking UI.
- **Typography:** Sử dụng Font chữ tối ưu cho việc "Nghiên cứu/Đọc" (ví dụ: Inter, hoặc các font phổ biến cho tài liệu học thuật) kết hợp với phông Monospace riêng cho các đoạn Code / Raw text.
- **Animation Constraints:** Tạo quy tắc khắt khe về thời lượng chuyển động (VD: Khai báo `@layer utilities` các class `duration-fast` < 150ms) để giữ cho cảm giác mọi thứ thao tác đều lập tức ngay dưới tay người dùng, không bao giờ bắt họ phải chờ một cái Dialog mất 0.5s để hiện lên.

## 2. Core User Experience

### 2.1 The Defining Experience
**Trò chuyện Phân tích Định hướng Nguồn (Source-grounded Analytical Chat)**
Mọi thứ trong SurfSense xoay quanh một tương tác vàng: *Hỏi một câu phức tạp dựa trên bộ tài liệu cá nhân, và ngay lập tức nhận về luồng văn bản trả lời đi kèm các trích dẫn (citations) trực quan.* Nếu làm đúng tương tác này, người dùng sẽ cảm thấy họ đang nắm trong tay một đội ngũ trợ lý nghiên cứu làm việc song song không mệt mỏi.

### 2.2 User Mental Model
- **Thói quen hiện tại (Status Quo):** Người dùng phải mở hàng chục tab PDF, dùng Ctrl+F tìm từ khoá, copy-paste từng đoạn sang ChatGPT/Claude để hỏi, và sau đó hoang mang vì AI có thể tóm tắt dông dài hoặc bịa đặt (hallucinate). Trải nghiệm rất chắp vá.
- **Kỳ vọng đối với SurfSense:** "Tôi gom 10 file báo cáo thả vào app, tôi hỏi một câu, hệ thống đọc cả 10 file đó và trả cho tôi câu trả lời được đúc kết lại, đồng thời **chỉ rõ luôn là lấy từ dòng nào của file nào**."

### 2.3 Success Criteria
1. **Khẳng định Bản sắc:** Người dùng ngay lập tức nhận ra đây là công cụ "Nghiên cứu tài liệu" (Research), chứ không phải công cụ tán gẫu (General Chat) như ChatGPT.
2. **Speed-to-First-Token:** Kéo thả tệp xong, click hỏi, phản hồi (Token) đầu tiên của AI xuất hiện tức thì nhờ cơ chế cache/sync tối ưu.
3. **Citations == Trust (Trích dẫn là Niềm tin):** Trích dẫn không chỉ ghi dạng text `[Source: document.pdf]`, mà phải là một Badge tương tác. Click vào Badge, nguyên bản tài liệu bật lên đúng ở dòng đó.

### 2.4 Novel UX Patterns
- **Established (Kế thừa mẫu quen thuộc):** Ô nhập câu hỏi Chat kiểu bong bóng (giống ChatGPT) để người dùng không phải học cách dùng mới.
- **Novel (Sự đột phá khác biệt):** Layout động (Dynamic Split-pane). Khi chat bình thường là 1 khung trung tâm rộng rãi. Khi click vào 1 trích dẫn `[2]`, màn hình mượt mà trượt sang trái, mở ra nửa màn hình bên phải là trình đọc PDF (PDF Viewer) scroll sẵn tới đúng vùng được highlight.

### 2.5 Experience Mechanics
1. **Initiation (Bắt đầu):** Người dùng kéo/thả một tệp PDF vào khung chat. File lập tức bay vào mục "Current Collection" một cách ảo diệu (Syncing chạy ngầm, không có thanh loading tròn chặn màn hình).
2. **Interaction (Tương tác thao tác):** Người dùng gõ "Nguyên nhân chính là gì?" và Enter. Token được lưu tức thì xuống db local (PGLite) bằng Rocicorp Zero, giao diện đẩy bong bóng tin nhắn lên ngay lập tức mà không khựng 1 giây.
3. **Feedback (Phản hồi thị giác):** Response trả về dồn dập (streaming). Cứ mỗi lần AI rải xong một fact (sự kiện), một thẻ Badge `[1]` nhỏ nhắn hiện ra phía cuối câu.
4. **Completion (Khoảnh khắc Aha):** Người dùng click dứt khoát vào `[1]`. Giao diện tách đôi, file PDF/Text gốc hiện ra tô vàng đúng câu AI vừa trích dẫn. Người dùng gật gù tin tưởng và yên tâm gõ tiếp câu hỏi số 2.

## Visual Design Foundation

### Color System
**Chiến lược "Trung tính & Một điểm nhấn" (Monochrome with Accent)**
Khác với ứng dụng giải trí, SurfSense là công cụ phân tích tài liệu, mắt người dùng sẽ phải đọc chữ liên tục. Sự rườm rà về màu sắc sẽ làm người dùng phân tâm.
- **Base (Nền tảng):** Sử dụng dải màu `Zinc` hoặc `Slate` của Tailwind. Chế độ Dark Mode sẽ là chủ đạo (với nền `#09090b`), tạo cảm giác "hacker/researcher" bí ẩn nhưng sang trọng. Light Mode sử dụng nền trắng `#ffffff` tinh khiết.
- **Accent (Điểm nhấn):** `Indigo` (Tím xanh) hoặc `Teal` (Xanh cổ vịt). Màu Accent chỉ xuất hiện ở các vị trí: Nút thao tác chính (Call-to-Action), viền Focus, và đặc biệt là **Màu của Thẻ Trích dẫn (Citations)** để thu hút sự chú ý.
- **Semantic/Status Indicators:** Bỏ qua các khối màu to. Chỉ sử dụng glow (đốm sáng) hoặc viền mỏng:
  - *Syncing:* Ánh sáng vàng cam (Amber glow) nhẹ nhàng ở góc màn hình.
  - *Offline:* Các nút bị vô hiệu hoá chuyển sắc xám nhạt (Muted Gray).
  - *Success:* Xanh ngọc (Emerald) vụt sáng rồi tắt khi file được Vector hoá thành công.

### Typography System
**Tập trung vào Tính Dễ Đọc (High Legibility)**
- **Primary Typeface (UI & Giao diện):** `Inter` hoặc `Geist Sans`. Font chữ không chân, trung tính, hiện đại, đảm bảo UI nhìn gọn gàng ở kích thước 12-14px.
- **Reading Typeface (Văn bản & Trả lời AI):** Có thể giữ nguyên `Inter` nhưng tăng `line-height` lên `1.6` (leading-relaxed) để tối ưu cho việc đọc đoạn văn dài.
- **Monospace Typeface:** `JetBrains Mono` hoặc `Fira Code`. Dành riêng cho giao diện hiển thị Raw Text, đoạn Code, hoặc Metadata của tài liệu, tạo sự phân biệt rõ ràng với văn bản văn xuôi.

### Spacing & Layout Foundation
**Hệ thống Lưới không gian (Airy vs Dense)**
- **Base Grid:** Dựa theo hệ số 8px mặc định của Tailwind (VD: 8, 16, 24, 32px).
- **Phân bổ không gian:** 
  - *Khu vực Chat:* Cần khoảng không thoáng đãng (Airy) giữa các tin nhắn (padding lớn, margin lớn) để làm chậm nhịp độ tiếp nhận thông tin, giúp người dùng "thở" khi xử lý dữ liệu phức tạp.
  - *Khu vực Đọc PDF/Document (Bên phải):* Mật độ cao (Dense/Compact) để chứa được nhiều chữ nhất có thể trên một khung hình, tối ưu việc dò tìm.
- **Split-Pane Layout:** Trên màn hình Desktop (>1024px), giới hạn khung Chat ở mức maxWidth cố định (khoảng 800px), toàn bộ phần hẹp dư thừa rẽ băng nhường chỗ cho khung Document Panel.

### Accessibility Considerations
- **Contrast Ratios (Độ Tương phản):** Tất cả Text (đặc biệt là nội dung AI sinh ra) phải đạt chuẩn WCAG AA (nhịp tương phản 4.5:1). Chữ xám trên nền xám đen cần kiểm tra kỹ.
- **Focus States (Dành cho Pro Users):** Vì phần mềm đề cao phím tắt (Cmd+K), hiệu ứng Focus (ví dụ viền `ring-2 ring-indigo-500`) phải nổi bật rõ ràng khi người dùng dùng phím `Tab` duyệt qua các Citation.

<!-- UX design content will be appended sequentially through collaborative workflow steps -->
