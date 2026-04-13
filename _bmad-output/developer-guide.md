# Hướng Dẫn Developer SurfSense

**Dành cho Nhà Phát Triển**

---

## 📖 Giới Thiệu

Tài liệu này hướng dẫn developers cách setup, develop, và extend hệ thống SurfSense.

---

## 🏗️ Kiến Trúc Tổng Quan

SurfSense bao gồm 3 components chính:

1. **Backend** (`surfsense_backend`) - Python/FastAPI
2. **Web** (`surfsense_web`) - Next.js 16
3. **Extension** (`surfsense_browser_extension`) - Plasmo/React

Xem chi tiết:
- [Kiến Trúc Backend](./architecture-backend.md)
- [Kiến Trúc Web](./architecture-web.md)
- [Kiến Trúc Extension](./architecture-extension.md)
- [Kiến Trúc Tích Hợp](./integration-architecture.md)

---

## 🚀 Setup Development Environment

### Prerequisites

- Python 3.11+
- Node.js 18+
- PostgreSQL 15+
- Redis
- Git

### Clone Repository

```bash
git clone https://github.com/your-org/surfsense.git
cd surfsense
```

### Backend Setup

```bash
cd surfsense_backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Setup environment
cp .env.example .env
# Edit .env với database credentials, API keys

# Run migrations
alembic upgrade head

# Start server
uvicorn app.main:app --reload
```

**Backend chạy tại:** `http://localhost:8000`

### Web Setup

```bash
cd surfsense_web

# Install dependencies
npm install

# Setup environment
cp .env.example .env.local
# Edit NEXT_PUBLIC_API_URL=http://localhost:8000

# Start dev server
npm run dev
```

**Web chạy tại:** `http://localhost:3000`

### Extension Setup

```bash
cd surfsense_browser_extension

# Install dependencies
npm install

# Build extension
npm run dev

# Load extension trong Chrome:
# 1. Vào chrome://extensions/
# 2. Enable "Developer mode"
# 3. Click "Load unpacked"
# 4. Chọn folder build/chrome-mv3-dev
```

---

## 🗂️ Cấu Trúc Dự Án

### Backend Structure

```
surfsense_backend/
├── app/
│   ├── api/          # API routes
│   ├── core/         # Core logic (auth, config)
│   ├── db/           # Database models
│   ├── services/     # Business logic
│   └── main.py       # FastAPI app
├── alembic/          # Database migrations
├── tests/            # Unit tests
└── requirements.txt
```

### Web Structure

```
surfsense_web/
├── app/              # Next.js App Router
│   ├── (auth)/       # Auth pages
│   ├── (dashboard)/  # Dashboard pages
│   └── api/          # API routes
├── components/       # React components
├── lib/              # Utilities
└── public/           # Static assets
```

### Extension Structure

```
surfsense_browser_extension/
├── src/
│   ├── background/   # Background service
│   ├── popup/        # Popup UI
│   ├── content/      # Content scripts
│   └── components/   # Shared components
└── manifest.json     # Extension manifest
```

---

## 🔌 API Reference

### Authentication

**Login:**

```bash
POST /api/auth/login
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "password123"
}

# Response:
{
  "access_token": "eyJ...",
  "token_type": "bearer"
}
```

**Sử dụng token:**

```bash
GET /api/content
Authorization: Bearer eyJ...
```

### Content Management

**Capture content:**

```bash
POST /api/content
Authorization: Bearer <token>
Content-Type: application/json

{
  "url": "https://example.com",
  "title": "Example Page",
  "body": "Content text...",
  "tags": ["research", "ai"]
}
```

**Search:**

```bash
GET /api/search?q=machine+learning&limit=10
Authorization: Bearer <token>
```

### AI Chat

**Send message:**

```bash
POST /api/ai/chat
Authorization: Bearer <token>
Content-Type: application/json

{
  "message": "Summarize my AI research",
  "mode": "research"  # "chat" | "research"
}
```

