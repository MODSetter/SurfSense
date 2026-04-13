# Epic 3: Trading Intelligence (Trí tuệ Giao dịch)

**Trạng thái:** 🚧 ĐANG TRIỂN KHAI (IN PROGRESS)
**Giai đoạn:** Phase 3
**Thời gian:** 2 tuần
**Mức độ ưu tiên:** P1 (Cao - Giá trị gia tăng)

**Tiến độ:**
- ✅ Extension UI: 80% hoàn thành (TokenAnalysisPanel, TradingSuggestionPanel, PortfolioPanel)
- ✅ Extension Widgets: 100% hoàn thành (TokenAnalysisWidget, TradingSuggestionWidget, PortfolioWidget)
- ✅ Web Tool UIs: 80% hoàn thành (TokenAnalysisToolUI, PortfolioDisplayToolUI)
- ⚠️ Web Tool UIs: TradingSuggestionToolUI chưa có (cần thêm để sync với Extension)
- ⏳ Backend APIs: 0% (AI analysis, wallet connection chưa implement)
- ⏳ Real-time P&L: 0% (cần backend)

---

## Tổng quan Epic

Cung cấp AI-powered trading insights để giúp users ra quyết định giao dịch tốt hơn (make better trading decisions). Tập trung vào **phân tích toàn diện (comprehensive analysis)**, **gợi ý điểm vào/ra (entry/exit suggestions)**, và **theo dõi danh mục đầu tư (portfolio tracking)**.

**Giá trị kinh doanh (Business Value):**
- **Quyết định tốt hơn:** AI-generated insights giúp users trade thông minh hơn.
- **Tiết kiệm thời gian:** Phân tích một cú click thay vì hàng giờ nghiên cứu.
- **Quản lý danh mục:** Theo dõi hiệu suất và tối ưu hóa holdings.
- **Lợi thế cạnh tranh:** Dự đoán AI so với dữ liệu tĩnh (DexScreener/DexTools).

**Điểm khác biệt chính:** Phân tích ưu tiên AI (AI-first analysis) với các giải thích bằng ngôn ngữ tự nhiên.

---

## User Stories

### Story 3.1: Phân tích Token Một Cú Click (One-Click Token Analysis)
**[FR-EXT-10]**

**Là một** crypto trader,  
**Tôi muốn** analyze token với một click,  
**Để** tôi có insights toàn diện mà không cần nghiên cứu thủ công.

**Tiêu chí chấp nhận (Acceptance Criteria):**
- [ ] Nút "Analyze This Token" trên Thẻ Thông tin Token (Token Info Card)
- [ ] Phân tích toàn diện bao gồm:
  - **Phân tích Hợp đồng (Contract Analysis):**
    - Đã xác minh/chưa xác minh (Verified/unverified)
    - Từ bỏ quyền sở hữu (Renounced ownership)
    - Phát hiện Proxy contract
    - Tính khả dụng của mã nguồn (Source code availability)
  - **Phân bổ Holder (Holder Distribution):**
    - Tỷ lệ Top 10 holders
    - Số lượng Holder
    - Độ tập trung của Whale
    - Biểu đồ phân bổ
  - **Phân tích Thanh khoản (Liquidity Analysis):**
    - Tổng thanh khoản (USD)
    - Trạng thái khóa LP & thời hạn
    - Lịch sử thanh khoản (7 ngày, 30 ngày)
    - Tỷ lệ Thanh khoản/Vốn hóa (Liquidity/Market cap ratio)
  - **Khối lượng Giao dịch (Trading Volume):**
    - Volume 24h
    - Xu hướng Volume (tăng/giảm)
    - Tỷ lệ Volume/Thanh khoản
    - Các đợt tăng volume bất thường (Unusual volume spikes)
  - **Lịch sử Giá (Price History):**
    - Giá cao nhất/thấp nhất mọi thời đại (ATH/ATL)
    - Hiệu suất 7 ngày, 30 ngày
    - Biến động giá (Price volatility)
    - Các mức Hỗ trợ/Kháng cự (Support/resistance levels)
  - **Cảm xúc Xã hội (Social Sentiment):**
    - Twitter mentions
    - Hoạt động Telegram
    - Thảo luận Reddit
    - Điểm cảm xúc (tích cực/tiêu cực/trung lập)
