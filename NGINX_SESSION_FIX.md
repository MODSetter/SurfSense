# Nginx Configuration Fix for Session Persistence

## Problem
The `/verify-token` endpoint was added to the backend in commit edfc49b to fix session persistence issues, but nginx was not configured to proxy this endpoint to the backend. This caused the request to be routed to the frontend instead, resulting in a 404 error and breaking session verification.

## Root Cause
The nginx configuration at `/etc/nginx/sites-available/ai.kapteinis.lv` had specific location blocks for:
- `/auth/*` → backend
- `/users/` → backend
- `/api/` → backend
- `/docs` → backend
- `/` → frontend (catch-all)

The `/verify-token` endpoint did not match any backend location patterns, so it was being routed to the frontend by the catch-all `location /` block.

## Solution
Added a dedicated location block for `/verify-token` that proxies requests to the backend on port 8000:

```nginx
# Token verification endpoint (required for session persistence)
location /verify-token {
    proxy_pass http://127.0.0.1:8000;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    
    proxy_read_timeout 300s;
    proxy_connect_timeout 75s;
}
```

## Changes Made
1. **Backed up** existing nginx config: `/etc/nginx/sites-available/ai.kapteinis.lv.backup.TIMESTAMP`
2. **Added** `/verify-token` location block before the catch-all `location /` block
3. **Tested** nginx configuration: `nginx -t`
4. **Reloaded** nginx: `systemctl reload nginx`

## Verification
Test the endpoint:
```bash
# Without token - should return Unauthorized
curl -s https://ai.kapteinis.lv/verify-token

# With valid token - should return user data
curl -s -H "Authorization: Bearer YOUR_TOKEN" https://ai.kapteinis.lv/verify-token
```

## Impact
- ✅ Session persistence now works correctly
- ✅ Users stay logged in after page refresh
- ✅ No more "Your session has expired" errors immediately after login

## Configuration Environment
- **Server:** ai.kapteinis.lv (46.62.230.195)
- **Nginx version:** Check with `nginx -v`
- **Backend:** FastAPI on port 8000
- **Frontend:** Next.js on port 3000
- **SSL:** Let's Encrypt certificates

## Related Files
- Backend endpoint: `surfsense_backend/app/app.py` (line 135)
- Nginx config: `/etc/nginx/sites-available/ai.kapteinis.lv`
- Documentation: `DEPLOYMENT_FIX.md`
