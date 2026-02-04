# Epic 2: Smart Monitoring & Alerts (Giám sát & Cảnh báo Thông minh)

**Trạng thái:** 🚧 ĐANG TRIỂN KHAI (IN PROGRESS)
**Giai đoạn:** Phase 2
**Thời gian:** 2 tuần
**Mức độ ưu tiên:** P0 (Nghiêm trọng - Risk Protection)

**Tiến độ:**
- ✅ Extension UI: 90% hoàn thành (WatchlistPanel, AlertConfigModal, WhaleActivityFeed, SafetyScoreDisplay)
- ✅ Extension Widgets: 100% hoàn thành (WatchlistWidget, AlertWidget, WhaleActivityWidget)
- ✅ Web Tool UIs: 100% hoàn thành (WatchlistDisplayToolUI, AlertConfigurationToolUI, WhaleActivityToolUI)
- ⏳ Backend APIs: 0% (DexScreener integration, real-time data chưa implement)
- ⏳ Browser Notifications: 0% (cần backend)

---

## Tổng quan Epic

Xây dựng hệ thống monitoring và alerts thông minh để bảo vệ users khỏi rủi ro và giúp họ không bỏ lỡ cơ hội. Tập trung vào **risk protection** (rug pull detection) và **opportunity alerts** (whale activity, price movements).

**Giá trị kinh doanh (Business Value):**
- **Risk Protection (Bảo vệ rủi ro):** Giúp users tránh mất tiền vào rug pulls.
- **Opportunity Alerts (Cảnh báo cơ hội):** Không bỏ lỡ whale movements và price spikes.
- **Always-On Monitoring:** Giám sát ngầm (Background monitoring) ngay cả khi browser đóng.
- **Lợi thế cạnh tranh:** Proactive alerts (Chủ động cảnh báo) so với passive dashboards (DexScreener/DexTools).

**Điểm khác biệt chính:** AI-driven anomaly detection (Phát hiện bất thường bằng AI), không chỉ là threshold alerts.

---

## User Stories

### Story 2.1: Cảnh báo Giá Thời gian thực (Real-time Price Alerts)
**[FR-EXT-07]**

**Là một** crypto trader,  
**Tôi muốn** đặt cảnh báo giá cho tokens trong watchlist,  
**Để** tôi được thông báo (notify) khi giá chạm target mà không cần nhìn chằm chằm vào biểu đồ cả ngày.

**Tiêu chí chấp nhận (Acceptance Criteria - BDD Format):**

#### AC 2.1.1: Quản lý Watchlist
**Given** user đang xem token trên DexScreener  
**When** user click nút "Add to Watchlist" trong Token Info Card  
**Then** token được thêm vào watchlist  
**And** watchlist badge hiển thị "5 tokens"  
**And** toast notification "Added BULLA/SOL to watchlist"

**Remove from Watchlist:**  
**Given** token đang trong watchlist  
**When** user click nút "Remove"  
**Then** confirmation modal xuất hiện "Remove BULLA/SOL from watchlist?"  
**And** user xác nhận (confirms)  
**Then** token bị xóa khỏi watchlist  
**And** tất cả alerts liên quan bị xóa

**View Watchlist:**  
**Given** user có 5 tokens trong watchlist  
**When** user mở Watchlist panel  
**Then** tất cả 5 tokens hiển thị với:
- Token symbol và chain
- Giá hiện tại (Current price)
- Thay đổi 24h (24h change %)
- Số lượng active alerts
- Nút [Edit] [Remove]

---

#### AC 2.1.2: Cấu hình Loại Alert
**Given** user có token trong watchlist  
**When** user click nút "Add Alert"  
**Then** modal cấu hình alert mở ra với các tùy chọn:

**Price Above Threshold (Giá trên ngưỡng):**  
**Given** user chọn "Price Above"  
**When** user nhập ngưỡng "$0.00015"  
**Then** alert được tạo  
**And** background worker kiểm tra giá mỗi 1 phút  
**When** giá vượt quá $0.00015  
**Then** browser notification hiển thị "🚀 BULLA/SOL hit $0.00016 (+6.7%)"

**Price Below Threshold (Giá dưới ngưỡng):**  
**Given** user chọn "Price Below"  
**When** user nhập ngưỡng "$0.0005"  
**Then** alert kích hoạt khi giá giảm xuống dưới ngưỡng

