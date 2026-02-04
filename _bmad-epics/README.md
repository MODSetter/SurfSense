# SurfSense 2.0 - Epics & Stories

**Project:** SurfSense Crypto Co-Pilot
**Created:** 2026-02-01
**Updated:** 2026-02-04
**Status:** 🚧 IN DEVELOPMENT

---

## Strategy Update (2026-02-04)

> **Extension = Full Features** (không chỉ Quick Actions)
>
> Extension là **full-featured crypto co-pilot** với đầy đủ tính năng phân tích, monitoring, và trading intelligence.
> Web Dashboard tập trung vào settings management và detailed analytics.

---

## Overview

Tài liệu này tổ chức tất cả epics và user stories cho SurfSense 2.0, được chia thành 4 phases dựa trên PRD.

---

## Epic Summary

| Epic | Phase | Stories | Status | Frontend | Backend | Priority |
|------|-------|---------|--------|----------|---------|----------|
| [Epic 1: AI-Powered Crypto Assistant](./epic-1-ai-powered-crypto-assistant.md) | Phase 1 | 10 | 🚧 IN PROGRESS | 100% ✅ | 0% ❌ | P0 |
| [Epic 2: Smart Monitoring & Alerts](./epic-2-smart-monitoring-alerts.md) | Phase 2 | 3 | 🚧 IN PROGRESS | 100% ✅ | 0% ❌ | P0 |
| [Epic 3: Trading Intelligence](./epic-3-trading-intelligence.md) | Phase 3 | 3 | 🚧 IN PROGRESS | 100% ✅ | 0% ❌ | P1 |
| [Epic 4: Content Creation & Productivity](./epic-4-content-creation-productivity.md) | Phase 4 | 5 | 🚧 IN PROGRESS | 100% ✅ | 0% ❌ | P2 |

**Total:** 4 epics, 21 user stories

**🔴 BLOCKER:** Backend APIs chưa được implement (Authentication, Settings, Chat sync, Data APIs)

---

## Phase 1: AI-Powered Crypto Assistant 🚧

**Epic 1** - Foundation cho tất cả features

### Stories:
1. **Story 1.0:** Authentication System (FR-EXT-00) - ⏳ BACKEND BLOCKER
2. **Story 1.1:** Side Panel Architecture (FR-EXT-01) - ✅ DONE
3. **Story 1.2:** AI Chat Interface Integration (FR-EXT-02) - ✅ DONE
4. **Story 1.3:** Page Context Detection (FR-EXT-03) - ✅ DONE
5. **Story 1.4:** DexScreener Smart Integration (FR-EXT-04) - ✅ DONE
6. **Story 1.5:** Quick Capture (FR-EXT-05) - ✅ DONE
7. **Story 1.6:** Settings Sync với Frontend (FR-EXT-06) - ⏳ BACKEND PENDING
8. **Story 1.7:** Universal Token Search Bar (FR-EXT-07) - ✅ DONE (NEW)
9. **Story 1.8:** Multi-Page Token Detection (FR-EXT-08) - ✅ DONE (NEW)
10. **Story 1.9:** Floating Quick Action Button (FR-EXT-09) - ✅ DONE (NEW)

**Key Deliverables:**
- ✅ Chrome Side Panel working
- ✅ AI chat interface integrated
- ✅ Context detection for DexScreener, Twitter, etc.
- ✅ Token info card
- ✅ Quick capture button
- ✅ Universal token search
- ✅ Multi-page token detection
- ✅ Floating quick action button
- ⏳ Settings sync (needs backend)
- ❌ Authentication (needs backend)

---

## Phase 2: Smart Monitoring & Alerts 🚧

**Epic 2** - Risk protection & opportunity alerts

### Stories:
1. **Story 2.1:** Real-time Price Alerts (FR-EXT-10) - ✅ UI DONE, ⏳ API PENDING
2. **Story 2.2:** Whale Activity Tracker (FR-EXT-11) - ✅ UI DONE, ⏳ API PENDING
3. **Story 2.3:** Rug Pull Early Warning System (FR-EXT-12) - ✅ UI DONE, ⏳ API PENDING

**Key Deliverables:**
- ✅ Watchlist management UI (WatchlistPanel, WatchlistWidget)
- ✅ Alert configuration UI (AlertConfigModal, AlertWidget)
- ✅ Whale activity UI (WhaleActivityFeed, WhaleActivityWidget)
- ✅ Safety score display (SafetyScoreDisplay)
- ⏳ Browser notifications (needs backend)
- ⏳ Real-time data (needs DexScreener API)

