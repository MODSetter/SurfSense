# Epic 4: Content Creation & Productivity (Tạo Nội dung & Hiệu suất)

**Trạng thái:** 🚧 ĐANG TRIỂN KHAI (IN PROGRESS)
**Giai đoạn:** Phase 4
**Thời gian:** 2 tuần
**Mức độ ưu tiên:** P2 (Trung bình - Nên có (Nice to Have))

**Tiến độ:**
- ✅ Story 4.1 (Chart Capture): UI hoàn thành (ChartCapturePanel, ChartCaptureWidget, AnnotationTools)
- ✅ Story 4.2 (Thread Generator): UI hoàn thành (ThreadGeneratorPanel, ThreadGeneratorWidget)
- ✅ Story 4.3 (Quick Actions): UI hoàn thành (Context menu in background/index.ts, useContextAction hook)
- ✅ Story 4.4 (Smart Notifications): UI hoàn thành (NotificationSettingsPanel, NotificationsList)
- ✅ Story 4.5 (Keyboard Shortcuts): UI hoàn thành (4 shortcuts: Analyze, Watchlist, Capture, Portfolio)
- ⏳ Backend APIs: 0% (AI thread generation chưa implement)

**Frontend UI: 100% ✅**

**Lưu ý:** Đây là Extension-only features (không có trên Web Dashboard)

---

## Tổng quan Epic

Tạo tools giúp users tạo nội dung (biểu đồ, threads) và cải thiện hiệu suất (thao tác nhanh, thông báo, phím tắt). Tập trung vào **content creators** và **power users**.

**Giá trị kinh doanh (Business Value):**
- **Content Creators:** Công cụ để tạo Twitter threads, chụp ảnh biểu đồ (chart screenshots).
- **Power Users:** Phím tắt, thao tác nhanh để làm việc nhanh hơn.
- **Viral Marketing:** Users chia sẻ nội dung → Marketing miễn phí.
- **User Retention:** Các tính năng hiệu suất → Sản phẩm có độ kết dính cao (Sticky product).

**Điểm khác biệt chính:** Tạo nội dung bằng AI (AI-powered content generation) so với công cụ thủ công.

---

## User Stories

### Story 4.1: Chụp ảnh Biểu đồ có Chú thích (Chart Screenshot with Annotations)
**[FR-EXT-13]**

**Là một** crypto content creator,  
**Tôi muốn** chụp và chú thích biểu đồ (capture và annotate charts),  
**Để** tôi có thể chia sẻ insights trên Twitter/Telegram.

**Tiêu chí chấp nhận (Acceptance Criteria):**
- [ ] Chụp biểu đồ một cú click (One-click chart capture):
  - Capture từ trang DexScreener
  - Tự động phát hiện vùng biểu đồ
  - Screenshot độ phân giải cao
- [ ] Tự động thêm metadata (Auto-add metadata):
  - Token symbol/name
  - Giá hiện tại
  - Thay đổi 24h
  - Volume, thanh khoản
  - Thời gian (Timestamp)
  - Watermark (tùy chọn)
- [ ] Công cụ vẽ (Drawing tools):
  - Đường (trend lines, support/resistance)
  - Mũi tên (chỉ hướng)
  - Nhãn văn bản (Text labels)
  - Hình dạng (tròn, chữ nhật)
  - Fibonacci retracement
- [ ] Kiểu mẫu (Template styles):
  - Dark mode (mặc định)
  - Light mode
  - Neon (crypto aesthetic)
  - Màu tùy chỉnh
- [ ] Tùy chọn xuất (Export options):
  - Định dạng Twitter (1200x675)
  - Định dạng Telegram (vuông)
  - Định dạng Instagram (1080x1080)
  - Kích thước tùy chỉnh
  - Copy vào clipboard
  - Lưu thành file

**UI Design:**
```
┌─────────────────────────────┐
│ 📸 Chart Capture            │
├─────────────────────────────┤
│ [Capture Chart]             │
│                             │
│ Drawing Tools:              │
│ [Line] [Arrow] [Text] [Fib] │
│                             │
│ Style:                      │
│ ● Dark  ○ Light  ○ Neon     │
│                             │
│ Metadata:                   │
│ ☑ Token info                │
│ ☑ Price & change            │
│ ☑ Volume & liquidity        │
│ ☑ Timestamp                 │
│ ☐ Watermark                 │
│                             │
│ Export:                     │
│ [Twitter] [Telegram] [Copy] │
└─────────────────────────────┘
```

