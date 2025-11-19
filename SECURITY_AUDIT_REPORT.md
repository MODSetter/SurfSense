# SurfSense Backend Security Audit Report
**Audit Date:** November 19, 2025
**Branch:** origin/nightly
**Scope:** Authentication, Authorization, Input Validation, Sensitive Data Handling, Session Security, File Upload Security

---

## CRITICAL SECURITY ISSUES

### 1. Token Exposure in Console Logs (CRITICAL)
**Location:** `/home/user/SurfSense/surfsense_backend/app/users.py` (lines 39, 44, 49)
**Severity:** CRITICAL
**Issue:** Reset and verification tokens are being printed to console, exposing sensitive authentication tokens.

**Vulnerable Code:**
```python
# Line 44
print(f"User {user.id} has forgot their password. Reset token: {token}")

# Line 49  
print(f"Verification requested for user {user.id}. Verification token: {token}")
```

**Risk:** 
- Tokens visible in server logs, application logs, and monitoring systems
- Attackers with log access can impersonate users
- Tokens may be exposed in container logs and log aggregation services

**Recommendation:** Remove print statements and use proper logging with redacted tokens:
```python
logger.info(f"User {user.id} has initiated password reset")
logger.info(f"Verification requested for user {user.id}")
```

---

### 2. API Keys Exposed in Response (CRITICAL)
**Location:** `/home/user/SurfSense/surfsense_backend/app/schemas/llm_config.py` (lines 22, 51, 63)
**Severity:** CRITICAL
**Issue:** LLMConfigRead schema includes api_key field, which returns API keys to clients.

**Vulnerable Code:**
```python
class LLMConfigRead(LLMConfigBase, IDModel, TimestampModel):
    id: int
    created_at: datetime | None
    search_space_id: int | None
    # api_key is inherited from LLMConfigBase - EXPOSED!
```

**Endpoints Affected:**
- `GET /api/v1/llm-configs` - Returns list of configs with API keys
- `GET /api/v1/llm-configs/{llm_config_id}` - Returns specific config with API key
- `PUT /api/v1/llm-configs/{llm_config_id}` - Returns updated config with API key

**Risk:**
- API keys exposed to frontend and network sniffing
- Allows attackers to use stolen API keys for unauthorized API calls
- Breaches third-party service credentials (OpenAI, Anthropic, etc.)

**Recommendation:** Create separate response schema without api_key:
```python
class LLMConfigRead(IDModel, TimestampModel):
    id: int
    name: str
    provider: str
    model_name: str
    # api_key should NOT be here
```

---

### 3. Connector Credentials Exposed in Response (CRITICAL)
**Location:** `/home/user/SurfSense/surfsense_backend/app/schemas/search_source_connector.py` (line 18, 63)
**Severity:** CRITICAL
**Issue:** SearchSourceConnectorRead includes full config dict with API keys and credentials.

**Vulnerable Code:**
```python
class SearchSourceConnectorRead(SearchSourceConnectorBase, IDModel, TimestampModel):
    # config field inherited from SearchSourceConnectorBase - contains secrets!
    config: dict[str, Any]  # EXPOSED!
    search_space_id: int
```

**Endpoints Affected:**
- `GET /api/v1/search-source-connectors` - Lists all connectors with configs
- `GET /api/v1/search-source-connectors/{connector_id}` - Returns specific connector config
- `POST /api/v1/search-source-connectors` - Returns created connector with config

**Config Examples (Containing Secrets):**
- GitHub: `{"github_pat": "ghp_xxxx"}`
- Slack: `{"slack_bot_token": "xoxb-xxxx"}`
- Jira: `{"api_token": "atatt-xxxxx"}`
- Airtable: `{"access_token": "pat-xxxxx"}`

**Risk:**
- All connector API keys/tokens exposed to frontend
- Credentials visible in network traffic
- Allows lateral movement if credentials are for internal services

**Recommendation:** Create sanitized response schema without sensitive config fields.

---

### 4. JWT Token Passed in URL Query Parameter (CRITICAL)
**Location:** `/home/user/SurfSense/surfsense_backend/app/users.py` (line 84)
**Severity:** CRITICAL
**Issue:** Access token exposed in redirect URL as query parameter.