**Price Change % (Biến động giá %):**  
**Given** user chọn "Price Change %"  
**When** user nhập "+20% in 1h"  
**Then** alert kích hoạt khi giá tăng 20% trong vòng 1 giờ

**Volume Spike (Khối lượng tăng đột biến):**  
**Given** user chọn "Volume Spike"  
**When** user nhập "3x average volume"  
**Then** alert kích hoạt khi volume vượt quá 3 lần trung bình 24h

**Liquidity Change (Thay đổi thanh khoản):**  
**Given** user chọn "Liquidity Change"  
**When** user nhập "-50% liquidity"  
**Then** alert kích hoạt khi thanh khoản giảm 50% so với baseline

---

#### AC 2.1.3: Browser Notifications
**Given** user có active price alert  
**When** điều kiện alert được đáp ứng  
**Then** browser notification xuất hiện với:
- Token symbol: "BULLA/SOL"
- Current price: "$0.00016"
- Change %: "+6.7%"
- Alert type: "Price Above $0.00015"

**Hoạt động khi đóng Tab:**  
**Given** user đã đóng tất cả browser tabs  
**When** alert kích hoạt  
**Then** notification vẫn xuất hiện (nhờ background service worker)

**Click Notification:**  
**Given** user nhận thông báo  
**When** user click vào thông báo  
**Then** tab mới mở ra với trang DexScreener cho token đó  
**And** side panel tự động mở với token context

---

#### AC 2.1.4: Cảnh báo Âm thanh (Sound Alerts)
**Given** user bật sound alerts  
**When** alert kích hoạt  
**Then** âm thanh phát ra dựa trên loại alert:
- Price Above: "ding.mp3" (âm thanh tích cực)
- Price Below: "alert.mp3" (âm thanh cảnh báo)
- Volume Spike: "chime.mp3" (âm thanh chú ý)

**Enable/Disable Per Alert:**  
**Given** user có nhiều alerts  
**When** user bật tắt âm thanh cho một alert cụ thể  
**Then** chỉ alert đó mới phát âm thanh  
**And** các alerts khác vẫn im lặng

---

#### AC 2.1.5: Lịch sử Alert (Alert History)
**Given** user có alerts đã kích hoạt  
**When** user mở panel "Alert History"  
**Then** danh sách hiển thị 100 alerts gần nhất với:
- Thời gian: "2 hours ago"
- Token: "BULLA/SOL"
- Alert type: "Price Above $0.00015"
- Triggered price: "$0.00016"
- Trạng thái Read/Unread

**Mark as Read:**  
**Given** alert chưa đọc (unread)  
**When** user click vào alert  
**Then** alert được đánh dấu là đã đọc  
**And** số lượng badge unread giảm đi

**Filter History:**  
**Given** user có 100+ alerts  
**When** user filter theo token "BULLA/SOL"  
**Then** chỉ hiển thị alerts của BULLA  
**When** user filter theo loại "Price Above"  
**Then** chỉ hiển thị alerts giá trên ngưỡng

**UI Design:**
```
┌─────────────────────────────┐
│ 📊 Watchlist (5 tokens)     │
├─────────────────────────────┤
│ BULLA/SOL    $0.0001  +15%  │
│ 🔔 Alert: Price > $0.00015  │
│ [Edit] [Remove]             │
├─────────────────────────────┤
│ PEPE/ETH     $0.000001 -5%  │
│ 🔕 No alerts                │
│ [Add Alert]                 │
├─────────────────────────────┤
│ [+ Add Token to Watchlist]  │
└─────────────────────────────┘
```

**Triển khai kỹ thuật:**
```typescript
interface PriceAlert {
  id: string;
  tokenAddress: string;
  chain: string;
  alertType: 'above' | 'below' | 'change_percent' | 'volume_spike' | 'liquidity_change';
  threshold: number;
  enabled: boolean;
  soundEnabled: boolean;
  lastTriggered?: number;
}

// Background service worker
chrome.alarms.create('checkPriceAlerts', { periodInMinutes: 1 });
chrome.alarms.onAlarm.addListener(async (alarm) => {
  if (alarm.name === 'checkPriceAlerts') {
    await checkAllPriceAlerts();
  }
});
```

