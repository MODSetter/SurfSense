# Kiến Trúc Browser Extension

## Tổng Quan
SurfSense Browser Extension là "tai mắt" của hệ thống, cho phép thu thập dữ liệu (ingestion) liền mạch và hỗ trợ người dùng ngay trên bất kỳ trang web nào. Nó được xây dựng bằng **Plasmo Framework**, giúp đơn giản hóa việc phát triển extension cho Chrome (Manifest V3).

## Stack Công Nghệ

| Hạng Mục | Công Nghệ |
|----------|-----------|
| **Framework** | Plasmo |
| **UI** | React 18, Tailwind CSS |
| **Stores** | Storage API (Plasmo Storage) |
| **Messaging** | Plasmo Messaging (Port-based) |

## Các Thành Phần Chính

### 1. Popup (`popup.tsx`)
- Giao diện người dùng xuất hiện khi click vào icon extension.
- **Chức năng**:
    - Đăng nhập/Đăng xuất.
    - Chuyển đổi trạng thái "Tracking" (Bật/Tắt thu thập active tab).
    - Tìm kiếm nhanh (Quick Search) vào kho kiến thức SurfSense.
    - Hiển thị thông báo trạng thái hệ thống.

### 2. Background Service Worker (`background/`)
- Trái tim của extension, chạy ngầm độc lập với các tab.
- **Nhiệm vụ**:
    - **Session Management**: Giữ token xác thực, refresh token khi hết hạn.
    - **Ingestion Queue**: Nhận dữ liệu từ Content Scripts, đóng gói (batching) để tránh spam request, và gửi về Backend API.
    - **Context Awareness**: Giám sát thay đổi URL/Tab để kích hoạt thu thập lại nếu cần.

### 3. Content Scripts
- Scripts chạy trong ngữ cảnh của trang web người dùng đang xem.
- **Nhiệm vụ**:
    - Trích xuất nội dung trang (DOM parsing, Readability.js).
    - Lắng nghe các sự kiện (ví dụ: user copy text -> gợi ý lưu làm note).
    - Inject UI (nếu cần): Hiển thị nút "Lưu vào SurfSense" trực tiếp trên trang.

## Luồng Hoạt Động (Workflows)

### Quy Trình Thu Thập (Ingestion Flow)
1. User truy cập `example.com`.
2. **Content Script** kích hoạt, parse nội dung chính (loại bỏ quảng cáo/footer).
3. Script gửi message chứa nội dung tới **Background Worker**.
4. **Background** kiểm tra:
    - User có đang bật tracking không?
    - Token còn hiệu lực không?
    - Trang này có bị blacklist không (ví dụ: localhost, banking sites)?
5. Nếu hợp lệ, Background đẩy dữ liệu về Backend `POST /api/v1/extension/ingest`.

### Quy Trình Tra Cứu (Lookup Flow)
1. User bôi đen 1 đoạn text trên web.
2. Extension hiển thị tooltip nhỏ.
3. User click "Search in SurfSense".
4. Request gửi về Backend để tìm kiếm các tài liệu liên quan đến đoạn text đó.
5. Kết quả hiển thị ngay trong Side Panel hoặc Popup.

---

## UX Performance Considerations

This section addresses **P1 Issue #6** from the Implementation Readiness Review. It defines performance requirements, optimization strategies, and monitoring approaches to ensure the extension delivers a smooth, responsive user experience.

### Performance Goals

| Metric | Target | Critical Threshold | Measurement |
|--------|--------|-------------------|-------------|
| **Side Panel Open** | <300ms | <500ms | Time from click to panel visible |
| **Token Detection** | <1s | <2s | Time from page load to token card display |
| **AI Response Start** | <2s | <3s | Time from query submit to first token |
| **Chat Message Render** | <100ms | <200ms | Time to render new message in chat |
| **Settings Sync** | <500ms | <1s | Time to fetch and apply settings |
| **Page Capture** | <3s | <5s | Time to capture and upload page |

### 1. Side Panel Rendering Performance

**Challenge:** Side panel must open instantly without blocking the main thread.

**Optimization Strategies:**

