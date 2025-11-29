# SurfSense Security Audit - November 2025

This document consolidates the comprehensive security audit findings for SurfSense, including detailed code examples and remediation strategies.

---

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



---

# Appendix: Code Examples and Implementation Details

# SurfSense Security Audit - Code Examples & Line References

## CRITICAL ISSUE #1: Token Exposure in Console Logs

**File:** `/home/user/SurfSense/surfsense_backend/app/users.py`

```python
Line 38-49: UserManager class
class UserManager(UUIDIDMixin, BaseUserManager[User, uuid.UUID]):
    reset_password_token_secret = SECRET
    verification_token_secret = SECRET

    async def on_after_register(self, user: User, request: Request | None = None):
        print(f"User {user.id} has registered.")  # LINE 39 - PROBLEM

    async def on_after_forgot_password(
        self, user: User, token: str, request: Request | None = None
    ):
        print(f"User {user.id} has forgot their password. Reset token: {token}")  # LINE 44 - TOKEN LEAKED!

    async def on_after_request_verify(
        self, user: User, token: str, request: Request | None = None
    ):
        print(f"Verification requested for user {user.id}. Verification token: {token}")  # LINE 49 - TOKEN LEAKED!
```

**Why it's critical:** 
- Tokens are printed to stdout/stderr
- Visible in Docker container logs
- Stored in application logs
- Accessible via log aggregation systems
- Attackers can use tokens to bypass authentication

**Fix:**
```python
import logging
logger = logging.getLogger(__name__)

async def on_after_forgot_password(self, user: User, token: str, request: Request | None = None):
    logger.info(f"Password reset requested for user {user.id}")  # NO TOKEN!

async def on_after_request_verify(self, user: User, token: str, request: Request | None = None):
    logger.info(f"Email verification requested for user {user.id}")  # NO TOKEN!
```

---

## CRITICAL ISSUE #2: API Keys Exposed in Response

**File:** `/home/user/SurfSense/surfsense_backend/app/schemas/llm_config.py`

```python
Line 11-31: LLMConfigBase includes api_key
class LLMConfigBase(BaseModel):
    name: str
    provider: LiteLLMProvider
    custom_provider: str | None = None
    model_name: str
    api_key: str = Field(..., description="API key for the provider")  # LINE 22 - PROBLEM!
    api_base: str | None = None
    litellm_params: dict[str, Any] | None = None
    language: str | None = None

Line 63-72: LLMConfigRead inherits api_key
class LLMConfigRead(LLMConfigBase, IDModel, TimestampModel):
    id: int
    created_at: datetime | None
    search_space_id: int | None
    # INHERITS api_key FROM LLMConfigBase - EXPOSED IN RESPONSES!
```

**Affected Endpoints:**
- `GET /api/v1/llm-configs` - Returns list with all API keys
- `GET /api/v1/llm-configs/{id}` - Returns single config with API key
- `PUT /api/v1/llm-configs/{id}` - Returns updated config with API key

**Example Response:**
```json
{
  "id": 1,
  "name": "OpenAI GPT-4",
  "provider": "OPENAI",
  "model_name": "gpt-4",
  "api_key": "[REDACTED-API-KEY]",  // CRITICAL LEAK!
  "api_base": null,
  "language": "English",
  "created_at": "2025-11-19T00:00:00Z"
}
```

**Fix:**
```python
class LLMConfigRead(IDModel, TimestampModel):
    id: int
    name: str
    provider: LiteLLMProvider
    custom_provider: str | None = None
    model_name: str
    # DO NOT INCLUDE: api_key
    api_base: str | None = None
    language: str | None = None
    # ... other fields EXCEPT api_key
```

---

## CRITICAL ISSUE #3: Connector Credentials Exposed

**File:** `/home/user/SurfSense/surfsense_backend/app/schemas/search_source_connector.py`

```python
Line 13-45: SearchSourceConnectorBase includes config
class SearchSourceConnectorBase(BaseModel):
    name: str
    connector_type: SearchSourceConnectorType
    is_indexable: bool
    last_indexed_at: datetime | None = None
    config: dict[str, Any]  # LINE 18 - PROBLEM! Contains all secrets!
    periodic_indexing_enabled: bool = False
    indexing_frequency_minutes: int | None = None
    next_scheduled_at: datetime | None = None

Line 63-67: SearchSourceConnectorRead inherits config
class SearchSourceConnectorRead(SearchSourceConnectorBase, IDModel, TimestampModel):
    search_space_id: int
    user_id: uuid.UUID
    # INHERITS config FIELD - ALL CREDENTIALS EXPOSED!
```

