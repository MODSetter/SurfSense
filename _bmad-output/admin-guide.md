# Hướng Dẫn Quản Trị SurfSense

**Dành cho Administrators**

---

## 📖 Giới Thiệu

Tài liệu này hướng dẫn administrators cách quản lý và vận hành hệ thống SurfSense.

---

## 🚀 Yêu Cầu Hệ Thống

### Backend Server (Production)
- CPU: 4+ cores
- RAM: 8GB+
- Storage: 100GB+ SSD
- OS: Ubuntu 22.04 LTS

### Database
- PostgreSQL 15+
- RAM: 4GB+
- Storage: 50GB+

### Dependencies
- Python 3.11+
- Node.js 18+
- Docker & Docker Compose
- Redis

---

---

## 🔑 Default Admin Account

**Tài khoản quản trị mặc định:**
- **Email:** `admin@surfsense.ai`
- **Password:** `password123`

> [!WARNING]
> **Bảo mật quan trọng:** Đổi mật khẩu ngay sau khi đăng nhập lần đầu!

---

## 👥 Quản Lý Users


### Tạo User Mới

**Via CLI:**

```bash
cd surfsense_backend
python manage.py create-user \
  --email user@example.com \
  --name "John Doe" \
  --role user \
  --plan pro
```

### Phân Quyền (Roles)

| Role | Permissions |
|------|-------------|
| `user` | Sử dụng tất cả tính năng end-user |
| `admin` | Quản lý users, xem analytics |
| `superadmin` | Quản lý toàn bộ hệ thống |

**Thay đổi role:**

```bash
python manage.py set-role --email user@example.com --role admin
```

### Quản Lý Plans

| Plan | Limits |
|------|--------|
| **Free** | 100 captures/month, 50 AI queries/month, 1GB storage |
| **Pro** | Unlimited captures, 500 AI queries/month, 10GB storage |
| **Enterprise** | Unlimited everything, custom AI models |

---

## ⚙️ Cấu Hình Hệ Thống

### Environment Variables

**File: `surfsense_backend/.env`**

```bash
DATABASE_URL=postgresql://user:password@localhost:5432/surfsense
REDIS_URL=redis://localhost:6379/0

OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...

JWT_SECRET=your-secret-key
JWT_EXPIRY=3600

ENABLE_RESEARCH_MODE=true
RATE_LIMIT_PER_MINUTE=60
LOG_LEVEL=INFO
```

### Database Migrations

```bash
cd surfsense_backend
alembic upgrade head
```

---

## 📊 Monitoring

### Health Check

```bash
curl https://api.surfsense.ai/health
```

**Response:**

```json
{
  "status": "healthy",
  "services": {
    "database": "up",
    "redis": "up",
    "vector_db": "up"
  }
}
```

### Logs

```bash
# Real-time logs
tail -f surfsense_backend/logs/app.log

# Docker logs
docker logs -f surfsense_backend
```

### Performance Metrics

**Via Admin Dashboard:**
- Active Users (real-time, daily, monthly)
- API Response Times (p50, p95, p99)
- Error Rates
- Storage Usage

---

## 🔐 Bảo Mật

### SSL/TLS

```bash
# Install certbot
sudo apt install certbot python3-certbot-nginx

# Obtain certificate
sudo certbot --nginx -d api.surfsense.ai
```

### Backup

**Automated backup script:**

```bash
#!/bin/bash
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/backups/surfsense"

pg_dump -U surfsense surfsense > $BACKUP_DIR/db_$DATE.sql
tar -czf $BACKUP_DIR/uploads_$DATE.tar.gz /var/surfsense/uploads

# Keep last 7 days
find $BACKUP_DIR -type f -mtime +7 -delete
```

**Cron job (2AM daily):**

```bash
0 2 * * * /usr/local/bin/backup.sh >> /var/log/surfsense-backup.log 2>&1
```

---

## 🛠️ Troubleshooting

### Backend Không Start

```bash
# Check logs
tail -n 100 surfsense_backend/logs/app.log

# Test database
python -c "from app.db import engine; engine.connect()"

# Check port
lsof -i :8000
```

### AI Queries Timeout

```bash
# Test AI endpoint
curl -X POST http://localhost:8000/api/ai/chat \
  -H "Authorization: Bearer <token>" \
  -d '{"message": "test"}'

# Check queue
redis-cli LLEN ai_query_queue
```

### Slow Search

```sql
-- Create indexes
CREATE INDEX idx_content_user_id ON content(user_id);
CREATE INDEX idx_content_tags ON content USING GIN(tags);
```

---

## 📦 Deployment

### Docker Compose

```yaml
version: '3.8'
services:
  backend:
    build: ./surfsense_backend
    ports: ["8000:8000"]
    depends_on: [db, redis]
  
  db:
    image: postgres:15
    environment:
      POSTGRES_USER: surfsense
      POSTGRES_PASSWORD: password
  
  redis:
    image: redis:7-alpine
  
  qdrant:
    image: qdrant/qdrant
    ports: ["6333:6333"]
```

**Deploy:**

```bash
docker-compose up -d
```

---

**Cập nhật:** 2026-01-31 | **Version:** 1.0