**Backend API:**
```
POST /api/watchlist/add
DELETE /api/watchlist/:id
GET /api/watchlist
POST /api/alerts/create
GET /api/alerts/check  // Returns triggered alerts
```

**Files:**
- `background/alerts/price-alerts.ts` (new)
- `sidepanel/watchlist/WatchlistPanel.tsx` (new)
- `sidepanel/watchlist/AddAlertModal.tsx` (new)

---

### Story 2.2: Theo dõi Hoạt động Cá voi (Whale Activity Tracker)
**[FR-EXT-08]**

**Là một** crypto trader,  
**Tôi muốn** được thông báo khi có giao dịch mua/bán lớn (whale buy/sell),  
**Để** tôi có thể theo chân dòng tiền thông minh (smart money) và tránh bị xả hàng (dumped).

**Tiêu chí chấp nhận (Acceptance Criteria - BDD Format):**

#### AC 2.2.1: Giám sát Giao dịch Lớn
**Given** user có token trong watchlist  
**When** phát hiện giao dịch cá voi (whale transaction) (>$10K)  
**Then** thông báo xuất hiện "🐋 $100K BUY detected for BULLA/SOL"  
**And** chi tiết giao dịch hiển thị:
- Loại: BUY hoặc SELL
- Số lượng: "1B tokens ($100,000)"
- Ví: "0x1234...5678"
- Thời gian: "2 min ago"

**Configurable Thresholds (Ngưỡng có thể cấu hình):**  
**Given** user mở cài đặt whale  
**When** user chọn ngưỡng "$50K"  
**Then** chỉ các giao dịch >$50K mới kích hoạt alerts  
**And** các giao dịch nhỏ hơn bị bỏ qua

**Phát hiện Mua vs Bán:**  
**Given** whale bán lượng token trị giá $100K  
**When** giao dịch được phát hiện  
**Then** thông báo hiển thị "🔴 SELL $100K BULLA/SOL"  
**And** màu đỏ chỉ thị áp lực bán

---

#### AC 2.2.2: Phát hiện Gom nhóm Ví (Wallet Clustering Detection)
**Given** cùng một thực thể kiểm soát nhiều ví  
**When** hệ thống phát hiện các ví liên quan  
**Then** các ví được nhóm lại với nhau  
**And** hiển thị tổng holdings trên tất cả các ví

**Ví dụ:**  
**Given** ví A và B thuộc cùng một thực thể  
**When** ví A mua 500M tokens  
**And** ví B mua 300M tokens  
**Then** hệ thống hiển thị "Entity holds 800M tokens across 2 wallets"

---

#### AC 2.2.3: Theo dõi Smart Money
**Given** user xác định được ví có lợi nhuận cao  
**When** user click "Track This Wallet"  
**Then** ví được thêm vào danh sách smart money  
**And** tất cả giao dịch tương lai từ ví này sẽ kích hoạt alerts

**Hiệu suất Lịch sử:**  
**Given** ví đang được theo dõi là smart money  
**When** user xem chi tiết ví  
**Then** hệ thống hiển thị:
- Tổng số giao dịch: 50
- Tỷ lệ thắng (Win rate): 75%
- Lợi nhuận trung bình: +120%
- Các giao dịch gần đây (10 giao dịch cuối)

**Cảnh báo Hoạt động:**  
**Given** ví smart money thực hiện giao dịch  
**When** giao dịch được phát hiện  
**Then** thông báo ưu tiên "⚠️ Smart Money Alert: Wallet 0x1234 bought $50K PEPE"  
**And** thông báo có mức ưu tiên cao hơn whale alerts thông thường

---

#### AC 2.2.4: Chi tiết Giao dịch
**Given** phát hiện giao dịch cá voi  
**When** user click vào thông báo  
**Then** modal chi tiết mở ra với:
- Địa chỉ ví: "0x1234...5678" (có thể copy)
- Transaction hash: "0xabcd...ef01" (có thể copy)
- Số lượng: "1B tokens ($100,000)"
- Thời gian: "2 min ago (14:30:15 UTC)"
- Link tới block explorer
- Nút [Track This Wallet]