**Triển khai kỹ thuật:**
```typescript
interface ChartCapture {
  screenshot: Blob;
  metadata: {
    tokenSymbol: string;
    price: number;
    change24h: number;
    volume: number;
    liquidity: number;
    timestamp: number;
  };
  annotations: {
    type: 'line' | 'arrow' | 'text' | 'shape' | 'fibonacci';
    coordinates: { x: number; y: number }[];
    text?: string;
    color: string;
  }[];
  style: 'dark' | 'light' | 'neon';
}

async function captureChart(): Promise<Blob> {
  // Capture DexScreener chart area
  const chartElement = document.querySelector('.chart-container');
  const canvas = await html2canvas(chartElement);
  return canvas.toBlob();
}

function addAnnotations(canvas: HTMLCanvasElement, annotations: Annotation[]) {
  const ctx = canvas.getContext('2d');
  for (const annotation of annotations) {
    switch (annotation.type) {
      case 'line':
        drawLine(ctx, annotation);
        break;
      case 'arrow':
        drawArrow(ctx, annotation);
        break;
      // ...
    }
  }
}
```

**Files:**
- `lib/capture/chart-capture.ts` (new)
- `sidepanel/capture/ChartCapturePanel.tsx` (new)
- `sidepanel/capture/AnnotationTools.tsx` (new)

---

### Story 4.2: AI tạo Thread Twitter (AI Thread Generator)
**[FR-EXT-14]**

**Là một** crypto content creator,  
**Tôi muốn** AI tạo Twitter threads,  
**Để** tôi có thể chia sẻ insights nhanh chóng.

**Tiêu chí chấp nhận (Acceptance Criteria):**
- [ ] Đầu vào (Input):
  - Token address (tự động điền nếu đang trên DexScreener)
  - Chủ đề Thread (tùy chọn)
  - Độ dài Thread (5-10 tweets)
  - Giọng điệu (Tone) (bullish/neutral/bearish)
- [ ] AI tạo nội dung (AI generation):
  - Phân tích dữ liệu token
  - Tạo cấu trúc thread
  - Bao gồm các thống kê chính
  - Thêm biểu đồ/screenshots
  - Tối ưu hóa cho tương tác (engagement)
- [ ] Cấu trúc Thread:
  - Tweet 1: Hook (thu hút sự chú ý)
  - Tweets 2-4: Phân tích (dữ liệu, insights)
  - Tweets 5-7: Hàm ý/Tác động (Implications - điều này có nghĩa là gì)
  - Tweet 8-9: Kết luận (tóm tắt, CTA)
  - Tweet 10: Tuyên bố miễn trừ trách nhiệm (Disclaimer - tùy chọn)
- [ ] Chỉnh sửa (Editing):
  - Chỉnh sửa từng tweet
  - Sắp xếp lại thứ tự tweets
  - Thêm/xóa tweets
  - Xem trước thread
- [ ] Xuất (Export):
  - Copy tất cả tweets
  - Copy từng tweet
  - Tweet trực tiếp (Twitter API)
  - Lưu nháp (Save as draft)

**UI Design:**
```
┌─────────────────────────────┐
│ 🧵 AI Thread Generator      │
├─────────────────────────────┤
│ Token: BULLA/SOL            │
│ Topic: [Auto]               │
│ Length: [7 tweets] ▼        │
│ Tone: ● Bullish ○ Neutral   │
│                             │
│ [Generate Thread]           │
│                             │
│ Preview:                    │
│ ┌─────────────────────────┐ │
│ │ 1/ 🧵 BULLA is showing  │ │
│ │ massive volume spike... │ │
│ │ [Edit]                  │ │
│ ├─────────────────────────┤ │
│ │ 2/ Contract analysis:   │ │
│ │ ✅ Verified ✅ Renounced│ │
│ │ [Edit]                  │ │
│ ├─────────────────────────┤ │
│ │ ...                     │ │
│ └─────────────────────────┘ │
│                             │
│ [Copy All] [Tweet Now]      │
└─────────────────────────────┘
```

