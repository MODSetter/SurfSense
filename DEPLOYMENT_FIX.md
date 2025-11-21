# Session Persistence Fix - Deployment Guide

## Problem Identified

The frontend was calling `/verify-token` endpoint to validate JWT tokens on every page load, but this endpoint didn't exist in the backend. This caused:
- Users could log in successfully
- Token was stored in localStorage
- On page refresh, verification would fail with 404
- Frontend would incorrectly redirect to login page

## Fix Applied

Added `/verify-token` endpoint that:
- Validates JWT Bearer tokens
- Returns user information if valid
- Returns 401 if expired/invalid
- Enables proper session persistence

## Deployment Steps for VPS

### 1. Check Current Status

```bash
# SSH into your VPS
ssh root@your-vps-ip

# Check if backend is running
systemctl status surfsense-backend
# or if using PM2:
pm2 status

# Check backend logs for any errors
journalctl -u surfsense-backend -n 50 --no-pager
# or for PM2:
pm2 logs surfsense-backend --lines 50
```

### 2. Pull Latest Changes

```bash
# Navigate to project directory
cd /opt/SurfSense  # Or your actual path

# Pull latest changes
git fetch origin
git checkout claude/pr108-feedback-01KvXspEYF5Mp3NkJREQ7r71
git pull origin claude/pr108-feedback-01KvXspEYF5Mp3NkJREQ7r71
```

### 3. Restart Backend Service

```bash
# If using systemd:
systemctl restart surfsense-backend
systemctl status surfsense-backend

# If using PM2:
pm2 restart surfsense-backend
pm2 logs surfsense-backend --lines 20

# If using Docker:
docker-compose restart backend
docker-compose logs -f backend --tail=20
```

### 4. Verify the Fix

#### A. Test the endpoint directly

```bash
# First, get a token by logging in (replace with your credentials)
TOKEN=$(curl -X POST "http://localhost:8000/api/v1/auth/2fa/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=your@email.com&password=yourpassword&grant_type=password" \
  | grep -o '"access_token":"[^"]*"' | cut -d'"' -f4)

echo "Token: $TOKEN"

# Test the verify-token endpoint
curl -X GET "http://localhost:8000/verify-token" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json"

# Should return:
# {"valid":true,"user":{"id":"...","email":"your@email.com",...}}
```

#### B. Check backend logs

```bash
# Watch logs in real-time during login test
journalctl -u surfsense-backend -f
# or
pm2 logs surfsense-backend --lines 0
```

Look for:
- ✅ `Token verified successfully for user <email>`
- ❌ No 404 errors for `/verify-token`

#### C. Test from browser

1. Open browser DevTools (F12)
2. Go to Network tab
3. Log in to your SurfSense instance
4. Refresh the page
5. Look for `/verify-token` request:
   - Should return **200 OK** with user data
   - Should **NOT** return 404

### 5. Check Cookie/CORS Configuration

If you're still having issues, check your environment variables:

```bash
# Check backend .env file
cat /opt/SurfSense/surfsense_backend/.env | grep -E "CORS_ORIGINS|NEXT_FRONTEND_URL|BACKEND_URL"
```

Ensure:
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

### 6. Frontend Environment Check

```bash
# Check frontend .env.local file
cat /opt/SurfSense/surfsense_web/.env.local | grep NEXT_PUBLIC_FASTAPI_BACKEND_URL
```

Should be:
```env
NEXT_PUBLIC_FASTAPI_BACKEND_URL=https://api.your-domain.com
```

### 7. Test Session Persistence

1. Open your SurfSense instance in browser
2. Open DevTools → Application → Local Storage
3. Log in successfully
4. Check localStorage for `surfsense_bearer_token` key
5. Refresh the page (F5)
6. **Should stay logged in** (not redirect to login)

## Troubleshooting

### Issue: Still getting logged out on refresh

**Check 1: Token is stored**
```javascript
// In browser console
localStorage.getItem('surfsense_bearer_token')
// Should return a long JWT token string
```

**Check 2: Endpoint returns 200**
```bash
# Check Network tab in DevTools
# Look for: GET /verify-token
# Status should be: 200 OK
```

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

### Issue: 401 Unauthorized immediately after login

**Possible causes:**
1. Token expiration time too short (check users.py → `lifetime_seconds`)
2. SECRET_KEY mismatch between .env and actual config
3. Token not being sent in Authorization header

**Debug:**
```bash
# Check token generation in backend logs
journalctl -u surfsense-backend -f | grep -i "token\|jwt"
```

### Issue: Mixed content warnings (HTTP/HTTPS)

If frontend is HTTPS but backend is HTTP:
```bash
# Ensure backend uses HTTPS in production
# Update nginx/caddy config to proxy with HTTPS
# Or use Cloudflare Tunnel
```

## Verification Checklist

- [ ] Backend service restarted successfully
- [ ] `/verify-token` endpoint returns 200 (not 404)
- [ ] Can log in successfully
- [ ] Token appears in localStorage
- [ ] Page refresh keeps user logged in
- [ ] No CORS errors in browser console
- [ ] Backend logs show "Token verified successfully"

## Additional Monitoring

Set up health checks to monitor authentication:

```bash
# Add to crontab for monitoring
*/5 * * * * curl -f http://localhost:8000/health/ready || echo "Backend health check failed"
```

## Need Help?

If issues persist, collect:
1. Backend logs: `journalctl -u surfsense-backend -n 100 --no-pager`
2. Browser console errors (screenshot)
3. Network tab showing failed `/verify-token` request
4. Environment variables (redact secrets):
   ```bash
   env | grep -E "CORS|FRONTEND|BACKEND|TRUSTED" | sed 's/=.*/=REDACTED/'
   ```

Then open an issue with this information.