**Link tới Explorer:**  
**Given** user click "View on Explorer"  
**When** link được click  
**Then** tab mới mở ra với:
- Solana: Solscan.io
- Ethereum: Etherscan.io
- Base: BaseScan.org

---

#### AC 2.2.5: Feed Hoạt động Cá voi
**Given** phát hiện nhiều giao dịch cá voi  
**When** user mở panel Whale Activity  
**Then** feed hiển thị danh sách theo thời gian:
- Gần nhất ở trên cùng
- 50 giao dịch cuối cùng
- Gom nhóm theo token
- Lọc theo: Tất cả tokens / Chỉ Watchlist

**Tùy chọn Lọc:**  
**Given** user có 100 whale transactions  
**When** user lọc "Watchlist only"  
**Then** chỉ hiển thị giao dịch của tokens trong watchlist  
**When** user lọc "Smart Money only"  
**Then** chỉ hiển thị giao dịch của ví được theo dõi

**Cập nhật Real-time:**  
**Given** user đang mở panel Whale Activity  
**When** phát hiện giao dịch cá voi mới  
**Then** item mới xuất hiện ở đầu feed  
**And** hiệu ứng trượt mượt mà (smooth animation)  
**And** badge unread tăng lên

**UI Design:**
```
┌─────────────────────────────┐
│ 🐋 Whale Activity           │
├─────────────────────────────┤
│ 2 min ago                   │
│ 🟢 BUY $100K BULLA/SOL      │
│ Wallet: 0x1234...5678       │
│ Amount: 1B tokens           │
│ [View on Explorer]          │
├─────────────────────────────┤
│ 5 min ago                   │
│ 🔴 SELL $50K PEPE/ETH       │
│ Wallet: 0xabcd...ef01       │
│ ⚠️ Smart Money Wallet       │
│ [Track This Wallet]         │
└─────────────────────────────┘
```

**Triển khai kỹ thuật:**
```typescript
interface WhaleTransaction {
  id: string;
  tokenAddress: string;
  chain: string;
  type: 'buy' | 'sell';
  amountUSD: number;
  amountTokens: string;
  walletAddress: string;
  txHash: string;
  timestamp: number;
  isSmartMoney: boolean;
}

// Poll blockchain for large transactions
async function monitorWhaleActivity() {
  const watchlistTokens = await getWatchlistTokens();
  for (const token of watchlistTokens) {
    const largeTxs = await fetchLargeTransactions(token, threshold);
    for (const tx of largeTxs) {
      await notifyWhaleActivity(tx);
    }
  }
}
```

**Data Sources:**
- Solana: Helius API / QuickNode
- Ethereum: Etherscan API / Alchemy
- Base: BaseScan API

**Files:**
- `background/alerts/whale-tracker.ts` (new)
- `sidepanel/whale/WhaleActivityFeed.tsx` (new)
- `lib/blockchain/transaction-monitor.ts` (new)

---

### Story 2.3: Hệ thống Cảnh báo Sớm Rug Pull (Rug Pull Early Warning System)
**[FR-EXT-09]**

**Là một** crypto trader,  
**Tôi muốn** được cảnh báo sớm về rủi ro rug pull,  
**Để** tôi không mất tiền vào các token lừa đảo (scam tokens).

**Tiêu chí chấp nhận (Acceptance Criteria - BDD Format):**

#### AC 2.3.1: Giám sát Chỉ số Rủi ro (Risk Indicators Monitoring)
**Given** user đang xem token trên DexScreener  
**When** hệ thống phân tích contract của token  
**Then** các chỉ số rủi ro sau được kiểm tra:

**Phát hiện Rút thanh khoản (LP Removal Detection):**  
**Given** token có liquidity pool  
**When** LP tokens bị rút hoặc mở khóa (unlocked)  
**Then** điểm rủi ro +3 điểm  
**And** cảnh báo "🔴 LP REMOVED: BULLA/SOL - Potential rug pull!"

**Thay đổi Quyền Mint (Mint Authority Changes):**  
**Given** token mint authority tồn tại  
**When** mint authority chưa được từ bỏ (not renounced)  
**Then** điểm rủi ro +2 điểm  
**And** cảnh báo "🟡 Mint authority active - can create unlimited tokens"

