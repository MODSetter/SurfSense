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

