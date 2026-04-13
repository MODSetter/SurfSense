# Story 1.6: Đồng bộ Cài đặt (Settings Sync) với Frontend

Status: ready-for-dev

## Story

**Là một** SurfSense user,
**Tôi muốn** extension sử dụng cùng model và search space như web dashboard,
**Để** tôi không phải cấu hình lại.

## Dependencies

- **REQUIRES:** Story 1.0 (Authentication System) - Must be completed first
- Extension must have valid JWT token to call backend APIs

## Acceptance Criteria

### AC 1.6.1: Hiển thị Dropdown Cài đặt
- **Given** user đã đăng nhập
- **When** user click icon ⚙️ trong header
- **Then** settings dropdown mở ra
- **And** dropdown hiển thị:
  - Current model: "GPT-4 Turbo" (chỉ xem, bị mờ)
  - Current search space: "Crypto Research" (chỉ xem, bị mờ)
  - Links đến web dashboard:
    - "🔗 Manage Connectors"
    - "💬 View All Chats"
    - "⚙️ Full Settings"
  - Nút "🚪 Logout"

### AC 1.6.2: Đồng bộ Cài đặt khi Đăng nhập
- **Given** user hoàn tất đăng nhập
- **When** nhận được JWT token
- **Then** extension gọi `GET /api/v1/searchspaces` để lấy danh sách search spaces
- **And** extension gọi `GET /api/v1/search-spaces/{id}/llm-preferences` để lấy LLM config
- **And** settings được lưu trong Plasmo Storage
- **And** settings hiển thị trong dropdown

**Response Format (từ backend):**
```json
// GET /api/v1/searchspaces
[
  {
    "id": 1,
    "name": "Crypto Research",
    "description": "...",
    "agent_llm_id": 0,
    "document_summary_llm_id": 0
  }
]

// GET /api/v1/search-spaces/{id}/llm-preferences
{
  "agent_llm_id": 0,
  "document_summary_llm_id": 0,
  "agent_llm": {
    "id": 0,
    "name": "Auto (Load Balanced)",
    "provider": "AUTO",
    "model_name": "auto"
  }
}
```

### AC 1.6.3: Tự động cập nhật Cài đặt
- **Given** user thay đổi model trên web dashboard
- **When** extension phát hiện thay đổi (qua polling)
- **Then** extension lấy settings đã cập nhật
- **And** dropdown phản ánh model mới
- **And** các cuộc chat tiếp theo sử dụng model mới

**Polling:**
- **Given** extension đang hoạt động
- **When** mỗi 5 phút
- **Then** extension polls `GET /api/v1/searchspaces` và LLM preferences

### AC 1.6.4: Search Space Selector
- **Given** user có nhiều search spaces
- **When** user click vào search space selector trong header
- **Then** dropdown hiển thị tất cả search spaces của user
- **And** user có thể chọn search space khác
- **And** extension lưu selection vào Plasmo Storage
- **And** các API calls tiếp theo sử dụng search_space_id mới

### AC 1.6.5: Offline Handling
- **Given** user đã đăng nhập và có settings đã cache
- **When** user mất kết nối internet
- **Then** extension sử dụng settings đã cache
- **And** hiển thị indicator "Using cached settings"
- **When** kết nối được khôi phục
- **Then** extension sync settings mới từ backend

## Tasks / Subtasks

- [ ] Task 1: Settings Service (AC: 1.6.2, 1.6.3)
  - [ ] 1.1 Tạo `lib/settings/settings-service.ts` - API calls cho settings
  - [ ] 1.2 Implement `fetchSearchSpaces()` - GET /api/v1/searchspaces
  - [ ] 1.3 Implement `fetchLLMPreferences(spaceId)` - GET LLM config
  - [ ] 1.4 Implement polling mechanism (5 phút interval)
  - [ ] 1.5 Implement settings caching trong Plasmo Storage

- [ ] Task 2: Settings State Management (AC: 1.6.1, 1.6.4)
  - [ ] 2.1 Tạo `lib/settings/settings-store.ts` - Zustand/Context store
  - [ ] 2.2 Define settings types và interfaces
  - [ ] 2.3 Implement search space selection logic
  - [ ] 2.4 Implement settings sync on login

- [ ] Task 3: Settings UI Components (AC: 1.6.1, 1.6.4)
  - [ ] 3.1 Update `sidepanel/chat/ChatHeader.tsx` - Integrate real settings
  - [ ] 3.2 Tạo `sidepanel/settings/SettingsDropdown.tsx` - Enhanced dropdown
  - [ ] 3.3 Tạo `sidepanel/settings/SearchSpaceSelector.tsx` - Space picker
  - [ ] 3.4 Tạo `sidepanel/settings/ModelDisplay.tsx` - Read-only model info

- [ ] Task 4: Integration với Auth (AC: 1.6.2, 1.6.5)
  - [ ] 4.1 Hook settings fetch vào auth flow (sau login thành công)
  - [ ] 4.2 Implement offline detection và fallback
  - [ ] 4.3 Clear settings on logout
  - [ ] 4.4 Handle 401 errors (redirect to login)

- [ ] Task 5: Testing
  - [ ] 5.1 Test settings sync sau login
  - [ ] 5.2 Test polling mechanism
  - [ ] 5.3 Test search space switching
  - [ ] 5.4 Test offline mode với cached settings

## Dev Notes

### Backend APIs (ALREADY EXISTS)

Backend đã có đầy đủ APIs cho settings:

