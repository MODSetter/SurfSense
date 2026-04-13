# 🎬 Demo Guide: Epic 2 - Smart Monitoring & Alerts

**Status:** Frontend UI Complete ✅ | Backend Logic Pending ⏳

---

## 🚀 How to Demo

### Prerequisites
1. Extension loaded in Chrome from `build/chrome-mv3-prod/`
2. Navigate to any DexScreener page (e.g., https://dexscreener.com/solana/...)
3. Open sidepanel (click extension icon or right-click → Open side panel)

---

## 📋 Demo Script

### **Demo 1: Watchlist Management** (Story 2.1)

#### Step 1: Add Token to Watchlist
**User says:** `"Add BULLA to my watchlist"`

**Expected Response:**
```
✅ Done! I've added BULLA to your watchlist.

[Action Confirmation Widget]
Token: BULLA
Alerts configured:
• Price change ±20%
• Liquidity drop >10%
• Whale movement >$50K
```

**Alternative commands:**
- `"add this token to watchlist"`
- `"watchlist add BULLA"`
- `"track BULLA"`

---

#### Step 2: View Watchlist
**User says:** `"Show my watchlist"`

**Expected Response:**
```
Here's your watchlist:

[Watchlist Widget]
📊 5 tokens tracked
• BULLA/SOL - $0.0001 (+156.7%) 🔔 3 alerts
• PEPE/ETH - $0.000001 (-5.2%) 🔔 2 alerts
• DOGE/SOL - $0.0002 (+12.3%) 🔕 No alerts
...

BULLA is up 156.7% - your best performer! 
Want me to analyze if it's time to take profits?
```

**Alternative commands:**
- `"view watchlist"`
- `"show my tokens"`
- `"what's in my watchlist"`

---

#### Step 3: Set Price Alert
**User says:** `"Set alert if BULLA drops 20%"`

**Expected Response:**
```
I'll set that up for you:

[Alert Config Widget]
Token: BULLA
Condition: Price drops 20%
Current: $0.00001234
Trigger: $0.00000987
Channels: Browser ✅ | In-App ✅ | Email ❌

Done! I'll notify you if BULLA drops 20% from current price.
Want to set any other alerts?
```

**Alternative commands:**
- `"notify me when BULLA pumps 50%"`
- `"alert if price reaches $0.0002"`
- `"set alert for 30% change"`

---

### **Demo 2: Whale Activity Tracking** (Story 2.2)

#### Step 1: View Whale Activity
**User says:** `"Show whale activity"`

**Expected Response:**
```
Here's recent whale activity for BULLA:

[Whale Activity Widget]
🐋 Recent Large Transactions

2 min ago
🟢 BUY $100K BULLA/SOL
Wallet: 0x742d...35BA ⭐ Smart Money
Amount: 1B tokens
[Track Wallet] [View on Explorer]

5 min ago
🔴 SELL $50K BULLA/SOL
Wallet: 0x1234...5678
Amount: 500M tokens
[Track Wallet] [View on Explorer]

🐋 I'm tracking 5 large transactions (>$10K) in the last hour.
The smart money wallet 0x742d...35BA just bought $50K worth - 
this could be a bullish signal!
```

**Alternative commands:**
- `"show large transactions"`
- `"whale trades"`
- `"big buys and sells"`

---

### **Demo 3: Safety Analysis** (Story 2.3)

#### Step 1: Check Token Safety
**User says:** `"Is BULLA safe?"`

**Expected Response:**
```
Here's my analysis of BULLA:

[Token Analysis Widget]
Safety Score: 72/100 (Medium Risk)

Contract Analysis:
✅ Contract verified
✅ Ownership renounced
⚠️ Top 10 holders: 35%

Liquidity Analysis:
✅ LP locked for 90 days
✅ Liquidity: $450K
✅ Volume/Liquidity: 2.67x

Risk Factors:
🟡 Moderate holder concentration
🟢 Strong liquidity
🟢 Verified contract

Based on your moderate risk profile, suggested allocation: 2-5% of portfolio.
The safety score of 72/100 indicates medium risk - proceed with caution.
```

**Alternative commands:**
- `"analyze BULLA"`
- `"research this token"`
- `"is this a rug pull"`
- `"check safety"`

---

## 🎨 UI Components Showcase

### 1. **Watchlist Panel** (`WatchlistPanel.tsx`)
- Token list with prices and 24h changes
- Alert count badges
- Quick actions: [Edit] [Remove] [Add Alert]
- Empty state with suggestions

### 2. **Alert Config Modal** (`AlertConfigModal.tsx`)
- Alert type selection (Price Above/Below, % Change, Volume Spike)
- Threshold input
- Notification channels (Browser, In-App, Email)
- Sound toggle
- Preview of trigger conditions

### 3. **Whale Activity Feed** (`WhaleActivityFeed.tsx`)
- Real-time transaction feed
- Buy/Sell indicators (🟢/🔴)
- Smart money badges (⭐)
- Wallet tracking buttons
- Explorer links

### 4. **Safety Score Display** (`SafetyScoreDisplay.tsx`)
- Overall safety score (0-100)
- Risk level badge (Low/Medium/High)
- Detailed risk factors
- Recommendations
- Expandable explanations

---

## 🎯 Key Features to Highlight

### ✅ **Implemented (Frontend)**
1. **Conversational UX** - Natural language commands
2. **Inline Widgets** - Rich UI embedded in chat
3. **Context Awareness** - Detects current token from DexScreener
4. **Mock Data** - Realistic demo data for all features
5. **Responsive Design** - Works in narrow sidepanel

### ⏳ **Not Yet Implemented (Backend)**
1. **Real-time Monitoring** - Background service worker
2. **Browser Notifications** - Chrome notifications API
3. **Persistent Storage** - Watchlist/alerts saved
4. **API Integration** - Helius, Alchemy, RugCheck APIs
5. **Sound Alerts** - Audio notifications
6. **Alert History** - Past alerts tracking

---

## 📝 Demo Tips

1. **Start with context** - Navigate to DexScreener first
2. **Use natural language** - Show conversational UX
3. **Highlight widgets** - Point out inline UI components
4. **Show multiple commands** - Demonstrate variety
5. **Explain limitations** - Frontend only, no real monitoring yet

---

## 🐛 Known Limitations

- ⚠️ No actual price monitoring (mock data only)
- ⚠️ Alerts don't trigger (no background worker)
- ⚠️ Watchlist not persisted (resets on reload)
- ⚠️ No real blockchain data (using mocks)
- ⚠️ No browser notifications

---

## 🚀 Next Steps to Complete Epic 2

See main Epic 2 file for full implementation plan:
- Background service worker
- Chrome alarms & notifications
- API integrations (Helius, Alchemy, RugCheck)
- Persistent storage
- Real-time monitoring logic