**Triển khai kỹ thuật:**
```typescript
interface ThreadRequest {
  tokenAddress: string;
  chain: string;
  topic?: string;
  length: number;
  tone: 'bullish' | 'neutral' | 'bearish';
}

interface GeneratedThread {
  tweets: {
    number: number;
    content: string;
    type: 'hook' | 'analysis' | 'implication' | 'conclusion' | 'disclaimer';
    includeChart?: boolean;
  }[];
  metadata: {
    tokenSymbol: string;
    keyStats: Record<string, any>;
  };
}

async function generateThread(request: ThreadRequest): Promise<GeneratedThread> {
  // Analyze token
  const analysis = await analyzeToken(request.tokenAddress, request.chain);
  
  // Generate thread with AI
  const prompt = `
    Generate a ${request.length}-tweet thread about ${analysis.symbol}.
    Tone: ${request.tone}
    Include: price, volume, holders, liquidity, sentiment
    Structure: Hook → Analysis → Implications → Conclusion
  `;
  
  const thread = await callAI(prompt, { analysis });
  
  return thread;
}
```

**Files:**
- `lib/content/thread-generator.ts` (new)
- `sidepanel/content/ThreadGeneratorPanel.tsx` (new)

---

### Story 4.3: Thao tác Nhanh & Hiệu suất (Quick Actions & Productivity)
**[FR-EXT-15, FR-EXT-16, FR-EXT-17]**

**Là một** power user,  
**Tôi muốn** có các thao tác nhanh và phím tắt,  
**Để** tôi có thể làm việc nhanh hơn.

**Tiêu chí chấp nhận (Acceptance Criteria):**

#### Menu ngữ cảnh Thao tác nhanh (Quick Actions Context Menu) (FR-EXT-15)
- [ ] Chuột phải vào địa chỉ token → Menu ngữ cảnh
- [ ] Các mục Menu:
  - "Add to Watchlist" (Thêm vào Watchlist)
  - "Analyze Token" (Phân tích Token)
  - "Check Safety" (Kiểm tra an toàn)
  - "Copy Address" (Sao chép địa chỉ)
  - "View on Explorer" (Xem trên Explorer)
  - "View on DexScreener" (Xem trên DexScreener)
- [ ] Hoạt động trên bất kỳ trang web nào (không chỉ DexScreener)
- [ ] Tự động phát hiện định dạng địa chỉ token

#### Thông báo Thông minh (Smart Notifications) (FR-EXT-16)
- [ ] Các mức ưu tiên thông báo:
  - Cao (High): Cảnh báo Rug pull, whale xả hàng
  - Trung bình (Medium): Cảnh báo giá, khối lượng tăng đột biến
  - Thấp (Low): Các cập nhật chung
- [ ] Giờ yên tĩnh (Quiet hours):
  - Đặt lịch ngủ (ví dụ: 11pm - 7am)
  - Không có thông báo trong giờ yên tĩnh
  - Chỉ cảnh báo khẩn cấp (rug pulls)
- [ ] Gom nhóm thông báo (Grouped notifications):
  - Gom theo token
  - Gom theo loại
  - Thu gọn các thông báo tương tự
- [ ] Gom nhóm thông minh (Smart batching):
  - 5+ cảnh báo → 1 thông báo tóm tắt
  - "5 cảnh báo giá đã được kích hoạt"
  - Click để mở rộng
- [ ] Cài đặt theo từng token (Per-token settings):
  - Bật/tắt thông báo
  - Đặt mức ưu tiên
  - Giờ yên tĩnh tùy chỉnh

#### Phím tắt Bàn phím (Keyboard Shortcuts) (FR-EXT-17)
- [ ] Phím tắt toàn cục (Global shortcuts):
  - `Cmd+Shift+S` → Mở side panel
  - `Cmd+Shift+H` → Ẩn side panel
  - `Cmd+Shift+N` → Chat mới
- [ ] Phím tắt ngữ cảnh (khi trên DexScreener):
  - `Cmd+Shift+A` → Phân tích token hiện tại
  - `Cmd+Shift+W` → Thêm vào watchlist
  - `Cmd+Shift+C` → Chụp biểu đồ
  - `Cmd+Shift+T` → Tạo thread
- [ ] Phím tắt Portfolio:
  - `Cmd+Shift+P` → Mở portfolio
  - `Cmd+Shift+R` → Làm mới portfolio