**Vulnerable Code:**
```python
class CustomBearerTransport(BearerTransport):
    async def get_login_response(self, token: str) -> Response:
        bearer_response = BearerResponse(access_token=token, token_type="bearer")
        redirect_url = f"{config.NEXT_FRONTEND_URL}/auth/callback?token={bearer_response.access_token}"
        # Token exposed in URL!
```

**Risk:**
- Tokens logged in browser history
- Visible in HTTP proxy logs
- Exposed in referrer headers to external sites
- Stored in server access logs
- Visible in CDN/WAF logs

**Recommendation:** Use secure methods to pass tokens:
1. Use POST with response body instead of GET with query parameter
2. Store in secure, httpOnly cookies (if using browser storage)
3. Use fragment identifier (#) instead of query string (not sent to server)

---

## HIGH SEVERITY ISSUES

### 5. Overly Permissive CORS Configuration
**Location:** `/home/user/SurfSense/surfsense_backend/app/app.py` (lines 51-57)
**Severity:** HIGH
**Issue:** CORS middleware allows all HTTP methods and headers.

**Vulnerable Code:**
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],  # PROBLEM: Allows all methods
    allow_headers=["*"],  # PROBLEM: Allows all headers
)
```

**Risk:**
- Allows DELETE, PATCH, and other methods from any origin
- Allows custom headers, potentially bypassing security controls
- Combined with allow_credentials=True, enables CSRF attacks

**Recommendation:**
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT"],
    allow_headers=["Content-Type", "Authorization"],
)
```

---

### 6. Untrusted Proxy Headers
**Location:** `/home/user/SurfSense/surfsense_backend/app/app.py` (line 48)
**Severity:** HIGH
**Issue:** ProxyHeadersMiddleware trusting all proxy hosts.

**Vulnerable Code:**
```python
app.add_middleware(ProxyHeadersMiddleware, trusted_hosts="*")
```

**Risk:**
- Any attacker can spoof X-Forwarded-For headers
- Can bypass IP-based access controls
- Allows auth bypass if trusting X-Forwarded-Proto

**Recommendation:**
```python
app.add_middleware(ProxyHeadersMiddleware, trusted_hosts=["127.0.0.1", "10.0.0.0/8"])
```

---

### 7. Excessive JWT Token Lifetime
**Location:** `/home/user/SurfSense/surfsense_backend/app/users.py` (line 57)
**Severity:** HIGH
**Issue:** JWT tokens valid for 24 hours without refresh mechanism.

**Vulnerable Code:**
```python
def get_jwt_strategy() -> JWTStrategy[models.UP, models.ID]:
    return JWTStrategy(secret=SECRET, lifetime_seconds=3600 * 24)
    # 86,400 seconds = 24 hours TOO LONG!
```

**Risk:**
- Stolen tokens valid for full 24 hours
- No token revocation mechanism observed
- Extended window for compromised tokens
- No refresh token rotation

**Recommendation:**
```python
# Short-lived access tokens (15-30 minutes)
lifetime_seconds=3600  # 1 hour max, prefer 15-30 mins
# Implement refresh token rotation every 7 days
```

---

### 8. In-Memory 2FA Token Storage Without Persistence
**Location:** `/home/user/SurfSense/surfsense_backend/app/routes/two_fa_routes.py` (lines 27-29)
**Severity:** HIGH
**Issue:** Temporary tokens for 2FA stored in-memory dictionary without persistence or Redis backend.

**Vulnerable Code:**
```python
# In-memory store for temporary tokens (use Redis in production)
_temp_tokens: dict[str, dict] = {}

def store_temporary_token(token: str, user_id: str, expires_in_minutes: int = 5):
    expires_at = datetime.now(UTC) + timedelta(minutes=expires_in_minutes)
    _temp_tokens[token] = {
        "user_id": user_id,
        "expires_at": expires_at,
    }
```

**Risk:**
- Tokens lost on application restart
- Not thread-safe for distributed deployments
- No backup of active 2FA sessions
- Scalability issues with multiple workers
- Comment says "use Redis in production" but not implemented

