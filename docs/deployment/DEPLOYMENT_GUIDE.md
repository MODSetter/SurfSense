# SurfSense Deployment Guide

## Overview

This guide provides comprehensive instructions for deploying and maintaining SurfSense on a VPS (Virtual Private Server). It covers initial deployment, common issues and fixes, and verification procedures.

## VPS Deployment

### Server Requirements

- **RAM**: 30 GiB minimum
- **Storage**: 50 GiB recommended
- **OS**: Ubuntu 20.04+ or similar Linux distribution
- **Python**: 3.11+
- **Node.js**: 20+

### Initial Setup

1. **Clone the repository:**
   ```bash
   cd /opt
   git clone https://github.com/okapteinis/SurfSense.git
   cd SurfSense
   ```

2. **Set up Python environment:**
   ```bash
   cd surfsense_backend
   python3 -m venv venv
   source venv/bin/activate
   pip install -e .
   ```

3. **Configure secrets:**
   - See `docs/development/SECRETS_MANAGEMENT.md` for SOPS setup
   - Decrypt secrets: `sops -d secrets.enc.yaml > secrets.yaml`
   - Copy environment template: `cp .env.example .env`
   - Update `.env` with your configuration

4. **Set up database:**
   ```bash
   # Install PostgreSQL
   sudo apt-get install postgresql postgresql-contrib

   # Create database and user
   sudo -u postgres psql
   CREATE DATABASE surfsense;
   CREATE USER surfsense_user WITH PASSWORD 'your_password';
   GRANT ALL PRIVILEGES ON DATABASE surfsense TO surfsense_user;
   \q

   # Run migrations
   alembic upgrade head
   ```

5. **Set up frontend:**
   ```bash
   cd ../surfsense_web
   npm install -g pnpm
   pnpm install
   cp .env.local.example .env.local
   # Update .env.local with your backend URL
   pnpm build
   ```

6. **Set up systemd services:**
   ```bash
   sudo cp deployment/systemd/*.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable surfsense surfsense-frontend surfsense-celery surfsense-celery-beat
   sudo systemctl start surfsense surfsense-frontend surfsense-celery surfsense-celery-beat
   ```

### Deployment Checklist

When deploying updates to VPS:

- [ ] Pull latest code: `git pull origin nightly`
- [ ] Install dependencies: `pip install -e .` (backend) and `pnpm install` (frontend)
- [ ] Run migrations: `alembic upgrade head`
- [ ] Rebuild frontend if needed: `pnpm build`
- [ ] Restart backend: `systemctl restart surfsense`
- [ ] Restart frontend: `systemctl restart surfsense-frontend`
- [ ] Restart workers: `systemctl restart surfsense-celery surfsense-celery-beat`
- [ ] Check logs: `journalctl -u surfsense -n 50`
- [ ] Test login: Visit your domain

## Common Issues and Fixes

### Issue 1: Session Persistence (Token Verification)

**Problem:**
- Users could log in successfully
- Token was stored in localStorage
- On page refresh, verification would fail with 404
- Frontend would incorrectly redirect to login page

**Root Cause:**
Frontend was calling `/verify-token` endpoint that didn't exist in the backend.

**Fix Applied:**
Added `/verify-token` endpoint that:
- Validates JWT Bearer tokens
- Returns user information if valid
- Returns 401 if expired/invalid
- Enables proper session persistence

**Verification:**
```bash
# Get a token by logging in
TOKEN=$(curl -X POST "http://localhost:8000/api/v1/auth/2fa/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=your@email.com&password=yourpassword&grant_type=password" \
  | grep -o '"access_token":"[^"]*"' | cut -d'"' -f4)

# Test the verify-token endpoint
curl -X GET "http://localhost:8000/verify-token" \
  -H "Authorization: Bearer $TOKEN"

# Should return: {"valid":true,"user":{...}}
```

### Issue 2: Double API Prefix Bug

**Problem:**
- Routes were registered as `/api/v1/api/v1/auth/2fa/login` instead of `/api/v1/auth/2fa/login`
- Frontend calls to `/api/v1/auth/2fa/login` returned 404 Not Found

**Root Cause:**
- Individual routers had `/api/v1/` in their prefix
- These routers were included via `crud_router` which also had `prefix="/api/v1"`
- FastAPI concatenated both prefixes, resulting in double `/api/v1/`