**Business Value:** Risk protection = User trust

---

## Phase 3: Trading Intelligence 🚧

**Epic 3** - AI-powered trading insights

### Stories:
1. **Story 3.1:** One-Click Token Analysis (FR-EXT-13) - ✅ UI DONE, ⏳ API PENDING
2. **Story 3.2:** Smart Entry/Exit Suggestions (FR-EXT-14) - ✅ UI DONE, ⏳ API PENDING
3. **Story 3.3:** Portfolio Tracker Integration (FR-EXT-15) - ✅ UI DONE, ⏳ API PENDING

**Key Deliverables:**
- ✅ Token analysis UI (TokenAnalysisPanel, TokenAnalysisWidget)
- ✅ Trading suggestions UI (TradingSuggestionPanel, TradingSuggestionWidget)
- ✅ Portfolio UI (PortfolioPanel, PortfolioWidget)
- ⏳ AI-generated summaries (needs backend)
- ⏳ Wallet connection (needs integration)
- ⏳ Real-time P&L (needs backend)

**Business Value:** Better decisions = Better results = Happy users

---

## Phase 4: Content Creation & Productivity ✅

**Epic 4** - Tools for creators & power users

### Stories:
1. **Story 4.1:** Chart Screenshot with Annotations (FR-EXT-16) - ✅ UI DONE
2. **Story 4.2:** AI Thread Generator (FR-EXT-17) - ✅ UI DONE, ⏳ AI PENDING
3. **Story 4.3:** Quick Actions Context Menu (FR-EXT-18) - ✅ UI DONE
4. **Story 4.4:** Smart Notifications Management (FR-EXT-19) - ✅ UI DONE
5. **Story 4.5:** Keyboard Shortcuts (FR-EXT-20) - ✅ UI DONE

**Key Deliverables:**
- ✅ Chart capture UI (ChartCapturePanel, ChartCaptureWidget)
- ✅ Thread generator UI (ThreadGeneratorPanel, ThreadGeneratorWidget)
- ✅ Context menu quick actions (background/index.ts, useContextAction hook)
- ✅ Smart notifications UI (NotificationSettingsPanel, NotificationsList)
- ✅ Keyboard shortcuts (4 shortcuts: Analyze, Watchlist, Capture, Portfolio)
- ⏳ AI thread generation (needs backend)

**Business Value:** Content creation = Viral marketing

---

## Implementation Roadmap

### Week 1-2: Phase 1 - Core Infrastructure
- [x] Side panel architecture
- [x] Chat interface
- [x] Context detection (DexScreener, Twitter, etc.)
- [x] DexScreener integration
- [x] Quick capture
- [x] Universal token search (NEW)
- [x] Multi-page token detection (NEW)
- [x] Floating quick action button (NEW)
- [ ] Authentication (BLOCKER)
- [ ] Settings sync API

### Week 3-4: Phase 2 - Smart Monitoring
- [x] Watchlist UI (WatchlistPanel, WatchlistWidget)
- [x] Alert config UI (AlertConfigModal, AlertWidget)
- [x] Whale activity UI (WhaleActivityFeed, WhaleActivityWidget)
- [x] Safety score UI (SafetyScoreDisplay)
- [ ] DexScreener API integration
- [ ] Real-time price alerts
- [ ] Browser notifications

### Week 5-6: Phase 3 - Trading Intelligence
- [x] Token analysis UI (TokenAnalysisPanel, TokenAnalysisWidget)
- [x] Trading suggestions UI (TradingSuggestionPanel, TradingSuggestionWidget)
- [x] Portfolio UI (PortfolioPanel, PortfolioWidget)
- [ ] AI analysis backend
- [ ] Wallet connection
- [ ] Real-time P&L

### Week 7-8: Phase 4 - Content & Productivity
- [x] Chart capture UI (ChartCapturePanel, ChartCaptureWidget)
- [x] Thread generator UI (ThreadGeneratorPanel, ThreadGeneratorWidget)
- [x] Context menu quick actions
- [x] Smart notifications UI
- [x] Keyboard shortcuts (4 shortcuts)
- [ ] AI thread generation backend

---

## Feature Responsibility Matrix

> **Strategy: Extension = Full Features**