Xem chi tiết: [API Contracts](./api-contracts-backend.md)

---

## 🗄️ Database Schema

### Core Tables

**users:**
- `id` (UUID, PK)
- `email` (unique)
- `hashed_password`
- `role` (user | admin | superadmin)
- `plan` (free | pro | enterprise)

**content:**
- `id` (UUID, PK)
- `user_id` (FK → users)
- `url`, `title`, `body`
- `tags` (JSONB)
- `created_at`

**collections:**
- `id` (UUID, PK)
- `user_id` (FK → users)
- `name`, `description`

Xem chi tiết: [Data Models](./data-models-backend.md)

---

## 🧪 Testing

### Backend Tests

```bash
cd surfsense_backend

# Run all tests
pytest

# Run specific test
pytest tests/test_auth.py

# With coverage
pytest --cov=app tests/
```

### Web Tests

```bash
cd surfsense_web

# Run unit tests
npm test

# Run E2E tests
npm run test:e2e
```

### Extension Tests

```bash
cd surfsense_browser_extension

# Run tests
npm test
```

---

## 🔧 Common Development Tasks

### Tạo API Endpoint Mới

**1. Tạo route (`app/api/routes/example.py`):**

```python
from fastapi import APIRouter, Depends
from app.core.auth import get_current_user

router = APIRouter()

@router.get("/example")
async def get_example(user = Depends(get_current_user)):
    return {"message": "Hello", "user_id": user.id}
```

**2. Register route (`app/api/__init__.py`):**

```python
from app.api.routes import example

api_router.include_router(example.router, prefix="/example", tags=["example"])
```

### Tạo Database Migration

```bash
cd surfsense_backend

# Auto-generate migration
alembic revision --autogenerate -m "Add new_column to users"

# Review migration file in alembic/versions/

# Apply migration
alembic upgrade head
```

### Thêm React Component Mới

**1. Tạo component (`components/MyComponent.tsx`):**

```tsx
export function MyComponent({ title }: { title: string }) {
  return <div>{title}</div>
}
```

**2. Sử dụng:**

```tsx
import { MyComponent } from '@/components/MyComponent'

export default function Page() {
  return <MyComponent title="Hello" />
}
```

---

## 🚢 Deployment

### Build Production

**Backend:**

```bash
cd surfsense_backend
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

**Web:**

```bash
cd surfsense_web
npm run build
npm start
```

**Extension:**

```bash
cd surfsense_browser_extension
npm run build
# Upload build/chrome-mv3-prod to Chrome Web Store
```

### Docker Deployment

```bash
docker-compose up -d
```

Xem chi tiết deployment trong [Admin Guide](./admin-guide.md).

---

## 🐛 Debugging

### Backend Debugging

**Enable debug logs:**

```bash
# .env
LOG_LEVEL=DEBUG
```

**Use debugger:**

```python
import pdb; pdb.set_trace()
```

### Web Debugging

**Next.js debug mode:**

```bash
NODE_OPTIONS='--inspect' npm run dev
```

**React DevTools:** Install extension

### Extension Debugging

1. Vào `chrome://extensions/`
2. Click **"Inspect views: background page"**
3. Sử dụng Chrome DevTools

---

## 📚 Tài Nguyên Bổ Sung

### Documentation
- [FastAPI Docs](https://fastapi.tiangolo.com/)
- [Next.js Docs](https://nextjs.org/docs)
- [Plasmo Docs](https://docs.plasmo.com/)

### Code Style
- Backend: PEP 8, Black formatter
- Web/Extension: ESLint, Prettier

### Git Workflow
- Branch naming: `feature/`, `bugfix/`, `hotfix/`
- Commit messages: Conventional Commits
- PR template: Mô tả changes, testing done

---

**Cập nhật:** 2026-01-31 | **Version:** 1.0