```typescript
// 1. Lazy load heavy components
const ChatInterface = lazy(() => import('./ChatInterface'));
const TokenInfoCard = lazy(() => import('./TokenInfoCard'));

// 2. Virtual scrolling for chat history
import { FixedSizeList } from 'react-window';

function ChatHistory({ messages }) {
  return (
    <FixedSizeList
      height={600}
      itemCount={messages.length}
      itemSize={80}
      width="100%"
    >
      {({ index, style }) => (
        <div style={style}>
          <ChatMessage message={messages[index]} />
        </div>
      )}
    </FixedSizeList>
  );
}

// 3. Memoize expensive computations
const TokenCard = memo(({ token }) => {
  const formattedPrice = useMemo(
    () => formatPrice(token.price),
    [token.price]
  );
  
  return <div>{formattedPrice}</div>;
});
```

**Performance Budget:**
- Initial bundle size: <200KB (gzipped)
- Side panel open: <300ms
- Chat scroll: 60fps (16.67ms per frame)

---

### 2. Streaming Response Performance

**Challenge:** Display AI responses as they stream without UI jank.

**Optimization Strategies:**

```typescript
// 1. Debounce UI updates during streaming
function useStreamingResponse(messageId: string) {
  const [content, setContent] = useState('');
  const debouncedContent = useDebouncedValue(content, 50); // Update every 50ms
  
  useEffect(() => {
    const eventSource = new EventSource(`/chat/stream/${messageId}`);
    
    eventSource.onmessage = (event) => {
      const chunk = JSON.parse(event.data);
      setContent(prev => prev + chunk.content);
    };
    
    return () => eventSource.close();
  }, [messageId]);
  
  return debouncedContent;
}

// 2. Use requestAnimationFrame for smooth updates
function StreamingMessage({ content }) {
  const ref = useRef<HTMLDivElement>(null);
  
  useEffect(() => {
    let rafId: number;
    
    const updateContent = () => {
      if (ref.current) {
        ref.current.textContent = content;
      }
    };
    
    rafId = requestAnimationFrame(updateContent);
    return () => cancelAnimationFrame(rafId);
  }, [content]);
  
  return <div ref={ref} />;
}
```

**Performance Budget:**
- Streaming latency: <50ms per chunk
- UI update frequency: 20 updates/second (50ms interval)
- Memory usage: <50MB for 100 messages

---

### 3. Token Detection Performance

**Challenge:** Detect tokens on DexScreener pages without blocking page load.

**Optimization Strategies:**

```typescript
// 1. Use Intersection Observer for lazy detection
const observer = new IntersectionObserver((entries) => {
  entries.forEach(entry => {
    if (entry.isIntersecting) {
      detectToken(entry.target);
      observer.unobserve(entry.target);
    }
  });
});

// 2. Debounce URL changes
const debouncedDetect = debounce((url: string) => {
  const tokenAddress = extractTokenFromURL(url);
  if (tokenAddress) {
    fetchTokenData(tokenAddress);
  }
}, 300);

chrome.tabs.onUpdated.addListener((tabId, changeInfo) => {
  if (changeInfo.url) {
    debouncedDetect(changeInfo.url);
  }
});

// 3. Cache token data aggressively
const tokenCache = new Map<string, { data: TokenData; timestamp: number }>();
const CACHE_TTL = 30_000; // 30 seconds

async function fetchTokenData(address: string) {
  const cached = tokenCache.get(address);
  
  if (cached && Date.now() - cached.timestamp < CACHE_TTL) {
    return cached.data;
  }
  
  const data = await fetch(`/api/tokens/${address}`).then(r => r.json());
  tokenCache.set(address, { data, timestamp: Date.now() });
  
  return data;
}
```

**Performance Budget:**
- Token detection: <1s from page load
- API call: <500ms (with retry)
- Cache hit rate: >80%

---

### 4. Offline Mode & Resilience

**Challenge:** Extension must work gracefully when backend is unavailable.

**Optimization Strategies:**

