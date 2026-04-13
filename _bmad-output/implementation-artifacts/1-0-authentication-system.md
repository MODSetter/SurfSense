# Story 1.0: Hệ thống Xác thực (Authentication System)

Status: ready-for-dev

## Story

**Là một** SurfSense user,
**Tôi muốn** đăng nhập vào extension với tài khoản SurfSense của tôi,
**Để** extension có thể đồng bộ settings, lịch sử chat, và truy cập backend APIs.

## Acceptance Criteria

### AC 1.0.1: User Login Flow
- **Given** user chưa đăng nhập vào extension
- **When** user click nút "Login" trong side panel header
- **Then** Chrome Identity API popup mở ra với tùy chọn Google OAuth
- **And** user hoàn tất quy trình OAuth
- **Then** extension nhận JWT token từ backend
- **And** extension chuyển hướng về side panel
- **And** avatar/email của user hiển thị trong header

**Error Scenario:**
- **Given** user đang trong quy trình OAuth
- **When** OAuth thất bại (user hủy hoặc lỗi mạng)
- **Then** extension hiển thị error toast "Login failed. Please try again."
- **And** user vẫn ở trạng thái chưa xác thực

### AC 1.0.2: JWT Token Management
- **Given** backend trả về JWT token (hết hạn sau 24 giờ - theo config hiện tại)
- **When** extension nhận được token
- **Then** extension lưu encrypted JWT trong Plasmo Storage
- **And** thời gian hết hạn của token được lưu

**Auto-Refresh:**
- **Given** JWT token còn < 1 giờ là hết hạn
- **When** extension kiểm tra token expiry (mỗi 30 phút)
- **Then** extension gọi API `/auth/jwt/refresh`
- **And** extension cập nhật token đã lưu

**Logout:**
- **Given** user click "Logout" trong settings dropdown
- **When** hành động logout được kích hoạt
- **Then** extension xóa JWT khỏi Plasmo Storage
- **And** user chuyển hướng về màn hình welcome/login

### AC 1.0.3: Authenticated API Requests
- **Given** user đã đăng nhập (JWT đã lưu)
- **When** extension thực hiện API request
- **Then** request bao gồm header `Authorization: Bearer {JWT}`
- **And** backend xác thực JWT
- **And** request thành công với status 200

**Expired Token:**
- **Given** JWT token đã hết hạn
- **When** extension thực hiện API request
- **Then** backend trả về lỗi 401 Unauthorized
- **And** extension cố gắng auto-refresh
- **And** nếu refresh thành công, thử lại request ban đầu
- **And** nếu refresh thất bại, chuyển hướng user đến trang login

### AC 1.0.4: Offline Handling
- **Given** user đã đăng nhập trước đó
- **And** user mất kết nối internet
- **When** extension cố gắng kết nối backend
- **Then** extension hiển thị chỉ báo "Offline" trong header
- **And** extension cache trạng thái auth gần nhất

## Tasks / Subtasks

- [ ] Task 1: Chrome Identity API Integration (AC: 1.0.1)
  - [ ] 1.1 Tạo `lib/auth/chrome-identity.ts` - wrapper cho Chrome Identity API
  - [ ] 1.2 Implement `launchWebAuthFlow` với backend OAuth URL
  - [ ] 1.3 Handle OAuth callback và extract JWT từ redirect URL
  - [ ] 1.4 Xử lý các error cases (user cancel, network error)

- [ ] Task 2: JWT Token Manager (AC: 1.0.2)
  - [ ] 2.1 Tạo `lib/auth/jwt-manager.ts` - quản lý JWT storage
  - [ ] 2.2 Implement token encryption/decryption với Plasmo Storage
  - [ ] 2.3 Implement token expiry checking và auto-refresh logic
  - [ ] 2.4 Implement logout và clear token

- [ ] Task 3: Authenticated API Client (AC: 1.0.3)
  - [ ] 3.1 Tạo `lib/auth/api-client.ts` - HTTP client với auth headers
  - [ ] 3.2 Implement request interceptor để inject Bearer token
  - [ ] 3.3 Implement 401 response handler với auto-retry
  - [ ] 3.4 Implement offline detection và caching

- [ ] Task 4: Auth UI Components (AC: 1.0.1, 1.0.4)
  - [ ] 4.1 Tạo `sidepanel/auth/LoginButton.tsx` - nút đăng nhập
  - [ ] 4.2 Tạo `sidepanel/auth/UserProfile.tsx` - hiển thị avatar/email
  - [ ] 4.3 Tạo `sidepanel/auth/AuthProvider.tsx` - React context cho auth state
  - [ ] 4.4 Update `sidepanel/chat/ChatHeader.tsx` để integrate auth UI