- [ ] Tóm tắt do AI tạo (AI-Generated Summary):
  - Tóm tắt 2-3 câu
  - Các insight chính được làm nổi bật
  - Đánh giá rủi ro (Risk assessment)
  - Khuyến nghị giao dịch (Trading recommendation)
- [ ] Caching phân tích:
  - Cache trong 5 phút
  - Hiển thị timestamp "Cập nhật lần cuối"
  - Nút Refresh

**UI Design:**
```
┌─────────────────────────────┐
│ 📊 Token Analysis           │
├─────────────────────────────┤
│ AI Summary:                 │
│ "BULLA shows strong holder  │
│ distribution with verified  │
│ contract. Volume increasing │
│ 200% in 24h. Moderate risk."│
│                             │
│ Contract: ✅ Verified       │
│ Ownership: ✅ Renounced     │
│                             │
│ Holders: 1,234              │
│ Top 10: 35% (Good)          │
│                             │
│ Liquidity: $50K             │
│ LP Lock: 90 days            │
│                             │
│ Volume 24h: $100K (+200%)   │
│ Price: $0.0001 (+15%)       │
│                             │
│ Sentiment: 😊 Positive      │
│ Twitter: 500 mentions       │
│                             │
│ Recommendation: BUY         │
│ Confidence: 75%             │
│                             │
│ [View Full Report]          │
│ Last updated: 2 min ago     │
107: └─────────────────────────────┘
```

**Triển khai kỹ thuật:**
```typescript
interface TokenAnalysis {
  tokenAddress: string;
  chain: string;
  timestamp: number;
  
  contract: {
    verified: boolean;
    renounced: boolean;
    isProxy: boolean;
    sourceCode: boolean;
  };
  
  holders: {
    count: number;
    top10Percent: number;
    distribution: { address: string; percent: number }[];
  };
  
  liquidity: {
    totalUSD: number;
    lpLocked: boolean;
    lpLockDuration?: number;
    history7d: number[];
    liquidityMcapRatio: number;
  };
  
  volume: {
    volume24h: number;
    trend: 'increasing' | 'decreasing' | 'stable';
    volumeLiquidityRatio: number;
    spikes: { timestamp: number; volume: number }[];
  };
  
  price: {
    current: number;
    ath: number;
    atl: number;
    change7d: number;
    change30d: number;
    volatility: number;
    supportLevels: number[];
    resistanceLevels: number[];
  };
  
  social: {
    twitterMentions: number;
    telegramActivity: number;
    redditDiscussions: number;
    sentimentScore: number; // -1 to 1
    sentiment: 'positive' | 'negative' | 'neutral';
  };
  
  aiSummary: string;
  recommendation: 'buy' | 'hold' | 'sell' | 'avoid';
  confidence: number; // 0-100
}

async function analyzeToken(tokenAddress: string, chain: string): Promise<TokenAnalysis> {
  // Parallel data fetching
  const [contract, holders, liquidity, volume, price, social] = await Promise.all([
    analyzeContract(tokenAddress, chain),
    analyzeHolders(tokenAddress, chain),
    analyzeLiquidity(tokenAddress, chain),
    analyzeVolume(tokenAddress, chain),
    analyzePrice(tokenAddress, chain),
    analyzeSocial(tokenAddress, chain),
  ]);
  
  // AI-generated summary
  const aiSummary = await generateAISummary({
    contract,
    holders,
    liquidity,
    volume,
    price,
    social,
  });
  
  return {
    tokenAddress,
    chain,
    timestamp: Date.now(),
    contract,
    holders,
    liquidity,
    volume,
    price,
    social,
    aiSummary,
    recommendation: getRecommendation(/* ... */),
    confidence: calculateConfidence(/* ... */),
  };
}
```

**Files:**
- `lib/analysis/token-analyzer.ts` (new)
- `sidepanel/analysis/TokenAnalysisPanel.tsx` (new)
- `sidepanel/analysis/AnalysisSummary.tsx` (new)

---

### Story 3.2: Gợi ý Điểm Vào/Ra Thông minh (Smart Entry/Exit Suggestions)
**[FR-EXT-11]**