**Affected Endpoints:**
- `POST /api/v1/search-source-connectors` - Returns config with secrets
- `GET /api/v1/search-source-connectors` - Lists all connectors with configs
- `GET /api/v1/search-source-connectors/{id}` - Returns connector with config
- `PUT /api/v1/search-source-connectors/{id}` - Returns updated connector with config

**Example Response (GitHub):**
```json
{
  "id": 1,
  "name": "My GitHub Repos",
  "connector_type": "GITHUB_CONNECTOR",
  "is_indexable": true,
  "config": {
    "github_pat": "ghp_1234567890abcdefghijklmnopqrstuv"  // PAT LEAKED!
  },
  "search_space_id": 5,
  "user_id": "uuid-1234"
}
```

**Example Response (Slack):**
```json
{
  "id": 2,
  "name": "Slack Workspace",
  "connector_type": "SLACK_CONNECTOR",
  "config": {
    "slack_bot_token": "[REDACTED-BOT-TOKEN]",  // TOKEN LEAKED!
    "slack_user_token": "[REDACTED-USER-TOKEN]"  // USER TOKEN LEAKED!
  }
}
```

**Fix:**
```python
class SearchSourceConnectorRead(IDModel, TimestampModel):
    id: int
    name: str
    connector_type: SearchSourceConnectorType
    is_indexable: bool
    last_indexed_at: datetime | None = None
    # DO NOT INCLUDE: config
    periodic_indexing_enabled: bool = False
    indexing_frequency_minutes: int | None = None
    next_scheduled_at: datetime | None = None
    search_space_id: int
    user_id: uuid.UUID
```

---

## CRITICAL ISSUE #4: JWT Token in URL

**File:** `/home/user/SurfSense/surfsense_backend/app/users.py`

```python
Line 81-88: CustomBearerTransport
class CustomBearerTransport(BearerTransport):
    async def get_login_response(self, token: str) -> Response:
        bearer_response = BearerResponse(access_token=token, token_type="bearer")
        redirect_url = f"{config.NEXT_FRONTEND_URL}/auth/callback?token={bearer_response.access_token}"
        # LINE 84 - TOKEN IN QUERY PARAMETER! PROBLEM!
        if config.AUTH_TYPE == "GOOGLE":
            return RedirectResponse(redirect_url, status_code=302)
        else:
            return JSONResponse(bearer_response.model_dump())
```

**How this is exploited:**
1. Browser history: Token stored in browser's address bar history
2. Proxy logs: Any HTTP proxy logs the full URL with token
3. Referrer headers: Frontend redirects expose token to external sites
4. Server logs: Access logs contain full request URL with token
5. WAF/CDN logs: Third-party services log the request

**Example leaked URL:**
```
https://app.example.com/auth/callback?token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

**Fix:**
Option 1 - Use response body (safer):
```python
@router.post("/auth/jwt/login")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    # Verify credentials
    token = await jwt_strategy.write_token(user)
    return {
        "access_token": token,
        "token_type": "bearer"
    }
```

Option 2 - Use fragment identifier (not sent to server):
```python
redirect_url = f"{config.NEXT_FRONTEND_URL}/auth/callback#token={token}"
return RedirectResponse(redirect_url, status_code=302)
# Fragment is NOT sent to server/proxy/CDN!
```

---

## HIGH ISSUE #5: CORS Misconfiguration

**File:** `/home/user/SurfSense/surfsense_backend/app/app.py`

```python
Line 50-57: CORSMiddleware configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],  # LINE 55 - PROBLEM! ALL METHODS!
    allow_headers=["*"],  # LINE 56 - PROBLEM! ALL HEADERS!
)
```

**Why this is a problem:**
- `allow_methods=["*"]` allows DELETE, PATCH, OPTIONS, TRACE, etc.
- `allow_headers=["*"]` allows arbitrary headers
- Combined with `allow_credentials=True`, enables CSRF
- Frontend from any allowed origin can make any request

**Fix:**
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT"],  # Specific methods only
    allow_headers=["Content-Type", "Authorization"],  # Specific headers only
)
```

---