| Feature | Extension | Web Dashboard | Sync |
|---------|-----------|---------------|------|
| Model Selection | 📖 Read-only | ✏️ Full control | API |
| Search Space | 📖 Read-only | ✏️ Full control | API |
| Chat | ✅ Full UI | ✅ Full UI | API |
| Connectors | 📖 Use only | ✏️ Setup | API |
| Documents | 👁️ View | ✏️ Manage | API |
| Watchlist | ✅ Full | ✅ Full | API |
| Alerts | ✅ Full | ✅ Full | API |
| Token Analysis | ✅ Full | ✅ Full (via chat) | API |
| Whale Activity | ✅ Full | ✅ Full (via chat) | API |
| Trading Suggestions | ✅ Full | ✅ Full (via chat) | API |
| Portfolio | ✅ Full | ✅ Full | API |
| Chart Capture | ✅ Full | ❌ N/A | Local |
| Thread Generator | ✅ Full | ❌ N/A | Local |
| Context Detection | ✅ Full | ❌ N/A | Local |
| Floating Button | ✅ Full | ❌ N/A | Local |
| Settings | 📖 Quick | ✏️ Full | API |
| Analytics | 👁️ Basic | ✅ Full | API |

**Legend:**
- ✅ Full feature
- ✏️ Full control
- 📖 Read-only
- 👁️ View only
- ❌ N/A

---

## Technical Stack

### Frontend (Extension)
- **Framework:** Plasmo (React + TypeScript)
- **UI:** @assistant-ui/react, shadcn/ui, Lucide icons
- **State:** Plasmo Storage, React Context
- **APIs:** Chrome Extension APIs (sidePanel, storage, tabs, identity)

### Frontend (Web)
- **Framework:** Next.js (React + TypeScript)
- **UI:** shadcn/ui, @assistant-ui/react
- **State:** React Context, Server Components

### Backend (⏳ PENDING)
- **Framework:** FastAPI (Python)
- **AI:** Gemini 1.5 Flash / GPT-4o-mini
- **RAG:** Supabase (pgvector)
- **Cache:** Redis

### Data Sources (⏳ PENDING)
- DexScreener API
- DefiLlama API
- Helius (Solana)
- Alchemy (Ethereum)
- RugCheck API
- Token Sniffer

---

## Current Progress

### Phase 1 (✅ 100% Frontend)
- [x] Extension installable
- [x] Chat works (mock data)
- [x] Context detection works
- [x] Token card displays
- [x] Universal search works
- [x] Multi-page detection works
- [x] Floating button works
- [ ] Authentication (BACKEND)
- [ ] Real data from APIs (BACKEND)

### Phase 2 (✅ 100% UI)
- [x] Watchlist UI complete
- [x] Alert config UI complete
- [x] Whale activity UI complete
- [x] Safety score UI complete
- [ ] Real-time data (BACKEND)
- [ ] Browser notifications (BACKEND)

### Phase 3 (✅ 100% UI)
- [x] Token analysis UI complete
- [x] Trading suggestions UI complete
- [x] Portfolio UI complete
- [x] Holder analysis widget
- [x] Market overview widget
- [x] Trending tokens widget
- [x] Live token price/data widgets
- [ ] AI analysis (BACKEND)
- [ ] Wallet connection (BACKEND)

### Phase 4 (✅ 100% UI)
- [x] Chart capture UI complete
- [x] Thread generator UI complete
- [x] Context menu quick actions
- [x] Smart notifications UI
- [x] Keyboard shortcuts (4 shortcuts)
- [ ] AI thread generation (BACKEND)

---

## 🔴 Critical Blockers

1. **Backend Authentication (Story 1.0)**
   - Cần JWT + OAuth
   - Blocks: Settings sync, Chat sync, User data

2. **DexScreener API Integration**
   - Cần real-time token data
   - Blocks: All token-related features

3. **Backend APIs**
   - Settings, Chat, Capture endpoints
   - Blocks: Extension ↔ Web sync

---

## Next Steps

1. 🔴 **PRIORITY: Backend Authentication** - Implement Story 1.0
2. 🔴 **PRIORITY: DexScreener API** - Replace mock data with real data
3. 🔴 **PRIORITY: Backend APIs** - Settings, Chat, Capture endpoints
4. 🟡 **AI Thread Generation** - Backend for Epic 4.2
5. 🟡 **Browser Notifications** - Real-time alerts
6. 🟢 **Wallet Connection** - Portfolio integration

---

## Related Documents

- [PRD v2](../_bmad-output/planning-artifacts/prd.md)
- [Epic 1: AI-Powered Crypto Assistant](./epic-1-ai-powered-crypto-assistant.md)
- [Epic 2: Smart Monitoring & Alerts](./epic-2-smart-monitoring-alerts.md)
- [Epic 3: Trading Intelligence](./epic-3-trading-intelligence.md)
- [Epic 4: Content Creation & Productivity](./epic-4-content-creation-productivity.md)