**Là một** crypto trader,  
**Tôi muốn** AI gợi ý các điểm entry/exit,  
**Để** tôi tối đa hóa lợi nhuận và giảm thiểu rủi ro.

**Tiêu chí chấp nhận (Acceptance Criteria):**
- [ ] Phân tích kỹ thuật (Technical analysis):
  - Các mức Hỗ trợ/Kháng cự (3 levels each)
  - Các mức Fibonacci retracement
  - Phân tích Volume profile
  - Đường trung bình động (Moving averages) (20, 50, 200)
- [ ] Dự đoán của AI (AI predictions):
  - Mục tiêu giá dự kiến (Predicted price targets) (3 levels)
  - Khung thời gian (1h, 4h, 24h)
  - Điểm tin cậy (Confidence score) cho mỗi dự đoán
- [ ] Tính toán Rủi ro/Lợi nhuận (Risk/Reward):
  - Vùng vào lệnh gợi ý (Suggested entry range)
  - Mức cắt lỗ (Stop loss level)
  - Các mức chốt lời (Take profit levels) (3 targets)
  - Tỷ lệ Risk/Reward
- [ ] Trực quan hóa (Visual representation):
  - Biểu đồ giá với các levels được đánh dấu
  - Vùng entry/exit được làm nổi bật
  - Trực quan hóa Risk/reward
- [ ] Giải thích (Explanation):
  - Tại sao lại là các levels này?
  - Tín hiệu nào hỗ trợ điều này?
  - Điều gì có thể vô hiệu hóa dự đoán này?

**UI Design:**
```
┌─────────────────────────────┐
│ 💡 AI Trading Suggestion    │
├─────────────────────────────┤
│ Current Price: $0.00010     │
│                             │
│ Entry Zone: 🟢              │
│ $0.00010 - $0.00012         │
│                             │
│ Targets:                    │
│ 🎯 Target 1: $0.00015 (+25%)│
│ 🎯 Target 2: $0.00018 (+50%)│
│ 🎯 Target 3: $0.00022 (+83%)│
│                             │
│ Stop Loss: 🔴               │
│ $0.00008 (-20%)             │
│                             │
│ Risk/Reward: 1:3.3 (Good)   │
│ Confidence: 75%             │
│                             │
│ Why?                        │
│ • Strong support at $0.0001 │
│ • Volume increasing         │
│ • Fibonacci 0.618 at $0.00015│
│                             │
│ [View Chart] [Set Alerts]   │
└─────────────────────────────┘
```

**Triển khai kỹ thuật:**
```typescript
interface TradingSuggestion {
  tokenAddress: string;
  chain: string;
  currentPrice: number;
  timestamp: number;
  
  entry: {
    min: number;
    max: number;
    reasoning: string;
  };
  
  targets: {
    level: number;
    price: number;
    percentGain: number;
    confidence: number;
  }[];
  
  stopLoss: {
    price: number;
    percentLoss: number;
    reasoning: string;
  };
  
  riskReward: number;
  overallConfidence: number;
  
  technicalLevels: {
    support: number[];
    resistance: number[];
    fibonacci: { level: number; price: number }[];
    movingAverages: { period: number; price: number }[];
  };
  
  reasoning: string[];
  invalidationConditions: string[];
}
```

**Files:**
- `lib/analysis/trading-suggestions.ts` (new)
- `sidepanel/analysis/TradingSuggestionPanel.tsx` (new)

---

### Story 3.3: Tích hợp Theo dõi Portfolio (Portfolio Tracker Integration)
**[FR-EXT-12]**

**Là một** crypto trader,  
**Tôi muốn** theo dõi portfolio ngay trong extension,  
**Để** tôi biết P&L realtime mà không cần mở nhiều tab.

**Tiêu chí chấp nhận (Acceptance Criteria):**
- [ ] Kết nối Ví (Wallet connection):
  - Hỗ trợ MetaMask, Phantom, Coinbase Wallet
  - Hỗ trợ Multi-wallet
  - Tự động phát hiện holdings
- [ ] Tổng quan Portfolio:
  - Tổng giá trị (USD)
  - 24h P&L ($ và %)
  - All-time P&L
  - Biểu đồ phân bổ tài sản