**Recommendation:** Implement Redis-backed token storage with TTL.

---

### 9. No File Upload Type Validation
**Location:** `/home/user/SurfSense/surfsense_backend/app/routes/documents_routes.py` (lines 96-142)
**Severity:** HIGH
**Issue:** File uploads accept any file extension without validation.

**Vulnerable Code:**
```python
@router.post("/documents/fileupload")
async def create_documents_file_upload(files: list[UploadFile], ...):
    for file in files:
        file_ext = os.path.splitext(file.filename)[1]
        unique_filename = f"{uuid.uuid4()}{file_ext}"
        # NO VALIDATION of file_ext or content type!
```

**Risk:**
- Upload executable files (.exe, .sh, .py)
- Upload malware or malicious scripts
- DoS attacks with resource-intensive files
- Arbitrary content served to users
- No size limit enforcement

**Recommendation:**
```python
ALLOWED_EXTENSIONS = {'.pdf', '.txt', '.docx', '.csv'}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB

# Validate extension
if not any(file.filename.lower().endswith(ext) for ext in ALLOWED_EXTENSIONS):
    raise HTTPException(status_code=400, detail="File type not allowed")

# Validate content type
if file.content_type not in ['application/pdf', 'text/plain', ...]:
    raise HTTPException(status_code=400, detail="Invalid content type")

# Validate size
content = await file.read()
if len(content) > MAX_FILE_SIZE:
    raise HTTPException(status_code=413, detail="File too large")
```

---

### 10. No Rate Limiting on Authentication Endpoints
**Location:** All auth routes (not found in codebase)
**Severity:** HIGH
**Issue:** No rate limiting on login, 2FA verification, or registration endpoints.

**Risk:**
- Brute force attacks on login endpoint
- Brute force on 2FA codes (6-digit TOTP: only 1 million possibilities)
- Credential stuffing attacks
- Account enumeration attacks

**Recommendation:** Implement rate limiting:
```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

@router.post("/auth/jwt/login")
@limiter.limit("5/minute")  # 5 attempts per minute per IP
async def login(...):
    pass

@router.post("/auth/2fa/verify")
@limiter.limit("10/minute")
async def verify_2fa_login(...):
    pass
```

---

## MEDIUM SEVERITY ISSUES

### 11. Unsafe Dynamic Attribute Setting
**Location:** `/home/user/SurfSense/surfsense_backend/app/routes/llm_config_routes.py` (lines 293-294)
**Severity:** MEDIUM
**Issue:** Using setattr() with user-controlled keys could allow setting arbitrary fields.

**Vulnerable Code:**
```python
update_data = llm_config_update.model_dump(exclude_unset=True)
for key, value in update_data.items():
    setattr(db_llm_config, key, value)
```

**Risk:**
- Could potentially bypass security checks (low risk due to Pydantic validation)
- Sets any attribute from update payload
- Could set internal fields if schema expanded carelessly

**Recommendation:** Explicitly list allowed fields:
```python
allowed_fields = {'name', 'provider', 'model_name', 'api_base', 'language'}
for key, value in update_data.items():
    if key in allowed_fields:
        setattr(db_llm_config, key, value)
```

---

### 12. Inconsistent Backup Code Removal Logic
**Location:** `/home/user/SurfSense/surfsense_backend/app/routes/two_fa_routes.py` (lines 213, 418)
**Severity:** MEDIUM
**Issue:** Inconsistent backup code removal between disable_2fa and verify_2fa_login endpoints.

**Inconsistent Code:**
```python
# In disable_2fa (line 213):
user.backup_codes[used_index] = None  # Sets to None

# In verify_2fa_login (line 418):
valid_backup_codes.pop(used_index)    # Removes from list
user.backup_codes = valid_backup_codes
```

**Risk:**
- Potential to re-use backup codes if logic is not applied uniformly
- Database inconsistency (None values vs. removed items)
- Confusing behavior for users