## HIGH ISSUE #6: Untrusted Proxy Headers

**File:** `/home/user/SurfSense/surfsense_backend/app/app.py`

```python
Line 46-48: ProxyHeadersMiddleware
app.add_middleware(ProxyHeadersMiddleware, trusted_hosts="*")
```

**Why this is dangerous:**
- `trusted_hosts="*"` means trust ANY proxy
- Attackers can spoof X-Forwarded-For headers
- Can bypass IP-based access controls
- Can spoof X-Forwarded-Proto to trick HTTPS detection

**Attack example:**
```
GET /auth/jwt/login HTTP/1.1
X-Forwarded-For: 127.0.0.1  # Spoof localhost IP to bypass rate limiting
```

**Fix:**
```python
app.add_middleware(
    ProxyHeadersMiddleware, 
    trusted_hosts=["127.0.0.1", "10.0.0.0/8", "172.16.0.0/12"]  # Specific IPs only
)
```

---

## HIGH ISSUE #7: Long JWT Lifetime

**File:** `/home/user/SurfSense/surfsense_backend/app/users.py`

```python
Line 56-57: JWT Strategy
def get_jwt_strategy() -> JWTStrategy[models.UP, models.ID]:
    return JWTStrategy(secret=SECRET, lifetime_seconds=3600 * 24)
    # 86,400 seconds = 24 HOURS - TOO LONG!
```

**Risk:**
- Stolen token valid for full 24 hours
- No token revocation possible
- Extended attack window
- No refresh token mechanism

**Calculation:**
```
lifetime_seconds = 3600 * 24
= 3600 * 24
= 86,400 seconds
= 1,440 minutes
= 24 hours ❌ TOO LONG!
```

**Best practices:**
```python
# Access token: 15-30 minutes
lifetime_seconds = 15 * 60  # 15 minutes - GOOD
lifetime_seconds = 30 * 60  # 30 minutes - ACCEPTABLE
lifetime_seconds = 3600     # 1 hour - MAXIMUM

# Refresh token: 7-30 days (separate mechanism)
```

---

## HIGH ISSUE #8: In-Memory 2FA Token Storage

**File:** `/home/user/SurfSense/surfsense_backend/app/routes/two_fa_routes.py`

```python
Line 27-29: Global in-memory store
_temp_tokens: dict[str, dict] = {}

Line 268-280: Store function
def store_temporary_token(token: str, user_id: str, expires_in_minutes: int = 5):
    expires_at = datetime.now(UTC) + timedelta(minutes=expires_in_minutes)
    _temp_tokens[token] = {
        "user_id": user_id,
        "expires_at": expires_at,
    }
    # Clean up expired tokens
    current_time = datetime.now(UTC)
    expired = [k for k, v in _temp_tokens.items() if v["expires_at"] < current_time]
    for k in expired:
        del _temp_tokens[k]
```

**Problems:**
1. Lost on app restart
2. Not shared between workers
3. Not thread-safe for concurrent requests
4. Comment says "use Redis in production" but not implemented

**Current flow:**
```
1. User logs in
2. temp_token = "uuid:secret" stored in _temp_tokens dict
3. User receives temp_token, enters 2FA code
4. Server verifies temp_token from dict
5. App restarts → ALL temp_tokens LOST!
6. User stuck in 2FA limbo
```

**Fix:**
```python
import redis
from datetime import timedelta

redis_client = redis.Redis(host='localhost', port=6379, db=1)

def store_temporary_token(token: str, user_id: str, expires_in_minutes: int = 5):
    redis_client.setex(
        f"2fa_token:{token}",
        timedelta(minutes=expires_in_minutes),
        user_id
    )

def get_user_id_from_token(token: str) -> str | None:
    user_id = redis_client.get(f"2fa_token:{token}")
    return user_id.decode() if user_id else None

def invalidate_temporary_token(token: str):
    redis_client.delete(f"2fa_token:{token}")
```

---

## HIGH ISSUE #9: No File Upload Validation

**File:** `/home/user/SurfSense/surfsense_backend/app/routes/documents_routes.py`