**Fix Applied:**
Changed router prefixes in:
- `app/routes/two_fa_routes.py`: `prefix="/api/v1/auth/2fa"` → `prefix="/auth/2fa"`
- `app/routes/rate_limit_routes.py`: `prefix="/api/v1/rate-limiting"` → `prefix="/rate-limiting"`
- `app/routes/site_configuration_routes.py`: `prefix="/api/v1/site-config"` → `prefix="/site-config"`
- `app/routes/social_media_links_routes.py`: `prefix="/api/v1/social-media-links"` → `prefix="/social-media-links"`

**Pattern to Follow:**
When a router is included via `crud_router` with `prefix="/api/v1"`, child router prefixes should NOT include `/api/v1/`.

```python
# Correct pattern ✅
app.include_router(crud_router, prefix="/api/v1", tags=["crud"])
router = APIRouter(prefix="/auth/2fa")  # No /api/v1/ prefix

# Incorrect pattern ❌
router = APIRouter(prefix="/api/v1/auth/2fa")  # Double prefix!
```

### Issue 3: Bcrypt Library Compatibility

**Problem:**
- `bcrypt 5.0.0` incompatible with `passlib 1.7.4`
- Error: `AttributeError: module 'bcrypt' has no attribute '__about__'`
- Password hashing/verification failed with internal server errors

**Fix:**
- Pinned `bcrypt==4.0.1` in `pyproject.toml`
- Manual downgrade on VPS: `pip install bcrypt==4.0.1`

### Issue 4: Function Parameter Order

**Problem:**
Python syntax error: "parameter without a default follows parameter with a default"

**Fix:**
Reorder parameters so non-default parameters come before default parameters:

```python
# Incorrect ❌
async def login_with_2fa(
    form_data: OAuth2PasswordRequestForm = Depends(),
    http_request: Request,
    session: AsyncSession = Depends(get_async_session),
):

# Correct ✅
async def login_with_2fa(
    http_request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    session: AsyncSession = Depends(get_async_session),
):
```

### Issue 5: CORS Configuration

If experiencing authentication issues across domains, verify CORS settings:

```bash
# Check backend .env file
cat /opt/SurfSense/surfsense_backend/.env | grep -E "CORS_ORIGINS|NEXT_FRONTEND_URL|BACKEND_URL"
```

Ensure correct configuration:
```env
# Frontend URL (must match your domain)
NEXT_FRONTEND_URL=https://your-domain.com

# CORS - allow frontend domain
CORS_ORIGINS=https://your-domain.com

# Backend URL (for OAuth redirects)
BACKEND_URL=https://api.your-domain.com

# If using proxy/Cloudflare
TRUSTED_HOSTS=127.0.0.1,your-cloudflare-ip
```

## Post-Deployment Verification

### 1. Check Service Status

```bash
# Backend
systemctl status surfsense
journalctl -u surfsense -n 50 --no-pager

# Frontend
systemctl status surfsense-frontend
journalctl -u surfsense-frontend -n 50 --no-pager

# Celery workers
systemctl status surfsense-celery surfsense-celery-beat
```

### 2. Test Backend Endpoints

```bash
# Health check
curl http://localhost:8000/health/ready

# Public site configuration
curl http://localhost:8000/api/v1/site-config/public

# Login endpoint
curl -X POST http://localhost:8000/api/v1/auth/2fa/login \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  -d 'username=YOUR_EMAIL&password=YOUR_PASSWORD&grant_type=password'
```

### 3. Test Frontend

1. Open your SurfSense instance in browser
2. Open DevTools (F12)
3. Test login functionality
4. Check Network tab for any 404 or 500 errors
5. Verify token storage in Application → Local Storage

### 4. Test Session Persistence

1. Log in successfully
2. Check localStorage for `surfsense_bearer_token` key
3. Refresh the page (F5)
4. **Should stay logged in** (not redirect to login)

### 5. Verify Database Connection

```bash
# Access psql
sudo -u postgres psql surfsense

# Check counts
SELECT COUNT(*) FROM users;
SELECT COUNT(*) FROM documents;
SELECT COUNT(*) FROM chunks;
\q
```

## Troubleshooting

### Backend Won't Start