- [ ] Phím tắt tùy chỉnh:
  - User có thể remap phím tắt
  - Không xung đột với phím tắt trình duyệt

**UI Design - Settings:**
```
┌─────────────────────────────┐
│ ⚙️ Productivity Settings    │
├─────────────────────────────┤
│ Notifications:              │
│ Priority: [High] [Med] [Low]│
│ Quiet Hours: 11pm - 7am     │
│ ☑ Group notifications       │
│ ☑ Smart batching            │
│                             │
│ Keyboard Shortcuts:         │
│ Open panel: Cmd+Shift+S     │
│ Analyze: Cmd+Shift+A        │
│ Watchlist: Cmd+Shift+W      │
│ [Customize]                 │
│                             │
│ Quick Actions:              │
│ ☑ Context menu enabled      │
│ ☑ Auto-detect addresses     │
└─────────────────────────────┘
```

**Triển khai kỹ thuật:**
```typescript
// Context menu
chrome.contextMenus.create({
  id: 'analyze-token',
  title: 'Analyze Token',
  contexts: ['selection'],
});

chrome.contextMenus.onClicked.addListener((info, tab) => {
  if (info.menuItemId === 'analyze-token') {
    const address = extractTokenAddress(info.selectionText);
    analyzeToken(address);
  }
});

// Keyboard shortcuts
chrome.commands.onCommand.addListener((command) => {
  switch (command) {
    case 'open-panel':
      chrome.sidePanel.open();
      break;
    case 'analyze-token':
      analyzeCurrentToken();
      break;
    // ...
  }
});

// Smart notifications
interface NotificationSettings {
  priority: 'high' | 'medium' | 'low';
  quietHours: { start: string; end: string };
  grouping: boolean;
  batching: boolean;
  perToken: Record<string, {
    enabled: boolean;
    priority: 'high' | 'medium' | 'low';
  }>;
}

function shouldShowNotification(notification: Notification, settings: NotificationSettings): boolean {
  // Check quiet hours
  if (isQuietHours(settings.quietHours) && notification.priority !== 'high') {
    return false;
  }
  
  // Check per-token settings
  const tokenSettings = settings.perToken[notification.tokenAddress];
  if (tokenSettings && !tokenSettings.enabled) {
    return false;
  }
  
  return true;
}
```

**Files:**
- `background/context-menu.ts` (new)
- `background/keyboard-shortcuts.ts` (new)
- `background/notifications/smart-notifications.ts` (new)
- `sidepanel/settings/ProductivitySettings.tsx` (new)

---

## Các phụ thuộc kỹ thuật (Technical Dependencies)

### Chrome APIs
- `chrome.contextMenus` - Context menu
- `chrome.commands` - Phím tắt bàn phím
- `chrome.notifications` - Thông báo
- `chrome.alarms` - Giờ yên tĩnh

### External Libraries
- `html2canvas` - Chụp biểu đồ
- `fabric.js` - Công cụ vẽ (tùy chọn)

---

## Chiến lược Kiểm thử (Testing Strategy)

### Unit Tests
- [ ] Logic phát hiện địa chỉ token
- [ ] Logic ưu tiên thông báo
- [ ] Tính toán giờ yên tĩnh

### Integration Tests
- [ ] Chụp biểu đồ hoạt động
- [ ] Tạo thread hoạt động
- [ ] Menu ngữ cảnh xuất hiện
- [ ] Phím tắt kích hoạt hành động

### Manual Testing
- [ ] Chụp và chú thích biểu đồ
- [ ] Tạo thread cho token live
- [ ] Test tất cả các phím tắt
- [ ] Xác minh giờ yên tĩnh hoạt động

---

## Định nghĩa hoàn thành (Definition of Done)

- [ ] Tất cả 3 user stories hoàn thành
- [ ] Tất cả tiêu chí chấp nhận được đáp ứng
- [ ] Unit tests pass
- [ ] Integration tests pass
- [ ] Manual testing hoàn thành
- [ ] Code được review
- [ ] Tài liệu được cập nhật

---

## Ghi chú

**Target Users:** Content creators và power users.

**Cơ hội Marketing:** User-generated content (threads, charts) → Viral marketing miễn phí.

**Tất cả Epics Đã Hoàn Thành!** 🎉