**Recommendation:** Use consistent removal logic throughout:
```python
# Option 1: Always remove entirely
if is_valid and used_index is not None:
    user.backup_codes.pop(used_index)

# Option 2: Always set to None  
if is_valid and used_index is not None:
    user.backup_codes[used_index] = None
    # Clean up None values when reading
```

---

### 13. Information Disclosure in Error Messages
**Location:** Multiple routes
**Severity:** MEDIUM
**Issue:** Generic error messages sometimes contain implementation details.

**Example:**
```python
raise HTTPException(
    status_code=500, detail=f"Failed to process documents: {e!s}"
)
```

**Risk:**
- Stack traces expose internal structure
- Exception details leak implementation information
- Attackers learn about technology stack

**Recommendation:** Use generic messages in production:
```python
logger.exception("Document processing failed")  # Log full details
raise HTTPException(
    status_code=500, detail="An error occurred while processing documents"
)
```

---

### 14. Logging Sensitive Information
**Location:** Various routes
**Severity:** MEDIUM
**Issue:** Email addresses logged alongside authentication events (privacy concern).

**Example:**
```python
logger.info(f"User {user.email} logged in successfully")
logger.info(f"User {user.email} completed 2FA login")
```

**Risk:**
- Email addresses exposed in logs
- Log files accessible to unauthorized personnel
- GDPR/privacy compliance issues
- User enumeration via logs

**Recommendation:**
```python
logger.info(f"User {user.id} logged in successfully")  # Use ID instead
```

---

## LOW SEVERITY ISSUES

### 15. Print Statements Should Use Logging
**Location:** `/home/user/SurfSense/surfsense_backend/app/routes/documents_routes.py` (line 39)
**Severity:** LOW
**Issue:** Print statement instead of logging framework.

**Vulnerable Code:**
```python
except RuntimeError as e:
    print("Error setting event loop policy", e)
```

**Recommendation:** Use logging:
```python
except RuntimeError as e:
    logger.warning("Error setting event loop policy: %s", e)
```

---

## SECURITY CONFIGURATION RECOMMENDATIONS

### 1. Implement HTTPS Only
Ensure all traffic is encrypted. Add security headers:
```python
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["example.com", "www.example.com"]
)
```

### 2. Add Security Headers
```python
app.add_middleware(
    CustomHeaderMiddleware,
    headers={
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "X-XSS-Protection": "1; mode=block",
        "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
        "Content-Security-Policy": "default-src 'self'"
    }
)
```

### 3. Implement Request Validation
- Validate all input size limits
- Implement request size limits
- Validate JSON schema strictly

### 4. Add Audit Logging
- Log all authentication events
- Log all sensitive operations
- Keep immutable audit trails
- Implement log rotation

### 5. Secret Management
- Use environment variables for all secrets
- Implement secret rotation mechanism
- Never log secrets
- Use .env.local (not in git)

---

## SUMMARY OF FINDINGS

| Severity | Count |
|----------|-------|
| CRITICAL | 4     |
| HIGH     | 6     |
| MEDIUM   | 4     |
| LOW      | 1     |
| **Total** | **15** |

---

## IMMEDIATE ACTIONS REQUIRED

**Priority 1 (Implement ASAP):**
1. Remove token logging (Issue #1)
2. Remove API keys from response schemas (Issues #2, #3)
3. Remove JWT token from URL query parameter (Issue #4)
4. Fix CORS configuration (Issue #5)
5. Implement rate limiting (Issue #10)

**Priority 2 (Within 1 week):**
6. Reduce JWT lifetime to 1 hour max (Issue #7)
7. Implement Redis for 2FA tokens (Issue #8)
8. Add file upload validation (Issue #9)
9. Fix proxy header trust (Issue #6)

**Priority 3 (Before production):**
10. Add security headers
11. Implement audit logging
12. Add HTTPS/TLS enforcement
13. Implement error handling
14. Add monitoring and alerting

---

## CONCLUSION

The SurfSense backend has several critical security vulnerabilities that need immediate attention, particularly around sensitive data exposure (API keys, credentials, tokens). The authentication and authorization mechanisms are generally sound but need hardening through rate limiting and shorter token lifetimes. Recommend addressing all CRITICAL and HIGH severity issues before deploying to production.

