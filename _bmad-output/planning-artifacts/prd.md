---
stepsCompleted: []
inputDocuments:
  - _bmad-output/analysis/brainstorming-session-2026-02-01.md
  - _bmad-output/analysis/brainstorming_summary_vi.md
  - strategic_context_synthesis.md
  - strategic_recommendation.md
  - market_landscape_analysis.md
  - business_model_analysis.md
  - disruption_opportunities_analysis.md
  - crypto_copilot_implementation_roadmap.md
  - crypto_copilot_roadmap_vi.md
  - task.md
workflowType: 'prd'
---

# Tài liệu Yêu cầu Sản phẩm - SurfSense 2.0 (Crypto Co-Pilot)

**Tác giả:** Luis & Antigravity  
**Ngày:** 2026-02-01  
**Trạng thái:** DRAFT (Bản nháp)

## 1. Bối cảnh Chiến lược & Tầm nhìn

### 1.1. Bối cảnh
SurfSense 2.0 đại diện cho một **bước chuyển mình sống còn ("Bet-the-Company" pivot)** từ một công cụ mã nguồn mở đa năng sang một **Nền tảng Crypto Intelligence ưu tiên AI (AI-First)** chuyên sâu. Quyết định này được thúc đẩy bởi "cửa sổ thị trường" độc nhất (Bull Run 2026) và cơ hội trong 6-12 tháng để xây dựng vị thế trước khi các đối thủ lớn bắt kịp.

**Quyết định Chiến lược:** **CONDITIONAL GO** (Đã duyệt ngày 1/2/2026) cho chiến lược "AI-First MVP".

### 1.2. Tầm nhìn
Xây dựng **AI Co-pilot dẫn đầu thị trường cho crypto traders**, giúp chuyển đổi dữ liệu thô thành thông tin tình báo chủ động, có thể hành động ngay. Chúng ta đang chuyển dịch từ "tổng hợp dữ liệu" (như DexTools/DexScreener) sang "Tình báo AI" (Dự đoán, Mô hình, Ngôn ngữ tự nhiên).

**Giá trị Cốt lõi:**
> *"AI Analyst của riêng bạn - tìm kiếm cơ hội, phát hiện lừa đảo (scams), và giải thích thị trường ngay cả khi bạn đang ngủ."*

### 1.3. Tiêu chí Thành công (Năm 1)
*   **User Traction:** 100-500 người dùng trả phí (tập trung vào tăng trưởng Organic).
*   **Doanh thu:** $5K-25K MRR ($60K-300K ARR).
*   **Sản phẩm:** Độ chính xác dự đoán >70%, time-to-insight <5 phút.
*   **Sự khác biệt:** Kiểm chứng được "AI Moat" (mô hình độc quyền/fine-tuned).

---

## 2. Vấn đề cần giải quyết (Jobs-to-be-Done)

Traders hiện đang đối mặt với **Quá tải Thông tin** và **Quy trình làm việc thụ động**.
1.  **Tìm kiếm Cơ hội:** "Giúp tôi tìm các giao dịch có lời trước khi chúng pump." (Hiện tại tốn >10 giờ/tuần để nghiên cứu thủ công).
2.  **Tránh Lừa đảo:** "Bảo vệ tôi khỏi rug pulls." (Các công cụ phát hiện honeypot hiện tại quá thụ động và thiếu sót).
3.  **Hiểu Thị trường:** "Giải thích tại sao token này đang biến động." (Công cụ hiện tại chỉ hiện biểu đồ mà thiếu ngữ cảnh).
4.  **Quản lý Danh mục:** "Báo cho tôi khi nào nên bán." (Công cụ hiện tại quá tĩnh).

---

## 3. Phạm vi & Định nghĩa MVP (Enhanced Core)

**Chiến lược:** AI-First MVP.
**Thời gian:** 12 Tuần (Triển khai Tốc độ cao).
**Ngân sách:** $18K (Tận dụng team hiện tại & các gói free tier).

### 3.1. Trong Phạm vi (In-Scope - MVP)
*   **Nguồn dữ liệu:** DexScreener (Giá/Volume), DefiLlama (TVL/Yields).
*   **Tính năng Thông minh (Intelligence):** 
    *   Smart Alerts (Cảnh báo dựa trên bất thường ML, không chỉ là ngưỡng cài đặt).
    *   Natural Language Queries (Truy vấn ngôn ngữ tự nhiên: "Show me Solana tokens with heavy buying").
    *   Rug Pull Detection (So khớp mẫu chủ động).