```python
Line 96-142: File upload endpoint
@router.post("/documents/fileupload")
async def create_documents_file_upload(
    files: list[UploadFile],
    search_space_id: int = Form(...),
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    try:
        await check_ownership(session, SearchSpace, search_space_id, user)
        if not files:
            raise HTTPException(status_code=400, detail="No files provided")
        
        for file in files:
            try:
                uploads_dir = Path(os.getenv("UPLOADS_DIR", "./uploads"))
                uploads_dir.mkdir(parents=True, exist_ok=True)
                
                file_ext = os.path.splitext(file.filename)[1]  # LINE 116 - NO VALIDATION!
                unique_filename = f"{uuid.uuid4()}{file_ext}"  # LINE 117 - ANY EXTENSION!
                temp_path = str(uploads_dir / unique_filename)
                
                content = await file.read()
                with open(temp_path, "wb") as f:
                    f.write(content)  # LINE 123 - NO SIZE CHECK!
```

**Vulnerabilities:**
1. No file extension validation
2. No content-type validation
3. No file size limit
4. No magic byte validation
5. Can upload executables

**Examples of attacks:**
```
1. Upload PHP shell: shell.php → xyz.php (PHP code executed)
2. Upload Python: script.py → xyz.py (Executed by backend)
3. Upload executable: virus.exe → xyz.exe
4. Upload large file: 10GB file → DoS
5. Upload malware → Infect production server
```

**Fix:**
```python
from mimetypes import guess_type
import mimetypes

ALLOWED_EXTENSIONS = {'.pdf', '.txt', '.docx', '.xlsx', '.csv', '.doc'}
ALLOWED_MIMETYPES = {
    'application/pdf',
    'text/plain',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'application/vnd.ms-excel'
}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB

for file in files:
    # 1. Validate extension
    file_ext = os.path.splitext(file.filename)[1].lower()
    if file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400, 
            detail=f"File extension {file_ext} not allowed"
        )
    
    # 2. Validate content-type
    if file.content_type not in ALLOWED_MIMETYPES:
        raise HTTPException(
            status_code=400, 
            detail="Invalid content type"
        )
    
    # 3. Validate size
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413, 
            detail=f"File exceeds {MAX_FILE_SIZE/1024/1024}MB limit"
        )
    
    # 4. Validate magic bytes (file signature)
    if file_ext == '.pdf':
        if not content.startswith(b'%PDF'):
            raise HTTPException(status_code=400, detail="Invalid PDF file")
```

---

## HIGH ISSUE #10: No Rate Limiting

**Problem:** All authentication endpoints have NO rate limiting

**Vulnerable Endpoints:**
- `POST /auth/register` - No limit on account creation
- `POST /auth/jwt/login` - No limit on login attempts
- `POST /auth/forgot-password` - No limit on reset requests
- `POST /auth/2fa/verify` - No limit on 2FA code guessing

**Attack scenarios:**
1. Brute force login: Try 1000s of passwords per second
2. Brute force 2FA: Try all 1,000,000 possible 6-digit codes
3. Account enumeration: Check which emails exist
4. DoS: Flood endpoint with requests

**Fix:**
```python
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

# In your routes file
@router.post("/jwt/login")
@limiter.limit("5/minute")  # 5 attempts per minute per IP
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    # Login logic
    pass

@router.post("/auth/2fa/verify")
@limiter.limit("10/minute")  # 10 verification attempts per minute
async def verify_2fa_login(request: TwoFALoginRequest):
    # 2FA logic
    pass

@router.post("/auth/register")
@limiter.limit("5/hour")  # 5 registrations per hour per IP
async def register(user_data: UserCreate):
    # Register logic
    pass
```

---

## SUMMARY TABLE

| Issue | Severity | File | Line | Type |
|-------|----------|------|------|------|
| Token logging | CRITICAL | users.py | 39, 44, 49 | Information Disclosure |
| API key exposure | CRITICAL | llm_config.py | 22, 51, 63 | Information Disclosure |
| Config exposure | CRITICAL | search_source_connector.py | 18, 63 | Information Disclosure |
| Token in URL | CRITICAL | users.py | 84 | Information Disclosure |
| CORS misconfiguration | HIGH | app.py | 55-56 | CORS Issue |
| Proxy headers | HIGH | app.py | 48 | Header Spoofing |
| JWT lifetime | HIGH | users.py | 57 | Long Expiry |
| 2FA token storage | HIGH | two_fa_routes.py | 27-29 | Persistence Issue |
| File validation | HIGH | documents_routes.py | 116-123 | Input Validation |
| Rate limiting | HIGH | - | - | Brute Force |