```typescript
// 1. Service Worker caching for static assets
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open('surfsense-v1').then((cache) => {
      return cache.addAll([
        '/sidepanel.html',
        '/sidepanel.js',
        '/styles.css',
      ]);
    })
  );
});

// 2. IndexedDB for offline chat history
import { openDB } from 'idb';

const db = await openDB('surfsense-chat', 1, {
  upgrade(db) {
    db.createObjectStore('messages', { keyPath: 'id' });
  },
});

async function saveChatMessage(message: ChatMessage) {
  await db.put('messages', message);
}

async function getChatHistory() {
  return await db.getAll('messages');
}

// 3. Optimistic UI updates
function sendMessage(content: string) {
  const optimisticMessage = {
    id: generateId(),
    content,
    status: 'sending',
    timestamp: Date.now(),
  };
  
  // Show immediately
  addMessageToUI(optimisticMessage);
  
  // Send to backend
  fetch('/api/chat/messages', {
    method: 'POST',
    body: JSON.stringify({ content }),
  })
    .then(() => updateMessageStatus(optimisticMessage.id, 'sent'))
    .catch(() => updateMessageStatus(optimisticMessage.id, 'failed'));
}
```

**Performance Budget:**
- Offline mode activation: <100ms
- IndexedDB read: <50ms
- Cache hit rate: >90% for static assets

---

### 5. Memory Management

**Challenge:** Extension must not leak memory during long browsing sessions.

**Optimization Strategies:**

```typescript
// 1. Cleanup event listeners
useEffect(() => {
  const handleMessage = (message: Message) => {
    // Handle message
  };
  
  chrome.runtime.onMessage.addListener(handleMessage);
  
  return () => {
    chrome.runtime.onMessage.removeListener(handleMessage);
  };
}, []);

// 2. Limit chat history in memory
const MAX_MESSAGES_IN_MEMORY = 100;

function addMessage(message: ChatMessage) {
  setMessages(prev => {
    const updated = [...prev, message];
    
    // Keep only last 100 messages in memory
    if (updated.length > MAX_MESSAGES_IN_MEMORY) {
      return updated.slice(-MAX_MESSAGES_IN_MEMORY);
    }
    
    return updated;
  });
}

// 3. Clear caches periodically
setInterval(() => {
  const now = Date.now();
  
  for (const [key, value] of tokenCache.entries()) {
    if (now - value.timestamp > CACHE_TTL) {
      tokenCache.delete(key);
    }
  }
}, 60_000); // Clean every minute
```

**Performance Budget:**
- Memory usage: <100MB after 1 hour
- Memory growth: <10MB per hour
- Cache size: <5MB

---

### 6. Performance Monitoring

**Implementation:**

```typescript
// 1. Performance marks for key operations
performance.mark('sidepanel-open-start');
// ... open side panel
performance.mark('sidepanel-open-end');

performance.measure(
  'sidepanel-open',
  'sidepanel-open-start',
  'sidepanel-open-end'
);

// 2. Send metrics to backend
const metrics = performance.getEntriesByType('measure');

fetch('/api/metrics', {
  method: 'POST',
  body: JSON.stringify({
    metrics: metrics.map(m => ({
      name: m.name,
      duration: m.duration,
      timestamp: Date.now(),
    })),
  }),
});

// 3. Real User Monitoring (RUM)
window.addEventListener('load', () => {
  const perfData = performance.getEntriesByType('navigation')[0];
  
  console.log('Page Load Time:', perfData.loadEventEnd - perfData.fetchStart);
  console.log('DOM Content Loaded:', perfData.domContentLoadedEventEnd - perfData.fetchStart);
});
```

**Monitoring Dashboards:**
- Track P95/P99 latencies for all critical operations
- Alert if any metric exceeds critical threshold
- Weekly performance review with team

---

### Definition of Done (Performance)

- [ ] All performance targets met in production
- [ ] Performance monitoring implemented
- [ ] Offline mode tested and working
- [ ] Memory leaks tested (24-hour stress test)
- [ ] Bundle size optimized (<200KB gzipped)
- [ ] Virtual scrolling for chat history
- [ ] Lazy loading for heavy components
- [ ] Cache hit rate >80% for token data
- [ ] Performance regression tests in CI/CD