*   **Giao diện Chính (Critical):** **Browser Extension (Chrome)** chạy overlay trực tiếp trên DexScreener.
*   **Mô hình thu phí:** Freemium + Gói Pro $49/tháng.

### 3.2. Ngoài Phạm vi (Out-of-Scope - V1)
*   Tích hợp QuickNode Premium (Dùng fallback tự host nếu cần).
*   Phân tích Cảm xúc Mạng xã hội (Social Sentiment Analysis) chuyên sâu (Sẽ bắt đầu đơn giản trước).
*   Native Mobile App (Chỉ làm Web bản đầu).
*   Mô hình Dự đoán Nâng cao (Dành cho Phase 2).

---

## 4. Tóm tắt Kế hoạch Triển khai
*   **Phase 1 (Tuần 1-2):** Nền tảng (Connectors + RAG Pipeline).
*   **Phase 2 (Tuần 3-4):** Trí tuệ (Intelligence: NLP + Alerts).
*   **Phase 3 (Tuần 5-6):** Đánh giá & Ra mắt Private Beta (20 Users).
*   **Phase 4 (Tuần 7-12):** Public Beta & Cải tiến (Iteration).

---

## 5. Lợi thế Cạnh tranh ("The Moat")

| Đối thủ | Mô hình của họ | "Lợi thế Đặc biệt" của chúng ta (The Wedge) |
| :--- | :--- | :--- |
| **DexScreener / DexTools** | **Data Aggregators (Thụ động).** Tốt để xem biểu đồ, tệ ở câu hỏi "Tại sao?". Người dùng phải tự phân tích dữ liệu thô. | **Proactive Intelligence.** Chúng ta không chỉ hiện biểu đồ; chúng ta giải thích *tại sao* nó biến động (Tin tức + On-chain + Xã hội). "Analyst của bạn, không chỉ là Terminal." |
| **GMGN.ai** | **"Degen Tooling" (Phức tạp).** UI quá tải, tập trung vào theo dõi ví thô. Khó sử dụng cho người mới. | **Sự đơn giản kiểu Apple.** Giao diện Ngôn ngữ Tự nhiên ("Token này có an toàn không?"). Bình dân hóa việc theo dõi "Smart Money" cho trader phổ thông. |
| **Perplexity / ChatGPT** | **Generalists (Đa năng).** Tốt cho định nghĩa, tệ cho ứng dụng crypto thời gian thực. Hay bị ảo giác (hallucinations) về giá. | **Chuyên biệt hóa theo chiều dọc.** RAG pipeline được tinh chỉnh riêng cho Dữ liệu Crypto. Kiến trúc "Zero-hallucination" cho giá cả/chỉ số. |

**Cốt lõi Moat của chúng ta:** **Khả năng Tiếp cận + Ngữ cảnh.** Mang phân tích "Tại sao" chuẩn tổ chức đến quy trình "Cái gì" của nhà đầu tư nhỏ lẻ.

---

## 6. Yêu cầu Chức năng ("Enhanced Core" MVP)

### 6.1. Lớp Trí tuệ (The Brain)
*   **[FR-INT-01] Truy vấn Ngôn ngữ Tự nhiên:** 
    *   Người dùng hỏi: "Show me trending Solana memes with >$10k liquidity created in the last hour."
    *   Hệ thống dịch sang: DexScreener API filters + SQL Query.
*   **[FR-INT-02] Kiểm tra Rug Pull Cơ bản:** 
    *   Người dùng hỏi: "Is $TOKEN safe?"
    *   Hệ thống kiểm tra: Trạng thái khóa LP, % Top 10 Holders, Mint Authority (qua API data).
*   **[FR-INT-03] Cảnh báo "Smart":** 
    *   Hệ thống đẩy thông báo cho các *bất thường*, không chỉ là chạm ngưỡng giá.
    *   Ví dụ: "Phát hiện sự phân kỳ giữa Volume/Liquidity trên $TOKEN."