- [ ] Danh sách Holdings:
  - Token symbol/name
  - Số lượng nắm giữ (Amount held)
  - Giá trị hiện tại
  - Thay đổi 24h
  - P&L theo từng token
  - Giá entry (nếu có sẵn)
- [ ] Phân tích Hiệu suất (Performance analytics):
  - Best/worst performers
  - Tỷ lệ thắng (Win rate)
  - Thời gian giữ trung bình (Average hold time)
  - Tổng số giao dịch
- [ ] Thao tác nhanh (Quick actions):
  - Analyze token
  - Set price alert
  - Xem trên DexScreener
  - Sell (link tới DEX)

**UI Design:**
```
┌─────────────────────────────┐
│ 💼 Portfolio                │
├─────────────────────────────┤
│ Total Value: $5,234         │
│ 24h P&L: +$234 (+4.7%) 📈   │
│                             │
│ Holdings (5 tokens):        │
│                             │
│ BULLA/SOL                   │
│ 1,000,000 tokens            │
│ $1,234 (+15%) 📈            │
│ [Analyze] [Alert] [Sell]    │
│                             │
│ PEPE/ETH                    │
│ 500,000,000 tokens          │
│ $2,100 (-5%) 📉             │
│ [Analyze] [Alert] [Sell]    │
│                             │
│ [+ Add Manual Position]     │
│                             │
│ Performance:                │
│ Best: BULLA (+15%)          │
│ Worst: PEPE (-5%)           │
│ Win Rate: 60%               │
└─────────────────────────────┘
```

**Triển khai kỹ thuật:**
```typescript
interface Portfolio {
  wallets: {
    address: string;
    chain: string;
    type: 'metamask' | 'phantom' | 'coinbase';
  }[];
  
  totalValue: number;
  change24h: number;
  change24hPercent: number;
  
  holdings: {
    tokenAddress: string;
    chain: string;
    symbol: string;
    name: string;
    amount: string;
    currentPrice: number;
    currentValue: number;
    change24h: number;
    change24hPercent: number;
    entryPrice?: number;
    pnl?: number;
    pnlPercent?: number;
  }[];
  
  analytics: {
    bestPerformer: { symbol: string; change: number };
    worstPerformer: { symbol: string; change: number };
    winRate: number;
    avgHoldTime: number;
    totalTrades: number;
  };
}
```

**Files:**
- `lib/wallet/wallet-connector.ts` (new)
- `lib/portfolio/portfolio-tracker.ts` (new)
- `sidepanel/portfolio/PortfolioPanel.tsx` (new)

---

## Các phụ thuộc kỹ thuật (Technical Dependencies)

### Backend APIs
```
POST /api/analysis/token
GET  /api/analysis/suggestions
POST /api/portfolio/connect
GET  /api/portfolio/holdings
GET  /api/portfolio/analytics
```

### External APIs
- **Blockchain Data:** Helius, Alchemy, QuickNode
- **Price Data:** DexScreener API
- **Social Data:** Twitter API, LunarCrush
- **Technical Analysis:** TradingView indicators

### Wallet Integration
- MetaMask SDK
- Phantom SDK
- Coinbase Wallet SDK

---

## Chiến lược Kiểm thử (Testing Strategy)

### Unit Tests
- [ ] Tính toán phân tích Token
- [ ] Thuật toán gợi ý giao dịch
- [ ] Tính toán P&L Portfolio

### Integration Tests
- [ ] Quy trình kết nối Wallet
- [ ] Fetch dữ liệu Portfolio
- [ ] Tạo phân tích (Analysis generation)

### Manual Testing
- [ ] Phân tích một token trực tiếp (live token)
- [ ] Kết nối ví và xem portfolio
- [ ] Xác minh độ chính xác của các gợi ý giao dịch

---

## Định nghĩa hoàn thành (Definition of Done)

- [ ] Tất cả 3 user stories hoàn thành
- [ ] Tất cả tiêu chí chấp nhận (acceptance criteria) được đáp ứng
- [ ] Unit tests pass
- [ ] Integration tests pass
- [ ] Manual testing hoàn thành
- [ ] Tích hợp Wallet hoạt động
- [ ] Code được review
- [ ] Tài liệu được cập nhật

---

## Ghi chú

**Next Epic:** Epic 4 - Content Creation & Productivity (Phase 4)