1. Check logs: `journalctl -u surfsense -n 100`
2. Common issues:
   - Missing Python packages: `pip install -e .`
   - Database column mismatches: `alembic upgrade head`
   - SOPS decryption failures: Check age keys in `~/.config/sops/age/keys.txt`
   - Environment variables: Verify `.env` file exists and is properly configured

### Frontend Build Errors

1. Check Node.js version: `node --version` (should be 20+)
2. Clear cache and reinstall: `rm -rf node_modules .next && pnpm install`
3. Verify environment variables in `.env.local`
4. Check build logs: `pnpm build 2>&1 | tee build.log`

### Users Getting Logged Out on Refresh

**Check 1: Token is stored**
```javascript
// In browser console
localStorage.getItem('surfsense_bearer_token')
// Should return a long JWT token string
```

**Check 2: Endpoint returns 200**
- Open DevTools → Network tab
- Look for: `GET /verify-token`
- Status should be: `200 OK`

**Check 3: CORS headers**
```bash
curl -X GET "https://api.your-domain.com/verify-token" \
  -H "Origin: https://your-domain.com" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -v
```

Look for:
```
< Access-Control-Allow-Origin: https://your-domain.com
< Access-Control-Allow-Credentials: true
```

### 401 Unauthorized Immediately After Login

**Possible causes:**
1. Token expiration time too short
2. SECRET_KEY mismatch between .env and actual config
3. Token not being sent in Authorization header

**Debug:**
```bash
journalctl -u surfsense -f | grep -i "token\|jwt"
```

## Monitoring and Maintenance

### Health Checks

Set up automated health checks:
```bash
# Add to crontab
*/5 * * * * curl -f http://localhost:8000/health/ready || echo "Backend health check failed"
```

### Log Monitoring

```bash
# Watch backend logs in real-time
journalctl -u surfsense -f

# Watch frontend logs
journalctl -u surfsense-frontend -f

# Watch Celery worker logs
journalctl -u surfsense-celery -f
```

### Database Maintenance

Run periodically for optimal performance:
```sql
VACUUM ANALYZE chunks;
VACUUM ANALYZE documents;
VACUUM ANALYZE users;
```

### Security Updates

1. Regularly update dependencies:
   ```bash
   cd surfsense_backend
   poetry update
   cd ../surfsense_web
   pnpm update
   ```

2. Monitor security vulnerabilities:
   - GitHub Dependabot alerts
   - `poetry run safety check`
   - `pnpm audit`

3. Review and rotate credentials:
   - Database passwords
   - JWT secret keys
   - API keys for third-party services

## Architecture Notes

### FastAPI Router Pattern

```python
# Main app (app.py)
app.include_router(crud_router, prefix="/api/v1", tags=["crud"])

# Child routers
router = APIRouter()
router.include_router(two_fa_router)  # Has prefix="/auth/2fa"
router.include_router(rate_limit_router)  # Has prefix="/rate-limiting"

# Result:
# /api/v1 + /auth/2fa + /login = /api/v1/auth/2fa/login ✅
```

### Service Dependencies

```
┌─────────────┐
│   Nginx     │ ← Reverse proxy
└──────┬──────┘
       │
       ├─────────────────┐
       │                 │
┌──────▼──────┐   ┌──────▼──────┐
│  Frontend   │   │  Backend    │
│  (Next.js)  │   │  (FastAPI)  │
│  Port 3000  │   │  Port 8000  │
└─────────────┘   └──────┬──────┘
                         │
                ┌────────┴────────┐
                │                 │
         ┌──────▼──────┐   ┌──────▼──────┐
         │ PostgreSQL  │   │   Redis     │
         │  (Database) │   │  (Celery)   │
         └─────────────┘   └──────┬──────┘
                                  │
                           ┌──────▼──────┐
                           │   Celery    │
                           │   Workers   │
                           └─────────────┘
```

## Need Help?

If issues persist, collect:
1. Backend logs: `journalctl -u surfsense -n 100 --no-pager`
2. Browser console errors (screenshot)
3. Network tab showing failed requests
4. Environment variables (redact secrets):
   ```bash
   env | grep -E "CORS|FRONTEND|BACKEND|TRUSTED" | sed 's/=.*/=REDACTED/'
   ```

Then open an issue on GitHub with this information.

---

**Last Updated:** November 29, 2025
