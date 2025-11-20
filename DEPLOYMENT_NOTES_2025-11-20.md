# Deployment Notes - November 20, 2025

## Login 404 Issue Fix & VPS Synchronization

### Summary
Fixed critical login issue where frontend was receiving 404 errors when attempting to authenticate. The root cause was a double API prefix issue introduced during the 2FA and rate limiting feature merge.

---

## Issues Fixed

### 1. **Double API Prefix Bug** ✅
**Problem:**
- Routes were registered as `/api/v1/api/v1/auth/2fa/login` instead of `/api/v1/auth/2fa/login`
- Frontend was calling `/api/v1/auth/2fa/login` which returned 404 Not Found

**Root Cause:**
- Individual routers had `/api/v1/` in their prefix (e.g., `prefix="/api/v1/auth/2fa"`)
- These routers were included via `crud_router` which also had `prefix="/api/v1"`
- FastAPI concatenated both prefixes, resulting in double `/api/v1/`

**Files Modified:**
- `surfsense_backend/app/routes/two_fa_routes.py`
  - Changed: `prefix="/api/v1/auth/2fa"` → `prefix="/auth/2fa"`
- `surfsense_backend/app/routes/rate_limit_routes.py`
  - Changed: `prefix="/api/v1/rate-limiting"` → `prefix="/rate-limiting"`
- `surfsense_backend/app/routes/site_configuration_routes.py`
  - Changed: `prefix="/api/v1/site-config"` → `prefix="/site-config"`
- `surfsense_backend/app/routes/social_media_links_routes.py`
  - Changed: `prefix="/api/v1/social-media-links"` → `prefix="/social-media-links"`

**Pattern:** When a router is included via `crud_router` with `prefix="/api/v1"`, child router prefixes should NOT include `/api/v1/`.

---

### 2. **Function Parameter Order Syntax Error** ✅
**Problem:**
- Python syntax error: "parameter without a default follows parameter with a default"
- Located in `two_fa_routes.py` line 432

**File Modified:**
- `surfsense_backend/app/routes/two_fa_routes.py:430-434`

**Before:**
```python
async def login_with_2fa(
    form_data: OAuth2PasswordRequestForm = Depends(),
    http_request: Request,
    session: AsyncSession = Depends(get_async_session),
):
```

**After:**
```python
async def login_with_2fa(
    http_request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    session: AsyncSession = Depends(get_async_session),
):
```

---

### 3. **Bcrypt Library Compatibility Issue** ✅
**Problem:**
- `bcrypt 5.0.0` incompatible with `passlib 1.7.4`
- Error: `AttributeError: module 'bcrypt' has no attribute '__about__'`
- Caused password hashing/verification to fail with internal server errors

**Solution:**
- Pinned `bcrypt==4.0.1` in `pyproject.toml`
- Manually downgraded bcrypt on VPS: `pip install bcrypt==4.0.1`

**File Modified:**
- `surfsense_backend/pyproject.toml` - Added `"bcrypt==4.0.1"` to dependencies

---

## VPS-Specific Changes

### Manual Changes on VPS
These changes were applied directly on the production server and are NOT tracked in code:

1. **Bcrypt Downgrade:**
   ```bash
   cd /opt/SurfSense/surfsense_backend
   source venv/bin/activate
   pip install bcrypt==4.0.1
   systemctl restart surfsense
   ```
   - **Note:** Now handled automatically via `pyproject.toml` for future deployments

2. **Password Resets:**
   - Created test user with superuser privileges
   - Reset password for production admin account
   - **Note:** Password hashes stored in database, not in code
   - **Security:** Use strong, unique passwords and rotate them regularly

### Future Automation Recommendations
To improve traceability and reduce human error, consider automating manual server processes:

**Configuration Management:**
- Use Ansible, Salt, or Chef to automate server configuration
- Document all server changes as Infrastructure as Code (IaC)
- Version control all deployment scripts and configurations

**Deployment Automation:**
- Create deployment scripts that handle dependency updates automatically
- Implement CI/CD pipelines for automated testing and deployment
- Use container orchestration (Docker Compose/Kubernetes) for consistent environments