### 6.2. Lớp Dữ liệu (The Foundation)
*   **[FR-DAT-01] Tích hợp DexScreener:** 
    *   Giá Real-time, Volume, Liquidity, FDV, Tuổi Pair.
    *   Hỗ trợ chuỗi Solana, Base, Ethereum (Phase 1).
*   **[FR-DAT-02] Tích hợp DefiLlama:** 
    *   Số liệu TVL cho các truy vấn về "Bối cảnh Vĩ mô" (Macro Context).

### 6.3. Lớp Giao diện (The Dashboard & Extension)

#### Browser Extension - Chrome Side Panel

> **UX Strategy:** "Extension for Quick Actions, Frontend for Management"
> 
> Extension tập trung vào **quick & contextual** actions, tận dụng tối đa frontend hiện có cho management tasks.

##### Phase 1: Core Infrastructure (✅ COMPLETED)

**[FR-EXT-01] Side Panel Architecture:**
*   Extension mở dưới dạng **Chrome Side Panel** (không phải popup nhỏ).
*   Chiều rộng mặc định: 400px, có thể resize từ 300-600px.
*   Luôn hiển thị bên phải màn hình, không che khuất nội dung chính.
*   Tự động mở khi click vào extension icon.

**[FR-EXT-02] AI Chat Interface (Tái sử dụng Frontend UI):**
*   Tích hợp đầy đủ `@assistant-ui/react` Thread component từ frontend web.
*   Hỗ trợ streaming responses với thinking steps visualization.
*   Attachment handling (images, files, screenshots).
*   Tool UIs: Display images, link previews, webpage scraping.
*   Chat history persistence sử dụng Plasmo Storage + Backend API sync.

**[FR-EXT-03] Page Context Detection:**
*   Tự động nhận diện loại trang đang xem:
    *   DexScreener → Extract token data (address, price, volume, liquidity)
    *   CoinGecko → Extract coin info
    *   Twitter/X → Extract crypto discussions
    *   Generic → Basic page info
*   Inject context vào chat: "You are viewing $TOKEN on Solana..."
*   Pre-populate relevant questions dựa trên page type.

**[FR-EXT-04] DexScreener Smart Integration:**
*   **Token Info Card:** Hiển thị ở top của side panel khi detect DexScreener page:
    ```
    ┌─────────────────────────────┐
    │ 🪙 BULLA/SOL               │
    │ $0.0001  📈 +15%           │
    │ Vol: $10K | Liq: $5K       │
    │ [Safety Check] [Holders]   │
    └─────────────────────────────┘
    ```
*   **Quick Actions:**
    *   "Is this token safe?" → Tự động check LP lock, mint authority, holder distribution
    *   "Show top holders" → Query blockchain data
    *   "Price prediction" → AI analysis dựa trên historical data
*   **Auto-context Chat:** Khi user hỏi "this token", AI tự hiểu là token đang xem.

**[FR-EXT-05] Quick Capture:**
*   Giữ tính năng capture page hiện tại.
*   Sticky button ở bottom của side panel: "📸 Save Current Page"
*   Lưu vào search space đã chọn.
*   Hiển thị toast notification khi save thành công.

**[FR-EXT-06] Settings Sync với Frontend:**
*   **Compact Settings Dropdown:**
    ```
    ┌─────────────────────────────┐
    │ ⚙️ Quick Settings           │
    ├─────────────────────────────┤
    │ Model: GPT-5.1         [▼]  │ ← Read-only, sync từ backend
    │ Search Space: My Space [▼]  │ ← Read-only, sync từ backend
    │                             │
    │ [🔗 Manage Connectors]      │ ← Open frontend tab
    │ [📚 View All Chats]         │ ← Open frontend tab
    │ [⚙️ Full Settings]          │ ← Open frontend tab
    └─────────────────────────────┘
    ```
*   **State Sync:** Extension ↔ Backend API ↔ Frontend
    *   Model selection (read-only in extension)
    *   Search space (read-only in extension)
    *   Enabled connectors (read-only in extension)
    *   Chat history (bidirectional sync)
*   **Deep Links:** "Manage X" buttons → Open frontend in new tab

##### Phase 2: Smart Monitoring & Alerts

**[FR-EXT-07] Real-time Price Alerts:**
*   **Watchlist Management:** Quản lý danh sách token theo dõi ngay trong side panel.
*   **Alert Types:**
    *   Price alerts: Above/Below/Change %
    *   Volume spike alerts (unusual trading activity)
    *   Liquidity change alerts