**Mô hình Holder Đáng ngờ:**  
**Given** token có phân bổ holder  
**When** top 10 holders sở hữu >80% nguồn cung  
**Then** điểm rủi ro +2 điểm  
**And** cảnh báo "🟡 Centralized ownership - top 10 hold 85%"

**Quyền sở hữu Contract:**  
**Given** token contract có chủ sở hữu (owner)  
**When** ownership chưa được từ bỏ  
**Then** điểm rủi ro +1 điểm  
**And** cảnh báo "🟡 Contract owner can modify code"

**Phát hiện Honeypot:**  
**Given** token contract được phân tích  
**When** chức năng bán bị vô hiệu hóa hoặc hạn chế  
**Then** điểm rủi ro +3 điểm  
**And** cảnh báo nghiêm trọng "🔴 HONEYPOT DETECTED - Cannot sell!"

---

#### AC 2.3.2: Tính toán Điểm Rủi ro (Risk Score Calculation)
**Given** tất cả chỉ số rủi ro đã được phân tích  
**When** hệ thống tính tổng điểm rủi ro  
**Then** điểm số hiển thị như sau:

**Rủi ro Thấp (Low Risk - 0-3):**  
**Given** điểm rủi ro = 2  
**Then** badge hiển thị "✅ Low Risk (2/10)"  
**And** màu xanh lá  
**And** khuyến nghị "SAFE: Proceed with caution"

**Rủi ro Trung bình (Medium Risk - 4-6):**  
**Given** điểm rủi ro = 5  
**Then** badge hiển thị "⚠️ Medium Risk (5/10)"  
**And** màu vàng  
**And** khuyến nghị "CAUTION: Do your own research"

**Rủi ro Cao (High Risk - 7-10):**  
**Given** điểm rủi ro = 8  
**Then** badge hiển thị "🔴 High Risk (8/10)"  
**And** màu đỏ  
**And** khuyến nghị "AVOID: Likely scam"

---

#### AC 2.3.3: Hiển thị Điểm Rủi ro
**Given** token đã được phân tích  
**When** user xem Token Info Card  
**Then** điểm rủi ro hiển thị nổi bật:
- Risk badge ở trên cùng
- Các yếu tố rủi ro riêng lẻ được liệt kê
- Mỗi yếu tố với icon (🔴/🟡/🟢)
- Giải thích cho mỗi yếu tố

**Cập nhật Real-time:**  
**Given** điểm rủi ro ban đầu là 3/10  
**When** LP bị rút (rủi ro tăng lên 6/10)  
**Then** risk badge cập nhật ngay lập tức  
**And** màu thay đổi từ xanh -> vàng  
**And** gửi thông báo

**Giải thích Yếu tố Rủi ro:**  
**Given** user click vào risk badge  
**When** modal chi tiết mở ra  
**Then** giải thích từng yếu tố:
- "🔴 LP unlocked (High Risk): Liquidity can be removed anytime"
- "🟡 Top holder owns 40%: Centralized ownership risk"
- "🟢 Contract verified: Code is public and audited"

---

#### AC 2.3.4: Khuyến nghị (Recommendations)
**Given** điểm rủi ro đã tính toán  
**When** hệ thống tạo khuyến nghị  
**Then** thông điệp phù hợp hiển thị:

**SAFE (0-3):**  
**Then** thông điệp "✅ Low risk, proceed with caution. Always DYOR."

**CAUTION (4-6):**  
**Then** thông điệp "⚠️ Medium risk, do your own research. Some red flags detected."

**AVOID (7-10):**  
**Then** thông điệp "🔴 High risk, likely scam. Strong evidence of rug pull potential."

---

#### AC 2.3.5: Cảnh báo Rủi ro (Risk Alerts)
**Given** user có token trong watchlist  
**When** điểm rủi ro tăng lên  
**Then** cảnh báo được kích hoạt

**Tăng Điểm Rủi ro:**  
**Given** điểm rủi ro là 3/10  
**When** rủi ro tăng lên 7/10  
**Then** thông báo "⚠️ RISK ALERT: BULLA/SOL risk increased to 7/10 (High Risk)"

**Cảnh báo Rút LP:**  
**Given** token có LP bị khóa  
**When** LP bị rút  
**Then** cảnh báo khẩn cấp "🚨 URGENT: LP REMOVED from BULLA/SOL - Exit immediately!"  
**And** âm thanh cảnh báo phát ra  
**And** thông báo tồn tại cho đến khi bị tắt (dismissed)