- [ ] Task 5: Integration Testing
  - [ ] 5.1 Test OAuth flow end-to-end
  - [ ] 5.2 Test token refresh mechanism
  - [ ] 5.3 Test offline mode behavior
  - [ ] 5.4 Test logout flow

## Dev Notes

### Backend Authentication (ALREADY EXISTS)
Backend đã có đầy đủ authentication system sử dụng `fastapi-users`:

**Existing Endpoints:**
```
POST /auth/jwt/login          - Email/password login
POST /auth/jwt/logout         - Logout
GET  /auth/google/authorize   - Google OAuth initiation
GET  /auth/google/callback    - Google OAuth callback
POST /auth/register           - User registration
GET  /verify-token            - Verify JWT validity
GET  /users/me                - Get current user info
```

**JWT Configuration (từ `surfsense_backend/app/users.py`):**
- Secret: `config.SECRET_KEY`
- Lifetime: 24 giờ (`3600 * 24` seconds)
- Transport: Bearer token
- OAuth redirect: `{NEXT_FRONTEND_URL}/auth/callback?token={token}`

### Extension Architecture Pattern

**Plasmo Storage (đã có trong project):**
```typescript
import { Storage } from "@plasmohq/storage";
const storage = new Storage({ area: "local" });
```

**Chrome Identity API:**
```typescript
chrome.identity.launchWebAuthFlow({
  url: `${BACKEND_URL}/auth/google/authorize`,
  interactive: true,
}, (redirectUrl) => {
  // Extract JWT from redirect URL
  const url = new URL(redirectUrl);
  const token = url.searchParams.get('token');
});
```

### Critical Implementation Details

**1. OAuth Flow cho Extension:**
- Backend hiện redirect về `{NEXT_FRONTEND_URL}/auth/callback?token={token}`
- Extension cần sử dụng Chrome Identity API với custom redirect
- Có thể cần thêm endpoint mới hoặc config cho extension redirect

**2. Token Storage Security:**
- KHÔNG lưu plaintext JWT
- Sử dụng encryption trước khi lưu vào Plasmo Storage
- Xem xét sử dụng `chrome.storage.session` cho sensitive data

**3. CORS Configuration:**
Backend đã có CORS cho localhost, cần thêm extension origin:
```python
# surfsense_backend/app/app.py - line 74-81
allowed_origins.extend([
    "chrome-extension://*",  # Cần thêm
])
```

### Project Structure Notes

**Files cần tạo mới:**
```
surfsense_browser_extension/
├── lib/
│   └── auth/
│       ├── chrome-identity.ts    # Chrome Identity API wrapper
│       ├── jwt-manager.ts        # JWT storage & refresh
│       └── api-client.ts         # Authenticated HTTP client
└── sidepanel/
    └── auth/
        ├── LoginButton.tsx       # Login UI component
        ├── UserProfile.tsx       # User avatar/menu
        └── AuthProvider.tsx      # Auth context provider
```

**Files cần modify:**
- `sidepanel/chat/ChatHeader.tsx` - Thêm auth UI
- `sidepanel/index.tsx` - Wrap với AuthProvider
- `background/index.ts` - Handle auth messages (nếu cần)

### Dependencies

**Existing (không cần cài thêm):**
- `@plasmohq/storage` - Đã có
- `react`, `react-dom` - Đã có
- `lucide-react` - Đã có (cho icons)

**Backend Dependencies (đã có):**
- `fastapi-users` - Authentication framework
- `httpx-oauth` - Google OAuth client
- `python-jose` - JWT handling

### Security Considerations

1. **KHÔNG** lưu API keys trong extension code
2. Mã hóa JWT trước khi lưu vào storage
3. Sử dụng HTTPS cho tất cả API calls
4. Validate JWT signature trên backend (đã có)
5. Implement CSRF protection cho OAuth flow

### References

- [Source: surfsense_backend/app/users.py] - JWT strategy, OAuth config
- [Source: surfsense_backend/app/app.py#L91-160] - Auth routes registration
- [Source: _bmad-epics/epic-1-ai-powered-crypto-assistant.md#Story-1.0] - Full requirements
- [Source: _bmad-output/architecture-extension.md] - Extension architecture
- [Source: _bmad-output/architecture-backend.md] - Backend auth flow

## Dev Agent Record

### Agent Model Used
{{agent_model_name_version}}

### Completion Notes List
- Story created: 2026-02-04
- Backend auth system already exists and is fully functional
- Extension needs new auth layer to integrate with existing backend
- P0 BLOCKER - This story blocks all sync features (Settings, Chat, Capture)

### Debug Log References
(To be filled during implementation)

### File List
(To be filled during implementation)