*   **Browser Notifications:** Gửi notification ngay cả khi tab đóng.
*   **Sound Alerts:** Có thể bật/tắt âm thanh cảnh báo.

**[FR-EXT-08] Whale Activity Tracker:**
*   Monitor large transactions (> $10K, $50K, $100K).
*   Detect wallet clustering (same entity).
*   Track smart money wallets.
*   Alert on unusual whale activity.
*   Show transaction details in side panel.

**[FR-EXT-09] Rug Pull Early Warning System:**
*   **Risk Indicators:**
    *   Monitor LP removal
    *   Track mint authority changes
    *   Detect suspicious holder patterns
    *   Check contract ownership
*   **Risk Score Display:**
    ```
    ⚠️ RUG PULL WARNING
    🔴 LP unlocked (High Risk)
    🟡 Top holder owns 40%
    🟢 Contract verified
    Risk Score: 7/10 (High)
    Recommendation: AVOID
    ```

##### Phase 3: Trading Intelligence

**[FR-EXT-10] One-Click Token Analysis:**
*   **Comprehensive Analysis:**
    *   Contract analysis (verified, renounced, etc.)
    *   Holder distribution
    *   Liquidity analysis
    *   Trading volume patterns
    *   Price history & trends
    *   Social sentiment (Twitter, Telegram)
*   **AI-Generated Summary:** Tóm tắt insights chính trong 2-3 câu.
*   **Quick Access:** Button "Analyze This Token" trên Token Info Card.

**[FR-EXT-11] Smart Entry/Exit Suggestions:**
*   Support/Resistance levels
*   Fibonacci retracement
*   Volume profile analysis
*   AI-predicted price targets
*   Risk/Reward ratio calculation

**[FR-EXT-12] Portfolio Tracker Integration:**
*   Connect wallet (MetaMask, Phantom, etc.)
*   Auto-detect holdings
*   Real-time P&L tracking
*   Performance analytics
*   **Side Panel Tab:** Dedicated "Portfolio" view

##### Phase 4: Content Creation & Productivity

**[FR-EXT-13] Chart Screenshot with Annotations:**
*   One-click chart capture from DexScreener
*   Auto-add price, volume, indicators
*   Drawing tools (lines, arrows, text)
*   Template styles (Dark/Light/Neon)
*   Export to Twitter/Telegram format

**[FR-EXT-14] AI Thread Generator:**
*   Analyze token data
*   Generate Twitter thread structure (5-10 tweets)
*   Include charts, stats, insights
*   Optimize for engagement
*   One-click copy to clipboard

**[FR-EXT-15] Quick Actions Context Menu:**
*   Right-click on token address → Quick actions
*   "Add to Watchlist"
*   "Analyze Token"
*   "Check Safety"
*   "Copy Address"
*   "View on Explorer"

**[FR-EXT-16] Smart Notifications Management:**
*   Notification priority levels (High/Medium/Low)
*   Quiet hours (no alerts during sleep)
*   Grouped notifications
*   Smart batching (5 alerts → 1 summary)
*   Per-token notification settings

**[FR-EXT-17] Keyboard Shortcuts:**
*   `Cmd+Shift+S` → Open side panel
*   `Cmd+Shift+A` → Analyze current token
*   `Cmd+Shift+W` → Add to watchlist
*   `Cmd+Shift+C` → Capture chart
*   `Cmd+Shift+P` → Portfolio view

##### Feature Responsibility Matrix

> **Strategy Update (2026-02-04):** Extension = Full Features
>
> Extension không chỉ là "Quick Actions" mà là **full-featured crypto co-pilot** với đầy đủ tính năng.
> Web Dashboard là nơi quản lý settings và xem analytics chi tiết.