**Search Spaces:**
```
GET  /api/v1/searchspaces                           - List all user's search spaces
POST /api/v1/searchspaces                           - Create new search space
GET  /api/v1/searchspaces/{id}                      - Get single search space
PUT  /api/v1/searchspaces/{id}                      - Update search space
DELETE /api/v1/searchspaces/{id}                    - Delete search space
```

**LLM Preferences:**
```
GET  /api/v1/search-spaces/{id}/llm-preferences     - Get LLM config for space
PUT  /api/v1/search-spaces/{id}/llm-preferences     - Update LLM config
```

**Global LLM Configs:**
```
GET  /api/v1/global-new-llm-configs                 - List available LLM models
```

### Existing Extension Code

**ChatHeader.tsx (đã có UI cơ bản):**
- Search space selector dropdown (hardcoded data)
- Settings dropdown với menu items
- User avatar với logout
- Token search bar

**Cần update:**
- Replace hardcoded search spaces với real data từ API
- Add model display trong settings dropdown
- Connect logout button với auth service

### Data Types

**SearchSpace (từ backend):**
```typescript
interface SearchSpace {
  id: number;
  name: string;
  description?: string;
  user_id: string;
  agent_llm_id: number;
  document_summary_llm_id: number;
  created_at: string;
}
```

**LLMPreferences (từ backend):**
```typescript
interface LLMPreferences {
  agent_llm_id: number;
  document_summary_llm_id: number;
  agent_llm?: LLMConfig;
  document_summary_llm?: LLMConfig;
}

interface LLMConfig {
  id: number;
  name: string;
  provider: string;
  model_name: string;
  is_global?: boolean;
  is_auto_mode?: boolean;
}
```

### Project Structure Notes

**Files cần tạo mới:**
```
surfsense_browser_extension/
├── lib/
│   └── settings/
│       ├── settings-service.ts    # API calls
│       ├── settings-store.ts      # State management
│       └── types.ts               # TypeScript interfaces
└── sidepanel/
    └── settings/
        ├── SettingsDropdown.tsx   # Enhanced dropdown
        ├── SearchSpaceSelector.tsx # Space picker
        └── ModelDisplay.tsx       # Read-only model info
```

**Files cần modify:**
- `sidepanel/chat/ChatHeader.tsx` - Integrate real settings data
- `sidepanel/index.tsx` - Add SettingsProvider
- `lib/auth/api-client.ts` - Add settings endpoints (từ Story 1.0)

### Implementation Pattern

**Settings Service:**
```typescript
// lib/settings/settings-service.ts
import { apiClient } from '../auth/api-client';

export const settingsService = {
  async fetchSearchSpaces(): Promise<SearchSpace[]> {
    return apiClient.get('/api/v1/searchspaces');
  },

  async fetchLLMPreferences(spaceId: number): Promise<LLMPreferences> {
    return apiClient.get(`/api/v1/search-spaces/${spaceId}/llm-preferences`);
  },

  async fetchGlobalLLMConfigs(): Promise<LLMConfig[]> {
    return apiClient.get('/api/v1/global-new-llm-configs');
  }
};
```

**Settings Store (Plasmo Storage):**
```typescript
// lib/settings/settings-store.ts
import { Storage } from "@plasmohq/storage";

const storage = new Storage({ area: "local" });

export const settingsStore = {
  async saveSearchSpaces(spaces: SearchSpace[]) {
    await storage.set('searchSpaces', spaces);
  },

  async getSearchSpaces(): Promise<SearchSpace[] | null> {
    return storage.get('searchSpaces');
  },

  async saveSelectedSpaceId(id: number) {
    await storage.set('selectedSearchSpaceId', id);
  },

  async getSelectedSpaceId(): Promise<number | null> {
    return storage.get('selectedSearchSpaceId');
  }
};
```

### Polling Implementation

```typescript
// Polling every 5 minutes
const POLLING_INTERVAL = 5 * 60 * 1000; // 5 minutes

useEffect(() => {
  const pollSettings = async () => {
    try {
      const spaces = await settingsService.fetchSearchSpaces();
      await settingsStore.saveSearchSpaces(spaces);

      const selectedId = await settingsStore.getSelectedSpaceId();
      if (selectedId) {
        const prefs = await settingsService.fetchLLMPreferences(selectedId);
        await settingsStore.saveLLMPreferences(prefs);
      }
    } catch (error) {
      console.error('Settings poll failed:', error);
    }
  };

  const interval = setInterval(pollSettings, POLLING_INTERVAL);
  return () => clearInterval(interval);
}, []);
```

### Security Considerations

1. Settings API calls require valid JWT (handled by api-client)
2. Cache settings locally for offline access
3. Clear cached settings on logout
4. Handle 401 errors gracefully (redirect to login)

### References

- [Source: surfsense_backend/app/routes/search_spaces_routes.py] - Search space APIs
- [Source: surfsense_backend/app/routes/new_llm_config_routes.py] - LLM config APIs
- [Source: surfsense_browser_extension/sidepanel/chat/ChatHeader.tsx] - Existing UI
- [Source: _bmad-epics/epic-1-ai-powered-crypto-assistant.md#Story-1.6] - Full requirements
- [Source: _bmad-output/implementation-artifacts/1-0-authentication-system.md] - Auth dependency

## Dev Agent Record

### Agent Model Used
{{agent_model_name_version}}

### Completion Notes List
- Story created: 2026-02-04
- Backend APIs already exist and are fully functional
- Extension UI partially exists (ChatHeader.tsx has basic structure)
- DEPENDS ON Story 1.0 (Authentication) - must complete auth first
- Settings are read-only in extension (changes made via web dashboard)

### Debug Log References
(To be filled during implementation)

### File List
(To be filled during implementation)