**Database Management:**
- Automate user creation and password resets via admin scripts or API endpoints
- Implement secure credential rotation policies
- Use environment variables or secret management tools (HashiCorp Vault, AWS Secrets Manager)

**Benefits:**
- ✅ Consistent deployments across environments
- ✅ Complete audit trail of all changes
- ✅ Reduced risk of configuration drift
- ✅ Faster rollback capabilities
- ✅ Improved team collaboration and documentation

---

## Git Commits

All code changes committed to `nightly` branch:

1. **`946db0c`** - Fix API route prefixes for 2FA and rate limiting
2. **`afd1807`** - Fix parameter order in login_with_2fa function
3. **`d3fd4cc`** - Fix double API prefix issue for all routes
4. **`296e25b`** - Pin bcrypt to 4.0.1 for passlib compatibility

---

## Verification Steps

### Backend Health Check ✅
```bash
# On VPS:
systemctl status surfsense
# Status: active (running)

curl http://127.0.0.1:8000/api/v1/site-config/public
# Returns: 200 OK with site configuration
```

### Login Endpoint Test ✅
```bash
curl -X POST http://127.0.0.1:8000/api/v1/auth/2fa/login \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  -d 'username=YOUR_EMAIL&password=YOUR_PASSWORD&grant_type=password'

# Response:
{
  "access_token": "eyJhbGci...",
  "token_type": "bearer",
  "requires_2fa": false,
  "temporary_token": null
}
```

### Frontend Test ✅
- URL: https://ai.kapteinis.lv/login
- Use your test account credentials to verify login functionality
- Result: Login successful, redirects to dashboard

---

## Architecture Notes

### FastAPI Router Prefix Pattern
```python
# Main app (app.py)
app.include_router(crud_router, prefix="/api/v1", tags=["crud"])

# Child routers (__init__.py)
router = APIRouter()
router.include_router(two_fa_router)  # Has prefix="/auth/2fa"
router.include_router(rate_limit_router)  # Has prefix="/rate-limiting"

# Result:
# /api/v1 + /auth/2fa + /login = /api/v1/auth/2fa/login ✅
```

### Incorrect Pattern (causes double prefix):
```python
# ❌ DON'T DO THIS
router = APIRouter(prefix="/api/v1/auth/2fa")  # Already includes /api/v1/
# Result: /api/v1/api/v1/auth/2fa/login (broken)
```

---

## Deployment Checklist

When deploying to VPS in the future:

- [ ] Pull latest code: `git pull origin nightly`
- [ ] Install dependencies: `pip install -e .` (includes bcrypt==4.0.1)
- [ ] Run migrations: `alembic upgrade head`
- [ ] Restart backend: `systemctl restart surfsense`
- [ ] Restart frontend: `systemctl restart surfsense-frontend`
- [ ] Restart workers: `systemctl restart surfsense-celery surfsense-celery-beat`
- [ ] Check logs: `journalctl -u surfsense -n 50`
- [ ] Test login: Visit https://ai.kapteinis.lv/login

---

## Related Features

### Two-Factor Authentication (2FA)
- Routes: `/api/v1/auth/2fa/*`
- Frontend: User dropdown → Security (2FA)
- Features: TOTP setup, backup codes, QR generation

### Rate Limiting
- Routes: `/api/v1/rate-limiting/*`
- Frontend: User dropdown → Rate Limiting
- Features: IP blocking, auto-unlock, statistics

### Site Configuration
- Routes: `/api/v1/site-config/*`
- Frontend: User dropdown → Site Settings (admin only)
- Features: Branding, registration toggle, contact info

---

## Known Issues

None currently. System is fully operational.

---

## Contact

For deployment issues, check:
- Backend logs: `journalctl -u surfsense -f`
- Frontend logs: `journalctl -u surfsense-frontend -f`
- Service status: `systemctl status surfsense surfsense-frontend`

---

**Deployment Date:** November 20, 2025
**Deployed By:** Claude Code
**Branch:** nightly
**Status:** ✅ Production Ready