| Feature | Extension | Frontend Dashboard | Sync Method |
|---------|-----------|-------------------|-------------|
| **Model Selection** | 📖 Read-only dropdown | ✏️ Full selector | Backend API |
| **Search Space** | 📖 Read-only dropdown | ✏️ Full management | Backend API |
| **Chat** | ✅ Full chat UI | ✅ Full chat UI | Backend API |
| **Connectors** | 📖 Use only | ✏️ Setup & manage | Backend API |
| **Documents** | 👁️ View in chat | ✏️ Full management | Backend API |
| **Watchlist** | ✅ Full management | ✅ Full management | Backend API |
| **Alerts** | ✅ Full management | ✅ Full management | Backend API |
| **Token Analysis** | ✅ Full analysis | ✅ Full analysis (via AI chat) | Backend API |
| **Whale Activity** | ✅ Full tracking | ✅ Full tracking (via AI chat) | Backend API |
| **Trading Suggestions** | ✅ Full suggestions | ✅ Full suggestions (via AI chat) | Backend API |
| **Portfolio Tracker** | ✅ Full tracking | ✅ Full tracking | Backend API |
| **Chart Capture** | ✅ Full capture + annotations | ❌ N/A (Extension-only) | Local |
| **Thread Generator** | ✅ Full generation | ❌ N/A (Extension-only) | Local |
| **Context Detection** | ✅ Auto-detect tokens | ❌ N/A (Extension-only) | Local |
| **Floating Button** | ✅ Quick access | ❌ N/A (Extension-only) | Local |
| **Settings** | 📖 Quick settings | ✏️ Full settings | Backend API |
| **Analytics** | 👁️ Basic stats | ✅ Full analytics | Backend API |

**Legend:**
- ✅ Full feature (create, edit, delete, view)
- ✏️ Full control (create, edit, delete)
- 📖 Read-only (view/select only)
- 👁️ View only
- ❌ N/A (Not applicable)

**Extension-only Features:**
- Chart Capture with Annotations (cần truy cập DOM của trang)
- AI Thread Generator (tối ưu cho workflow trên browser)
- Context Detection (cần content script)
- Floating Quick Action Button (cần inject vào trang)

**Web Dashboard Focus:**
- Full Settings Management
- Detailed Analytics & Reports
- Connector Setup & Configuration
- Document Management

#### Web Dashboard (Secondary - Existing)
*   **[FR-UI-01] Chat Management:** Xem lịch sử chat, manage search spaces.
*   **[FR-UI-02] Settings:** API key, preferences, connector configs.
*   **[FR-UI-03] Analytics:** Usage stats, token watchlist.


---

## 7. User Stories (Quy trình của Trader)

### Story 1: Khám phá (Discover - "Morning Brew")
> **Là một** Momentum Trader,
> **Tôi muốn** hỏi "Có gì đang hot trên hệ Base ngay lúc này?"
> **Để** tôi có thể tìm cơ hội mà không cần lướt thủ công qua 500+ token rác trên DexScreener.

### Story 2: Thẩm định (Vet - "Safety Check")
> **Là một** Nhà đầu tư Thận trọng,
> **Tôi muốn** dán địa chỉ contract và hỏi "Kiểm tra giúp các dấu hiệu cờ đỏ (red flags),"
> **Để** tôi không mất tiền vào các vụ rug pulls rõ ràng (token cho phép mint thêm, LP chưa khóa) mà tôi có thể bỏ sót trong lúc vội.

### Story 3: Giám sát (Monitor - "Sleep Aid")
> **Là một** Swing Trader bận rộn,
> **Tôi muốn** đặt cảnh báo AI cho việc "Cá voi bán tháo lượng lớn" trên vị thế của tôi,
> **Để** tôi có thể ngủ ngon mà không cần check điện thoại mỗi 5 phút, biết rằng AI đang canh chừng *hành vi*, chứ không chỉ là giá.

---

## 8. Kiến trúc Kỹ thuật (Cấp cao)
*   **Frontend (Extension):** **Plasmo Framework** (React/TypeScript). Tối ưu cho Chrome Extensions, dễ mở rộng.
*   **Frontend (Web/Mobile):** Next.js (Secondary - Dùng cho trang quản lý tài khoản/Landing page).
*   **Backend:** Python (FastAPI) - Quan trọng cho stack AI/Data.
*   **AI Engine:** 
    *   LLM: Gemini 1.5 Flash (Chi phí/Tốc độ) hoặc GPT-4o-mini.
    *   RAG: Supabase (pgvector).
    *   Agent Framework: LangGraph (cho suy luận đa bước).
*   **Data Ops:** 
    *   Dịch vụ Polling cho DexScreener API (Tuân thủ rate limits).
    *   Redis để cache dữ liệu token nóng nhằm giảm chi phí API.