**Thay đổi Quyền Mint:**  
**Given** mint authority đã được từ bỏ  
**When** mint authority được kích hoạt lại  
**Then** cảnh báo "⚠️ WARNING: Mint authority changed for BULLA/SOL"

**Phát hiện Honeypot:**  
**Given** token có thể bán được  
**When** honeypot bị phát hiện  
**Then** cảnh báo nghiêm trọng "🔴 HONEYPOT: Cannot sell BULLA/SOL - Do not buy!"

**UI Design:**
```
┌─────────────────────────────┐
│ ⚠️ RUG PULL WARNING         │
├─────────────────────────────┤
│ Risk Score: 7/10 (High)     │
│                             │
│ 🔴 LP unlocked (High Risk)  │
│ 🟡 Top holder owns 40%      │
│ 🟢 Contract verified        │
│ 🟢 Mint authority renounced │
│                             │
│ Recommendation: AVOID       │
│ This token shows signs of   │
│ potential rug pull.         │
│                             │
│ [View Full Analysis]        │
└─────────────────────────────┘
```

**Triển khai kỹ thuật:**
```typescript
interface RiskAssessment {
  tokenAddress: string;
  chain: string;
  riskScore: number; // 0-10
  riskLevel: 'low' | 'medium' | 'high';
  indicators: {
    lpLocked: boolean;
    lpLockDuration?: number; // days
    mintAuthority: 'renounced' | 'active' | 'unknown';
    topHolderPercent: number;
    contractVerified: boolean;
    isHoneypot: boolean;
  };
  recommendation: 'safe' | 'caution' | 'avoid';
  explanation: string;
  timestamp: number;
}
```

**Data Sources:**
- LP Lock: RugCheck API, Token Sniffer
- Mint Authority: On-chain data (Solana/Ethereum)
- Holders: Blockchain explorers
- Contract Verification: Etherscan, Solscan
- Honeypot: Honeypot.is API

**Files:**
- `lib/risk/rug-pull-detector.ts` (new)
- `sidepanel/risk/RiskScoreCard.tsx` (new)
- `background/alerts/risk-monitor.ts` (new)

---

## Technical Dependencies

### Backend APIs
```
POST /api/watchlist/add
GET  /api/watchlist
POST /api/alerts/create
GET  /api/alerts/check
GET  /api/whale/transactions
GET  /api/risk/assess
```

### External APIs
- **Helius API** (Solana transactions)
- **Alchemy** (Ethereum transactions)
- **RugCheck API** (LP lock status)
- **Token Sniffer** (Contract analysis)
- **Honeypot.is** (Honeypot detection)

### Chrome APIs
- `chrome.alarms` - Periodic checks
- `chrome.notifications` - Browser notifications
- `chrome.storage` - Watchlist persistence

---

## Testing Strategy

### Unit Tests
- [ ] Tính toán điểm rủi ro (Risk score calculation)
- [ ] Phát hiện giao dịch cá voi (Whale transaction detection)
- [ ] Logic kích hoạt cảnh báo (Alert triggering logic)

### Integration Tests
- [ ] Price alerts kích hoạt chính xác
- [ ] Thông báo hoạt động cá voi hoạt động
- [ ] Đánh giá rủi ro cập nhật realtime

### Manual Testing
- [ ] Thêm token vào watchlist
- [ ] Đặt price alert và xác minh thông báo
- [ ] Giám sát hoạt động cá voi trên live token
- [ ] Kiểm tra cảnh báo rug pull trên scam token đã biết

---

## Definition of Done

- [ ] All 3 stories completed
- [ ] All acceptance criteria met
- [ ] Unit tests passing
- [ ] Integration tests passing
- [ ] Manual testing completed
- [ ] External API integrations working
- [ ] Code reviewed
- [ ] Documentation updated

---

## Ghi chú

**Priority Justification:** Risk protection (rug pull detection) là QUAN TRỌNG (CRITICAL) cho niềm tin của user. Users sẽ không sử dụng sản phẩm nếu họ mất tiền vì scams.

**Next Epic:** Epic 3 - Trading Intelligence (Phase 3)
